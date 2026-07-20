"""Compliance Agent — iterative refinement loop until quality threshold is met.

Server-side metric selection:
  - Ground truth available → uses "completeness" (semantic_F1 + coverage + format)
  - Ground truth absent    → uses "compliance_self" (format + AC coverage + count/structure)

Loop exits on:
  - Score ≥ threshold       → success
  - Max iterations reached   → flagged for human review
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import yaml
from pathlib import Path

from .state import AgentContext
from . import cascade_generator, qa_agent


# ── Config ─────────────────────────────────────────────────────────────

def _load_config() -> Dict[str, Any]:
    config_path = Path(__file__).resolve().parent.parent / "config.yaml"
    if config_path.exists():
        with open(config_path) as f:
            return yaml.safe_load(f) or {}
    return {}

_CONFIG = _load_config()


# ── Metric selection ───────────────────────────────────────────────────

def _select_metric(knowledge_base, story_id: str) -> tuple:
    """
    Choose (metric_name, threshold) based on data availability.

    Returns:
        ("completeness", 0.95)   if ground truth FRs exist
        ("compliance_self", 0.90)  if self-evaluation only
    """
    try:
        gt_frs = knowledge_base.get_ground_truth_frs(story_id)
        if gt_frs:
            return "completeness", _CONFIG.get("compliance", {}).get("threshold_gt", 0.95)
    except Exception:
        pass
    return "compliance_self", _CONFIG.get("compliance", {}).get("threshold_self", 0.90)


# ── Critique injection ─────────────────────────────────────────────────

def _inject_critique(base_prompt: str, previous_scores: Dict[str, float],
                     critique: str, iteration: int) -> str:
    """Build an enriched prompt that tells the LLM what to fix."""
    # Strip previous critique blocks to avoid accumulation
    if "## Previous Attempt Critique" in base_prompt:
        base_prompt = base_prompt.split("## Previous Attempt Critique")[0]

    score_str = ", ".join(
        f"{k}={float(v):.2f}" for k, v in previous_scores.items()
        if isinstance(v, (int, float))
    )

    return (
        f"{base_prompt}\n\n"
        f"## Previous Attempt Critique (iteration {iteration})\n"
        f"The previous attempt scored {score_str}.\n"
        f"Issues to fix:\n{critique}\n\n"
        f"Regenerate the complete output. Address every issue listed above. "
        f"Do NOT include commentary — output only the requested format."
    )


# ── Main compliance loop ───────────────────────────────────────────────

def refine_until_compliant(
    ctx: AgentContext,
    cheap_backend,
    strong_backend,
    knowledge_base,
    always_both: bool = True,
) -> AgentContext:
    """
    Run iterative generation → evaluation → refinement until compliance
    threshold is met or max iterations are exhausted.

    Updates ctx in place and returns it.
    """
    cfg = _CONFIG.get("compliance", {})
    max_iterations = cfg.get("max_iterations", 5)
    inject_critique = cfg.get("critique_inject", True)
    category = ctx.prompt_category

    # Select metric and threshold
    metric_name, threshold = _select_metric(knowledge_base, ctx.story_id)
    ctx.compliance_metric = metric_name
    ctx.compliance_threshold = threshold

    history: List[Dict[str, Any]] = []

    for iteration in range(1, max_iterations + 1):
        # ── Generate ───────────────────────────────────────────────
        # Iteration 1 uses cascade (both tiers). Subsequent use only strong.
        both = always_both if iteration == 1 else True
        ctx = cascade_generator.generate(
            ctx, cheap_backend, strong_backend,
            always_both=both,
        )

        # ── Evaluate ───────────────────────────────────────────────
        ctx = qa_agent.evaluate(ctx, knowledge_base)

        # ── Get score ──────────────────────────────────────────────
        score = ctx.evaluation.get(metric_name, 0)

        # Record iteration history
        history.append({
            "iteration": iteration,
            "score": float(score),
            "critique": ctx.critique,
            "tier_used": ctx.tier_used,
            "metric": metric_name,
        })

        score_exceeded = score >= threshold
        ctx.compliance_score = float(score)
        ctx.iterations_used = iteration
        ctx.iteration_history = history

        if score_exceeded:
            ctx.needs_human_review = False
            ctx.human_review_reason = ""
            return ctx

        # ── Inject critique for next round ────────────────────────
        if inject_critique and iteration < max_iterations:
            ctx.user_prompt = _inject_critique(
                ctx.user_prompt, ctx.evaluation, ctx.critique, iteration
            )

    # Max iterations reached — flag for human
    ctx.needs_human_review = True
    ctx.human_review_reason = (
        f"Max iterations ({max_iterations}) reached. "
        f"Best score: {float(ctx.compliance_score):.3f} "
        f"(threshold: {threshold:.2f}, metric: {metric_name})"
    )
    return ctx
