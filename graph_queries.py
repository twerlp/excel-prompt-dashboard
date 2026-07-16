#!/usr/bin/env python3
"""
Graph queries for prompt selection and experiment analysis.

Builds a NetworkX DiGraph from SQLite rows, then runs graph-aware
queries that consider acceptance-criterion keywords, coverage edges,
semantic similarity, and human reviews to rank prompts.

Node types: Story, AcceptanceCriterion, GroundTruthFR, GroundTruthTC,
            Experiment, GeneratedFR, GeneratedTC, Prompt, HumanReview

Edges:
  Story       -[:HAS_AC]→ AcceptanceCriterion
  Story       -[:HAS_GT_FR]→ GroundTruthFR
  Story       -[:HAS_GT_TC]→ GroundTruthTC
  Experiment  -[:USES_PROMPT]→ Prompt
  Experiment  -[:RUNS_ON]→ Story
  Experiment  -[:PRODUCES_FR]→ GeneratedFR
  Experiment  -[:PRODUCES_TC]→ GeneratedTC
  GeneratedFR -[:COVERS]→ AcceptanceCriterion       (cosine > 0.4)
  GeneratedFR -[:SIMILAR_TO]→ GroundTruthFR         (cosine, with weight)
  HumanReview -[:REVIEWS]→ Experiment

Usage:
  from graph_queries import build_graph, select_best_prompt
  G = build_graph(kb)
  best = select_best_prompt(G, story_ac_keywords, category="frs")
"""

from __future__ import annotations

import collections
import re
import sqlite3
from typing import Any, Dict, List, Optional, Tuple

import networkx as nx
import numpy as np

# ── AC Keyword tagging ────────────────────────────────────────────────

KEYWORD_PATTERNS: Dict[str, re.Pattern] = {
    "validation":     re.compile(r"\b(valid|check|format|reject|compli)\w*\b", re.I),
    "notification":   re.compile(r"\b(email|send|notif|alert|dispatch)\w*\b", re.I),
    "state_change":   re.compile(r"\b(status|state|transit|becom|transition|activate)\w*\b", re.I),
    "security":       re.compile(r"\b(encrypt|hash|auth|token|password|secret|credential|permission)\w*\b", re.I),
    "retry":          re.compile(r"\b(retry|resend|attempt|backoff|recovery|re-submit)\w*\b", re.I),
    "timing":         re.compile(r"\b(second|minute|hour|within|timeout|expir|delay|instant|TTL)\w*\b", re.I),
    "api_endpoint":   re.compile(r"\b(POST|GET|PUT|DELETE|PATCH|endpoint|API|REST)\b", re.I),
    "ui_component":   re.compile(r"\b(form|button|page|modal|toggle|dropdown|input|field)\w*\b", re.I),
}

# ── Graph builder ──────────────────────────────────────────────────────

_EMBEDDER = None


def _get_embedder():
    global _EMBEDDER
    if _EMBEDDER is None:
        from sentence_transformers import SentenceTransformer
        _EMBEDDER = SentenceTransformer("all-MiniLM-L6-v2")
    return _EMBEDDER


def _cosine(a, b):
    a, b = np.asarray(a), np.asarray(b)
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-10))


def _extract_ac_items(text: str) -> List[str]:
    items = re.findall(r"\d+\.\s*(.*?)(?=\d+\.\s|\Z)", text, re.DOTALL)
    return [item.strip() for item in items if item.strip()]


def _tag_ac_keywords(text: str) -> Dict[str, bool]:
    """Tag an acceptance criterion with boolean keyword flags."""
    flags = {}
    for name, pattern in KEYWORD_PATTERNS.items():
        flags[f"kw_{name}"] = bool(pattern.search(text))
    return flags


def _make_node_id(node_type: str, *parts: str) -> str:
    return f"{node_type}::{'::'.join(parts)}"


