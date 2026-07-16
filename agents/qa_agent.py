"""QA Agent — evaluates generated FRS / test cases."""

from __future__ import annotations

import json
from typing import Any, Dict, List

from .state import AgentContext

from eval_metrics import (
    evaluate_frs,
    evaluate_test_cases,
    format_compliance_frs,
    semantic_f1,
)


def evaluate(ctx: AgentContext, knowledge_base) -> AgentContext:
    """
    Evaluate the generated output against ground truth and heuristics.
    Populates ctx.evaluation, ctx.needs_human_review, ctx.critique.
    """
    category = ctx.prompt_category
    final = ctx.final_output or ""
    story_id = ctx.story_id

    if category.startswith("frs"):
        ctx.evaluation = _evaluate_frs_output(ctx, knowledge_base, story_id, final)
    else:
        ctx.evaluation = _evaluate_tc_output(ctx, final)

    # Determine if human review is needed
    completeness = ctx.evaluation.get("completeness", ctx.evaluation.get("tc_completeness", 0))
    ctx.needs_human_review = completeness < 0.5
    if ctx.needs_human_review:
        ctx.human_review_reason = f"Low completeness score: {completeness:.2f}"
    elif ctx.tier_used == 1 and completeness < 0.7:
        ctx.needs_human_review = True
        ctx.human_review_reason = "Tier-1 output below 0.7"

    return ctx


def _evaluate_frs_output(
    ctx: AgentContext, knowledge_base, story_id: str, generated_frs: str
) -> Dict[str, float]:
    acceptance_criteria = ctx.story.get("acceptance_criteria", "")

    # Get ground truth FRs
    gt_frs: List[str] = []
    try:
        gt_rows = knowledge_base.get_ground_truth_frs(story_id)
        gt_frs = [r.get("fr_text", "") for r in gt_rows]
    except Exception:
        pass

    scores = evaluate_frs(acceptance_criteria, generated_frs, gt_frs)

    critique_parts = []
    if scores["ac_coverage"] < 0.5:
        critique_parts.append(f"Coverage low ({scores['ac_coverage']:.0%}): missing acceptance criteria")
    if scores["format_compliance"] < 0.7:
        critique_parts.append(f"Format issues ({scores['format_compliance']:.0%}): FR lines not canonical")
    if scores.get("semantic_f1", 0) < 0.3:
        critique_parts.append(f"Low semantic match with ground truth")
    ctx.critique = "; ".join(critique_parts) if critique_parts else "Good"

    return scores


def _evaluate_tc_output(ctx: AgentContext, generated_tc: str) -> Dict[str, float]:
    # Try to parse as JSON array
    tcs: List[Dict[str, Any]] = []
    try:
        parsed = json.loads(generated_tc)
        if isinstance(parsed, list):
            tcs = parsed
        elif isinstance(parsed, dict) and "tc_id" in parsed:
            tcs = [parsed]
    except json.JSONDecodeError:
        pass

    scores = evaluate_test_cases(tcs)

    critique_parts = []
    if scores["tc_count_score"] < 0.6:
        critique_parts.append(f"TC count issue ({len(tcs)} test cases)")
    if scores["tc_type_diversity"] < 0.5:
        critique_parts.append("Low type diversity: add Boundary/Security tests")
    if scores["tc_expected_measurability"] < 0.5:
        critique_parts.append("Expected results not specific enough")
    ctx.critique = "; ".join(critique_parts) if critique_parts else "Good"

    return scores
