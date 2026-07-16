#!/usr/bin/env python3
"""
Evaluation metrics for FRS and test case quality.

Each metric returns a score in [0.0, 1.0]. The `evaluate_generated_output`
function is the main entry point for the QA agent.

Metrics for FRS:
  ac_coverage       — % of acceptance criteria mapped to ≥1 generated FR
  fr_precision      — % of generated FRs that are valid (not hallucinated)
  format_compliance — % of FR lines matching "FR-XXX: The system shall..."
  semantic_f1       — semantic overlap between generated and ground truth FRs
  completeness      — weighted composite score

Metrics for Test Cases:
  tc_count_score     — score based on ideal count range (4–6)
  tc_type_diversity  — variety of test types present
  tc_step_specificity — average step detail quality
  tc_expected_measurability — whether expected results are specific/measurable
  tc_completeness    — weighted composite score

Usage:
  from eval_metrics import evaluate_frs, evaluate_test_cases, quick_score
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

import numpy as np
from sentence_transformers import SentenceTransformer


_EMBEDDER: Optional[SentenceTransformer] = None


def _get_embedder() -> SentenceTransformer:
    global _EMBEDDER
    if _EMBEDDER is None:
        _EMBEDDER = SentenceTransformer("all-MiniLM-L6-v2")
    return _EMBEDDER


# ── FRS Metrics ────────────────────────────────────────────────────────

def ac_coverage(acceptance_criteria: str, generated_frs: str) -> float:
    """Fraction of AC items that have at least one semantically matching FR."""
    ac_items = _extract_ac_items(acceptance_criteria)
    fr_lines = [l.strip() for l in generated_frs.split("\n")
                if l.strip().startswith("FR-")]

    if not ac_items or not fr_lines:
        return 0.0

    model = _get_embedder()
    ac_vectors = model.encode(ac_items)
    fr_vectors = model.encode(fr_lines)

    sim_matrix = np.dot(fr_vectors, ac_vectors.T) / (
        np.linalg.norm(fr_vectors, axis=1, keepdims=True) *
        np.linalg.norm(ac_vectors, axis=1, keepdims=True).T + 1e-10
    )
    max_per_ac = np.max(sim_matrix, axis=0)
    covered = int(np.sum(max_per_ac > 0.4))
    return covered / len(ac_items)


def fr_precision(acceptance_criteria: str, generated_frs: str) -> float:
    """Fraction of generated FRs that map to at least one AC item."""
    ac_items = _extract_ac_items(acceptance_criteria)
    fr_lines = [l.strip() for l in generated_frs.split("\n")
                if l.strip().startswith("FR-")]

    if not fr_lines:
        return 0.0
    if not ac_items:
        return 0.5  # neutral if no ground truth

    model = _get_embedder()
    ac_vectors = model.encode(ac_items)
    fr_vectors = model.encode(fr_lines)

    sim_matrix = np.dot(fr_vectors, ac_vectors.T) / (
        np.linalg.norm(fr_vectors, axis=1, keepdims=True) *
        np.linalg.norm(ac_vectors, axis=1, keepdims=True).T + 1e-10
    )
    max_per_fr = np.max(sim_matrix, axis=1)
    valid = int(np.sum(max_per_fr > 0.4))
    return valid / len(fr_lines)


def format_compliance_frs(generated_frs: str) -> float:
    """Fraction of FR lines matching canonical format."""
    lines = [l.strip() for l in generated_frs.split("\n") if l.strip()]
    fr_lines = [l for l in lines if l.startswith("FR-")]
    if not fr_lines:
        return 0.0
    compliant = 0
    for line in fr_lines:
        if re.match(r"FR-\d{3}:\s+The system shall ", line):
            compliant += 1
    return compliant / len(fr_lines)


def semantic_f1(generated_frs: str, ground_truth_frs: List[str]) -> float:
    """Semantic overlap between generated and ground truth FR batches."""
    gen_lines = [l.strip() for l in generated_frs.split("\n")
                 if l.strip().startswith("FR-")]
    gt_lines = [l.strip() for l in ground_truth_frs if l.strip()]

    if not gen_lines or not gt_lines:
        return 0.0

    model = _get_embedder()
    gen_vecs = model.encode(gen_lines)
    gt_vecs = model.encode(gt_lines)

    sims = np.dot(gen_vecs, gt_vecs.T) / (
        np.linalg.norm(gen_vecs, axis=1, keepdims=True) *
        np.linalg.norm(gt_vecs, axis=1, keepdims=True).T + 1e-10
    )

    precision = float(np.mean(np.max(sims, axis=1)))
    recall = float(np.mean(np.max(sims, axis=0)))
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def completeness_frs(acceptance_criteria: str, generated_frs: str,
                      ground_truth_frs: Optional[List[str]] = None) -> float:
    """Weighted composite FRS score."""
    ac_cov = ac_coverage(acceptance_criteria, generated_frs)
    fr_prec = fr_precision(acceptance_criteria, generated_frs)
    fmt = format_compliance_frs(generated_frs)

    if ground_truth_frs:
        sf1 = semantic_f1(generated_frs, ground_truth_frs)
        return 0.3 * ac_cov + 0.2 * fr_prec + 0.3 * sf1 + 0.2 * fmt
    return 0.4 * ac_cov + 0.3 * fr_prec + 0.3 * fmt


# ── Test Case Metrics ──────────────────────────────────────────────────

def tc_count_score(tc_list: List[Dict[str, Any]]) -> float:
    """Score based on ideal TC count (4–6)."""
    n = len(tc_list)
    if n < 3:
        return 0.3
    if n == 3:
        return 0.6
    if 4 <= n <= 6:
        return 1.0
    if 7 <= n <= 8:
        return 0.8
    return 0.5


def tc_type_diversity(tc_list: List[Dict[str, Any]]) -> float:
    """Score based on variety of test types present."""
    expected_types = {"Functional", "Boundary", "Security",
                      "Performance", "Integration", "Reliability"}
    present = {tc.get("test_type", "").strip() for tc in tc_list}
    overlap = len(present & expected_types)
    return min(1.0, overlap / 4.0)


def tc_step_specificity(tc_list: List[Dict[str, Any]]) -> float:
    """Score based on step detail (word count proxy)."""
    if not tc_list:
        return 0.0
    scores = []
    for tc in tc_list:
        steps = tc.get("steps", "")
        words = len(steps.split())
        if words < 10:
            scores.append(0.3)
        elif words < 20:
            scores.append(0.6)
        elif words < 60:
            scores.append(1.0)
        else:
            scores.append(0.8)
    return float(np.mean(scores))


def tc_expected_measurability(tc_list: List[Dict[str, Any]]) -> float:
    """Score based on whether expected results contain concrete indicators."""
    if not tc_list:
        return 0.0
    indicators = [
        r"\d{3}",              # HTTP status codes
        r"\$\d+",              # dollar amounts
        r"\d+\s*(?:ms|sec|%)", # time/percentage
        r"status.*→",          # state transitions
        r"message[:\s]*['\"]",  # explicit messages
        r"(?:Error|error)[:\s]*['\"]",  # error messages
    ]
    scores = []
    for tc in tc_list:
        expected = tc.get("expected", "")
        matches = sum(1 for pat in indicators if re.search(pat, expected))
        scores.append(min(1.0, matches / 3.0))
    return float(np.mean(scores))


def completeness_tc(tc_list: List[Dict[str, Any]]) -> float:
    """Weighted composite TC score."""
    if not tc_list:
        return 0.0
    return (0.20 * tc_count_score(tc_list) +
            0.25 * tc_type_diversity(tc_list) +
            0.25 * tc_step_specificity(tc_list) +
            0.30 * tc_expected_measurability(tc_list))


# ── Quick score (for cascade threshold check) ──────────────────────────

def quick_score(output: str, category: str) -> float:
    """Fast heuristic score without embeddings (for real-time cascade decisions)."""
    if category.startswith("frs"):
        return format_compliance_frs(output)
    else:
        lines = [l.strip() for l in output.split("\n") if l.strip()]
        n = len(lines)
        count_score = 1.0 if 3 <= n <= 8 else (0.5 if n > 0 else 0.0)
        return count_score


# ── Helpers ────────────────────────────────────────────────────────────

def _extract_ac_items(text: str) -> List[str]:
    """Extract acceptance criteria items from text."""
    items = re.findall(r"\d+\.\s*(.*?)(?=\d+\.\s|\Z)", text, re.DOTALL)
    return [item.strip() for item in items if item.strip()]


# ── Main entry points for QA agent ─────────────────────────────────────

def evaluate_frs(acceptance_criteria: str, generated_frs: str,
                  ground_truth_frs: Optional[List[str]] = None) -> Dict[str, float]:
    """Return all FRS scores as a dict."""
    return {
        "ac_coverage": ac_coverage(acceptance_criteria, generated_frs),
        "fr_precision": fr_precision(acceptance_criteria, generated_frs),
        "format_compliance": format_compliance_frs(generated_frs),
        "semantic_f1": semantic_f1(generated_frs, ground_truth_frs or []),
        "completeness": completeness_frs(acceptance_criteria,
                                          generated_frs, ground_truth_frs),
    }


def evaluate_test_cases(tc_list: List[Dict[str, Any]]) -> Dict[str, float]:
    """Return all TC scores as a dict."""
    return {
        "tc_count_score": tc_count_score(tc_list),
        "tc_type_diversity": tc_type_diversity(tc_list),
        "tc_step_specificity": tc_step_specificity(tc_list),
        "tc_expected_measurability": tc_expected_measurability(tc_list),
        "tc_completeness": completeness_tc(tc_list),
    }