def build_graph(db_path: str = "kb.sqlite") -> nx.DiGraph:
    """
    Build a NetworkX DiGraph from the SQLite knowledge base.

    Returns a directed graph with typed nodes and weighted edges.
    """
    G = nx.DiGraph()
    embedder = _get_embedder()

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    # ── Stories + AcceptanceCriteria ──────────────────────────────────
    story_rows = conn.execute(
        "SELECT story_id, title, domain, priority, story_points, "
        "user_story, acceptance_criteria FROM stories ORDER BY story_id"
    ).fetchall()

    for row in story_rows:
        sid = row["story_id"]
        story_node = _make_node_id("Story", sid)
        G.add_node(story_node, type="Story", **dict(row))

        ac_items = _extract_ac_items(row["acceptance_criteria"])
        G.nodes[story_node]["ac_count"] = len(ac_items)

        for i, ac_text in enumerate(ac_items):
            ac_id = _make_node_id("AC", sid, str(i))
            tags = _tag_ac_keywords(ac_text)
            G.add_node(ac_id, type="AcceptanceCriterion",
                       story_id=sid, index=i, text=ac_text, **tags)
            G.add_edge(story_node, ac_id, rel="HAS_AC")

    # ── GroundTruth FRs ───────────────────────────────────────────────
    gt_fr_rows = conn.execute(
        "SELECT id, story_id, fr_ref, fr_text FROM functional_requirements "
        "WHERE source = 'ground_truth' ORDER BY id"
    ).fetchall()
    gt_fr_by_id: Dict[int, Dict] = {}

    for row in gt_fr_rows:
        fr_id = _make_node_id("GroundTruthFR", str(row["id"]))
        G.add_node(fr_id, type="GroundTruthFR",
                   story_id=row["story_id"], fr_ref=row["fr_ref"],
                   fr_text=row["fr_text"])
        G.add_edge(_make_node_id("Story", row["story_id"]), fr_id, rel="HAS_GT_FR")
        gt_fr_by_id[row["id"]] = dict(row)

    # ── GroundTruth TCs ───────────────────────────────────────────────
    gt_tc_rows = conn.execute(
        "SELECT id, story_id, tc_id, test_type FROM test_cases "
        "WHERE source = 'ground_truth' ORDER BY id"
    ).fetchall()

    for row in gt_tc_rows:
        tc_id = _make_node_id("GroundTruthTC", str(row["id"]))
        G.add_node(tc_id, type="GroundTruthTC",
                   story_id=row["story_id"], tc_id=row["tc_id"],
                   test_type=row["test_type"])
        G.add_edge(_make_node_id("Story", row["story_id"]), tc_id, rel="HAS_GT_TC")

    # ── Prompts ───────────────────────────────────────────────────────
    prompt_rows = conn.execute(
        "SELECT DISTINCT prompt_name, category FROM experiments"
    ).fetchall()
    for row in prompt_rows:
        prompt_id = _make_node_id("Prompt", row["prompt_name"])
        if not G.has_node(prompt_id):
            G.add_node(prompt_id, type="Prompt",
                       name=row["prompt_name"],
                       category=row["category"])

    # ── Experiments ───────────────────────────────────────────────────
    exp_rows = conn.execute(
        "SELECT id, story_id, prompt_name, category, backend, model, tier, "
        "ac_coverage, fr_precision, format_compliance, semantic_f1, "
        "completeness, tc_count_score, tc_type_diversity, "
        "tc_step_specificity, tc_expected_measurability, "
        "tc_completeness, generated_content, error "
        "FROM experiments ORDER BY id"
    ).fetchall()

    for row in exp_rows:
        exp_id = _make_node_id("Experiment", row["id"])
        node_attrs = dict(row)
        # Convert any bytes/None scores to floats
        for k in (
            "ac_coverage", "fr_precision", "format_compliance",
            "semantic_f1", "completeness", "tc_count_score",
            "tc_type_diversity", "tc_step_specificity",
            "tc_expected_measurability", "tc_completeness",
        ):
            v = node_attrs.get(k)
            try:
                node_attrs[k] = float(v)
            except (TypeError, ValueError):
                node_attrs[k] = None
        G.add_node(exp_id, type="Experiment", **node_attrs)

        story_node = _make_node_id("Story", row["story_id"])
        prompt_node = _make_node_id("Prompt", row["prompt_name"])
        G.add_edge(exp_id, story_node, rel="RUNS_ON")
        G.add_edge(exp_id, prompt_node, rel="USES_PROMPT")

    # ── Generated FRs + COVERS / SIMILAR_TO edges ─────────────────────
    gen_fr_rows = conn.execute(
        "SELECT id, story_id, experiment_id, fr_text FROM functional_requirements "
        "WHERE source = 'generated' ORDER BY id"
    ).fetchall()

    # Pre-compute AC embeddings per story (for COVERS edges)
    ac_texts_by_story: Dict[str, List[Tuple[str, str]]] = collections.defaultdict(list)
    for node, data in G.nodes(data=True):
        if data.get("type") == "AcceptanceCriterion":
            ac_texts_by_story[data["story_id"]].append((node, data["text"]))

    # Batch-encode all AC texts
    all_ac_texts = []
    all_ac_keys = []
    for sid, pairs in ac_texts_by_story.items():
        for node_id, text in pairs:
            all_ac_texts.append(text)
            all_ac_keys.append((sid, node_id))
    ac_embeddings = embedder.encode(all_ac_texts) if all_ac_texts else np.array([])
    ac_emb_map = {key: ac_embeddings[i] for i, key in enumerate(all_ac_keys)}

    # Process generated FRs
    for row in gen_fr_rows:
        fr_id = _make_node_id("GeneratedFR", str(row["id"]))
        G.add_node(fr_id, type="GeneratedFR",
                   story_id=row["story_id"],
                   experiment_id=row["experiment_id"],
                   fr_text=row["fr_text"])

        exp_id = _make_node_id("Experiment", row["experiment_id"])
        if G.has_node(exp_id):
            G.add_edge(exp_id, fr_id, rel="PRODUCES_FR")

    # Add COVERS edges (GeneratedFR → AC) — expensive, do once for all FRs
    gen_fr_texts = []
    gen_fr_ids = []
    for node, data in G.nodes(data=True):
        if data.get("type") == "GeneratedFR":
            gen_fr_texts.append(data.get("fr_text", ""))
            gen_fr_ids.append(node)

    if gen_fr_texts and ac_embeddings.shape[0] > 0:
        fr_embeddings = embedder.encode(gen_fr_texts)

        for i, fr_node in enumerate(gen_fr_ids):
            fr_vec = fr_embeddings[i]
            fr_data = G.nodes[fr_node]
            sid = fr_data.get("story_id", "")
            ac_pairs = ac_texts_by_story.get(sid, [])

            for ac_node, _ in ac_pairs:
                ac_key = (sid, ac_node)
                if ac_key in ac_emb_map:
                    sim = _cosine(fr_vec, ac_emb_map[ac_key])
                    if sim > 0.4:
                        G.add_edge(fr_node, ac_node, rel="COVERS", weight=float(sim))

        # Add SIMILAR_TO edges (GeneratedFR → GroundTruthFR)
        gt_fr_texts = []
        gt_fr_nodes = []
        for node, data in G.nodes(data=True):
            if data.get("type") == "GroundTruthFR":
                gt_fr_texts.append(data.get("fr_text", ""))
                gt_fr_nodes.append(node)

        if gt_fr_texts:
            gt_embeddings = embedder.encode(gt_fr_texts)
            for i, fr_node in enumerate(gen_fr_ids):
                fr_data = G.nodes[fr_node]
                sid = fr_data.get("story_id", "")
                for j, gt_node in enumerate(gt_fr_nodes):
                    if G.nodes[gt_node].get("story_id") == sid:
                        sim = _cosine(fr_embeddings[i], gt_embeddings[j])
                        if sim > 0.5:
                            G.add_edge(fr_node, gt_node, rel="SIMILAR_TO",
                                       weight=float(sim))

    # ── Human Reviews ─────────────────────────────────────────────────
    review_rows = conn.execute(
        "SELECT experiment_id, score_frs, score_tc, notes FROM human_reviews"
    ).fetchall()
    for row in review_rows:
        review_id = _make_node_id("HumanReview", row["experiment_id"])
        G.add_node(review_id, type="HumanReview",
                   score_frs=row["score_frs"],
                   score_tc=row["score_tc"],
                   notes=row["notes"])
        exp_node = _make_node_id("Experiment", row["experiment_id"])
        if G.has_node(exp_node):
            G.add_edge(review_id, exp_node, rel="REVIEWS")

    conn.close()
    return G


