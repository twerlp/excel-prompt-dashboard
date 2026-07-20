"""QA Agent — evaluates generated FRS / test cases."""

from __future__ import annotations

import json
from typing import Any, Dict, List

from .state import AgentContext

from eval_metrics import (
    evaluate_frs,
    evaluate_test_cases,
    compliance_self_frs,
    compliance_self_tc,
)


def evaluate(ctx: AgentContext, knowledge_base) -> AgentContext:
    """
    Evaluate the generated output. Uses compliance_self when no ground
    truth exists. Populates ctx.evaluation and ctx.critique.

    Human review gating is handled by the compliance agent — QA agent
    only provides scores + actionable critique.
    """
    category = ctx.prompt_category
    final = ctx.final_output or ""
    story_id = ctx.story_id

    # Check ground truth availability
    has_gt = _has_ground_truth(knowledge_base, story_id)

    if category.startswith("frs"):
        ctx.evaluation = _evaluate_frs_output(ctx, knowledge_base, story_id, final, has_gt)
    else:
        ctx.evaluation = _evaluate_tc_output(ctx, final, has_gt)

    return ctx


def _has_ground_truth(knowledge_base, story_id: str) -> bool:
    try:
        gt = knowledge_base.get_ground_truth_frs(story_id)
        return len(gt) > 0
    except Exception:
        return False


def _evaluate_frs_output(
    ctx: AgentContext, knowledge_base, story_id: str,
    generated_frs: str, has_gt: bool,
) -> Dict[str, float]:
    acceptance_criteria = ctx.story.get("acceptance_criteria", "")

    if has_gt:
        gt_frs: List[str] = []
        try:
            gt_rows = knowledge_base.get_ground_truth_frs(story_id)
            gt_frs = [r.get("fr_text", "") for r in gt_rows]
        except Exception:
            pass
        scores = evaluate_frs(acceptance_criteria, generated_frs, gt_frs)
    else:
        scores = compliance_self_frs(acceptance_criteria, generated_frs)

    critique_parts = []
    if scores.get("ac_coverage", 1) < 0.5:
        critique_parts.append(f"Coverage low ({scores['ac_coverage']:.0%}): missing acceptance criteria")
    if scores.get("format_compliance", 1) < 0.7:
        critique_parts.append(f"Format issues ({scores['format_compliance']:.0%}): FR lines must match 'FR-XXX: The system shall...'")
    if scores.get("fr_count_score", 1) < 0.5:
        critique_parts.append(f"FR count mismatch: ensure one FR per acceptance criterion")
    if has_gt and scores.get("semantic_f1", 1) < 0.3:
        critique_parts.append("Low semantic match with expected requirements")
    ctx.critique = "; ".join(critique_parts) if critique_parts else "Good"

    return scores


def _evaluate_tc_output(
    ctx: AgentContext, generated_tc: str, has_gt: bool,
) -> Dict[str, float]:
    tcs: List[Dict[str, Any]] = []
    try:
        parsed = json.loads(generated_tc)
        if isinstance(parsed, list):
            tcs = parsed
        elif isinstance(parsed, dict) and "tc_id" in parsed:
            tcs = [parsed]
    except json.JSONDecodeError:
        pass

    if has_gt:
        scores = evaluate_test_cases(tcs)
    else:
        scores = compliance_self_tc(tcs)

    critique_parts = []
    if scores.get("tc_count_score", 1) < 0.6:
        critique_parts.append(f"TC count issue ({len(tcs)} test cases): aim for 4-6")
    if scores.get("tc_type_diversity", 1) < 0.5:
        critique_parts.append("Low type diversity: add Boundary/Security/Integration tests")
    if scores.get("tc_step_specificity", 1) < 0.5:
        critique_parts.append("Test steps are too brief: provide numbered, actionable steps")
    if scores.get("tc_expected_measurability", 1) < 0.5:
        critique_parts.append("Expected results not specific enough: include HTTP codes, exact messages, state changes")
    ctx.critique = "; ".join(critique_parts) if critique_parts else "Good"

    return scores