# ═══════════════════════════════════════════════════════════════════════════
# Query functions (each takes G + params, returns prompt rankings)
# ═══════════════════════════════════════════════════════════════════════════

def _prompt_name_for_exp(G: nx.DiGraph, exp_node: str) -> str:
    """Follow USES_PROMPT edge to get the prompt name for an experiment."""
    for _, neighbor, data in G.edges(exp_node, data=True):
        if data.get("rel") == "USES_PROMPT":
            return G.nodes[neighbor].get("name", "")
    return ""


def _ac_nodes_for_story(G: nx.DiGraph, story_node: str) -> List[str]:
    """Return all AC node IDs for a story."""
    return [n for n in G.successors(story_node)
            if G.nodes[n].get("type") == "AcceptanceCriterion"]


def _exp_nodes_for_story(G: nx.DiGraph, story_node: str, category: str) -> List[str]:
    """Return experiment nodes for a story with the given category."""
    exps = []
    for n in G.predecessors(story_node):
        if G.nodes[n].get("type") == "Experiment" and G.nodes[n].get("category") == category:
            exps.append(n)
    return exps


# ── Query 1: Keyword-weighted prompt ranking ──────────────────────────

def select_by_ac_profile(
    G: nx.DiGraph,
    query_ac_keywords: List[str],
    domain: Optional[str] = None,
    category: str = "frs",
) -> List[Tuple[str, float, str]]:
    """
    Rank prompts by keyword overlap between the query story's AC keywords
    and past stories' AC keywords, weighted by ac_coverage scores.

    Returns: [(prompt_name, score, reason), ...]
    """
    prompt_scores: Dict[str, List[float]] = collections.defaultdict(list)

    for node, data in G.nodes(data=True):
        if data.get("type") != "Story":
            continue
        if domain and data.get("domain") != domain:
            continue

        story_node = node
        story_acs = _ac_nodes_for_story(G, story_node)

        # Collect all keywords from this story's ACs
        story_kw = set()
        for ac_node in story_acs:
            for kw_name in KEYWORD_PATTERNS:
                if G.nodes[ac_node].get(f"kw_{kw_name}"):
                    story_kw.add(kw_name)

        overlap = len(set(query_ac_keywords) & story_kw)
        if overlap < 2:
            continue

        for exp_node in _exp_nodes_for_story(G, story_node, category):
            coverage = G.nodes[exp_node].get("ac_coverage", 0)
            prompt = _prompt_name_for_exp(G, exp_node)
            if prompt:
                prompt_scores[prompt].append(coverage * overlap)

    ranking = []
    for prompt, scores in prompt_scores.items():
        avg = sum(scores) / len(scores) if scores else 0
        n = len(scores)
        ranking.append((prompt, avg, f"keyword-overlap × coverage (n={n})"))
    return sorted(ranking, key=lambda x: x[1], reverse=True)


# ── Query 2: Coverage gap ranking ─────────────────────────────────────

def select_by_coverage_gap(
    G: nx.DiGraph,
    query_ac_keywords: List[str],
    domain: Optional[str] = None,
    category: str = "frs",
) -> List[Tuple[str, float, str]]:
    """
    Rank prompts by how few ACs they leave uncovered on stories with
    similar AC keyword profiles.

    Returns: [(prompt_name, gap_closure_score, reason), ...]
    """
    prompt_gaps: Dict[str, List[float]] = collections.defaultdict(list)

    for node, data in G.nodes(data=True):
        if data.get("type") != "Story":
            continue
        if domain and data.get("domain") != domain:
            continue

        story_node = node
        story_acs = _ac_nodes_for_story(G, story_node)
        total_acs = len(story_acs)

        story_kw = set()
        for ac_node in story_acs:
            for kw_name in KEYWORD_PATTERNS:
                if G.nodes[ac_node].get(f"kw_{kw_name}"):
                    story_kw.add(kw_name)

        overlap = len(set(query_ac_keywords) & story_kw)
        if overlap < 2:
            continue

        for exp_node in _exp_nodes_for_story(G, story_node, category):
            gen_frs = [
                n for n in G.successors(exp_node)
                if G.nodes[n].get("type") == "GeneratedFR"
            ]

            covered = set()
            for fr_node in gen_frs:
                for _, ac_node, e_data in G.edges(fr_node, data=True):
                    if e_data.get("rel") == "COVERS":
                        covered.add(ac_node)

            uncovered = total_acs - len(covered)
            gap_ratio = uncovered / total_acs if total_acs else 1.0
            closure = 1.0 - gap_ratio  # higher = better

            prompt = _prompt_name_for_exp(G, exp_node)
            if prompt:
                prompt_gaps[prompt].append(float(closure))

    ranking = []
    for prompt, gaps in prompt_gaps.items():
        avg = sum(gaps) / len(gaps) if gaps else 0
        n = len(gaps)
        ranking.append((prompt, avg, f"coverage-closure (n={n})"))
    return sorted(ranking, key=lambda x: x[1], reverse=True)


# ── Query 3: Multi-objective ranking (coverage + semantic + human) ────

def select_multi_objective(
    G: nx.DiGraph,
    domain: Optional[str] = None,
    category: str = "frs",
) -> List[Tuple[str, float, str, Dict[str, float]]]:
    """
    Rank prompts by composite score: coverage × F1, with human review bonus.

    Returns: [(prompt_name, score, reason, breakdown_dict), ...]
    """
    prompt_metrics: Dict[str, Dict[str, List[float]]] = collections.defaultdict(
        lambda: collections.defaultdict(list)
    )

    for node, data in G.nodes(data=True):
        if data.get("type") != "Story":
            continue
        if domain and data.get("domain") != domain:
            continue

        story_node = node
        for exp_node in _exp_nodes_for_story(G, story_node, category):
            exp_data = G.nodes[exp_node]
            prompt = _prompt_name_for_exp(G, exp_node)
            if not prompt:
                continue

            if exp_data.get("ac_coverage") is not None:
                prompt_metrics[prompt]["coverage"].append(float(exp_data["ac_coverage"]))
            if exp_data.get("semantic_f1") is not None:
                prompt_metrics[prompt]["f1"].append(float(exp_data["semantic_f1"]))
            if exp_data.get("completeness") is not None:
                prompt_metrics[prompt]["completeness"].append(float(exp_data["completeness"]))
            if exp_data.get("tc_completeness") is not None:
                prompt_metrics[prompt]["tc_completeness"].append(float(exp_data["tc_completeness"]))

            # Check for human reviews
            for review_node in G.predecessors(exp_node):
                if G.nodes[review_node].get("type") == "HumanReview":
                    r = G.nodes[review_node]
                    if category == "frs" and r.get("score_frs"):
                        prompt_metrics[prompt]["human"].append(float(r["score_frs"]) / 5.0)
                    elif category == "test_case" and r.get("score_tc"):
                        prompt_metrics[prompt]["human"].append(float(r["score_tc"]) / 5.0)

    ranking = []
    for prompt, metrics in prompt_metrics.items():
        cov = (sum(metrics["coverage"]) / len(metrics["coverage"])
               if metrics["coverage"] else 0)
        f1 = (sum(metrics["f1"]) / len(metrics["f1"])
              if metrics["f1"] else 0)
        comp = (sum(metrics["completeness"]) / len(metrics["completeness"])
                if metrics["completeness"] else
                sum(metrics["tc_completeness"]) / len(metrics["tc_completeness"])
                if metrics["tc_completeness"] else 0)
        human = (sum(metrics["human"]) / len(metrics["human"])
                 if metrics["human"] else None)

        if human is not None:
            score = 0.35 * cov + 0.35 * f1 + 0.20 * comp + 0.10 * human
            reason = f"coverage={cov:.2f} f1={f1:.2f} comp={comp:.2f} human={human:.2f}"
        else:
            score = 0.40 * cov + 0.40 * f1 + 0.20 * comp
            reason = f"coverage={cov:.2f} f1={f1:.2f} comp={comp:.2f} (no human)"

        n = len(metrics.get("coverage", []))
        ranking.append((prompt, score, f"{reason} (n={n})",
                        {"coverage": cov, "f1": f1, "completeness": comp, "human": human}))

    return sorted(ranking, key=lambda x: x[1], reverse=True)


# ── Query 4: Structural match (same AC count, similar complexity) ─────

def select_by_structure(
    G: nx.DiGraph,
    ac_count: int,
    story_points: int,
    domain: Optional[str] = None,
    category: str = "frs",
    tolerance: float = 0.3,
) -> List[Tuple[str, float, str]]:
    """
    Rank prompts by how well they perform on stories with similar
    structural complexity (AC count and story points).

    Returns: [(prompt_name, score, reason), ...]
    """
    prompt_scores: Dict[str, List[float]] = collections.defaultdict(list)

    for node, data in G.nodes(data=True):
        if data.get("type") != "Story":
            continue
        if domain and data.get("domain") != domain:
            continue

        s_ac_count = data.get("ac_count", 0)
        s_points = data.get("story_points", 0)

        # Structural similarity: within tolerance range
        if ac_count > 0:
            ac_distance = abs(s_ac_count - ac_count) / max(s_ac_count, ac_count)
        else:
            ac_distance = 0
        if story_points > 0:
            sp_distance = abs(s_points - story_points) / max(s_points, story_points)
        else:
            sp_distance = 0

        if ac_distance > tolerance or sp_distance > tolerance:
            continue

        similarity = 1.0 - 0.5 * ac_distance - 0.5 * sp_distance

        for exp_node in _exp_nodes_for_story(G, node, category):
            comp = G.nodes[exp_node].get("completeness") or G.nodes[exp_node].get("tc_completeness") or 0
            prompt = _prompt_name_for_exp(G, exp_node)
            if prompt:
                prompt_scores[prompt].append(float(comp) * similarity)

    ranking = []
    for prompt, scores in prompt_scores.items():
        avg = sum(scores) / len(scores) if scores else 0
        n = len(scores)
        ranking.append((prompt, avg, f"structural-match (n={n}, tol={tolerance})"))
    return sorted(ranking, key=lambda x: x[1], reverse=True)


# ── Query 5: Consensus ranking (ensemble of all strategies) ────────────

def select_consensus(
    G: nx.DiGraph,
    query_ac_keywords: List[str],
    ac_count: int = 0,
    story_points: int = 0,
    domain: Optional[str] = None,
    category: str = "frs",
) -> List[Tuple[str, float, str, Dict[str, Any]]]:
    """
    Ensemble ranking: average normalized scores from all four strategies,
    plus per-strategy breakdown.

    Returns: [(prompt_name, consensus_score, "consensus", strategy_breakdown), ...]
    """
    strategies = {
        "ac_profile": [(p, s, r) for p, s, r in select_by_ac_profile(G, query_ac_keywords, domain, category)],
        "coverage_gap": [(p, s, r) for p, s, r in select_by_coverage_gap(G, query_ac_keywords, domain, category)],
        "multi_objective": [(p, s, r) for p, s, r, _ in select_multi_objective(G, domain, category)],
        "structure": [(p, s, r) for p, s, r in select_by_structure(G, ac_count, story_points, domain, category)],
    }

    # Build union of prompts across all strategies
    all_prompts: Dict[str, Dict[str, float]] = collections.defaultdict(dict)
    for strat_name, results in strategies.items():
        for prompt, score, _ in results:
            all_prompts[prompt][strat_name] = score

    # Normalize each strategy's scores to [0, 1]
    normalized: Dict[str, Dict[str, float]] = collections.defaultdict(dict)
    for strat_name in strategies:
        strat_scores = [(p, all_prompts[p].get(strat_name, 0))
                        for p in all_prompts]
        max_s = max(s for _, s in strat_scores) if strat_scores else 1.0
        if max_s > 0:
            for prompt, score in strat_scores:
                normalized[prompt][strat_name] = score / max_s

    # Consensus: mean of available strategy scores
    consensus = []
    for prompt, strat_scores in normalized.items():
        available = list(strat_scores.values())
        consensus_score = sum(available) / len(available) if available else 0
        breakdown = {
            "consensus": consensus_score,
            **strat_scores,
        }
        consensus.append((prompt, consensus_score, "consensus-ensemble", breakdown))

    return sorted(consensus, key=lambda x: x[1], reverse=True)


# ── Utility: select best prompt for a story ────────────────────────────

def select_best_prompt(
    G: nx.DiGraph,
    story: Dict[str, Any],
    category: str = "frs",
    domain: Optional[str] = None,
) -> Tuple[str, str]:
    """
    High-level entry point for the Prompt Crafter agent.

    Args:
        G: The graph (from build_graph).
        story: Story dict with keys: story_id, domain, acceptance_criteria,
               story_points.
        category: 'frs' or 'test_case'.
        domain: Optional domain override.

    Returns:
        (prompt_name, reason_string)
    """
    ac_text = story.get("acceptance_criteria", "")
    ac_items = _extract_ac_items(ac_text)
    ac_count = len(ac_items)
    story_points = story.get("story_points", 0)

    # Extract keywords from this story's ACs
    keywords = set()
    for ac in ac_items:
        for kw_name, pattern in KEYWORD_PATTERNS.items():
            if pattern.search(ac):
                keywords.add(kw_name)
    kw_list = list(keywords)

    domain = domain or story.get("domain", "")

    # Try consensus ranking first
    ranking = select_consensus(
        G, kw_list,
        ac_count=ac_count,
        story_points=story_points,
        domain=domain,
        category=category,
    )

    if ranking:
        best = ranking[0]
        breakdown = best[3] if len(best) > 3 else {}
        strategies = ", ".join(
            f"{k}={v:.2f}" for k, v in breakdown.items()
            if k != "consensus" and v > 0
        )
        return best[0], f"consensus={best[1]:.3f} ({strategies})"

    # Fallback to individual strategies
    for strategy_fn in [
        select_multi_objective,
        lambda g: select_by_ac_profile(g, kw_list, domain, category),
        lambda g: select_by_coverage_gap(g, kw_list, domain, category),
        lambda g: select_by_structure(g, ac_count, story_points, domain, category),
    ]:
        results = strategy_fn(G)
        if results:
            return results[0][0], f"fallback: {results[0][2]}"

    return "frs_few_shot" if category.startswith("frs") else "tc_few_shot", "default"


# ── Target AC analysis (for QA agent gap reporting) ───────────────────

def find_uncovered_acs(
    G: nx.DiGraph, experiment_id: str,
) -> List[Dict[str, Any]]:
    """
    Return list of ACs not covered by any generated FR for an experiment.
    """
    exp_node = _make_node_id("Experiment", experiment_id)
    if not G.has_node(exp_node):
        return []

    story_node = None
    for _, neighbor, data in G.edges(exp_node, data=True):
        if data.get("rel") == "RUNS_ON":
            story_node = neighbor
            break
    if not story_node:
        return []

    ac_nodes = _ac_nodes_for_story(G, story_node)
    gen_frs = [
        n for n in G.successors(exp_node)
        if G.nodes[n].get("type") == "GeneratedFR"
    ]

    # Collect all covered AC ids
    covered_ids = set()
    for fr_node in gen_frs:
        for _, ac_node, e_data in G.edges(fr_node, data=True):
            if e_data.get("rel") == "COVERS":
                covered_ids.add(ac_node)

    uncovered = []
    for ac_node in ac_nodes:
        if ac_node not in covered_ids:
            ac_data = G.nodes[ac_node]
            uncovered.append({
                "ac_id": ac_node,
                "index": ac_data.get("index", -1),
                "text": ac_data.get("text", "")[:120],
                "keywords": [
                    k.replace("kw_", "") for k, v in ac_data.items()
                    if k.startswith("kw_") and v
                ],
            })

    return uncovered
