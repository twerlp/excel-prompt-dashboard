"""Cascade Generator Agent — two-tier LLM generation with escalation."""

from __future__ import annotations

from .state import AgentContext

from eval_metrics import quick_score


def generate(
    ctx: AgentContext,
    cheap_backend,
    strong_backend,
    always_both: bool = True,
    frs_threshold: float = 0.7,
    tc_threshold: float = 0.65,
) -> AgentContext:
    """
    Run tier-1 (cheap local model), evaluate, optionally escalate to tier-2.

    Populates ctx.tier1_output, ctx.tier2_output, ctx.final_output, ctx.tier_used.
    """
    category = ctx.prompt_category
    metadata = {
        "story_id": ctx.story_id,
        "category": ctx.active_prompt_name,
    }

    # ── Tier 1: Cheap LLM ───────────────────────────────────────────
    ctx.tier1_output = cheap_backend.complete(
        ctx.system_prompt, ctx.user_prompt, metadata=metadata
    )

    if not always_both:
        threshold = frs_threshold if category.startswith("frs") else tc_threshold
        score = quick_score(ctx.tier1_output or "", category)
        ctx.tier1_scores = {"quick_score": score}
        if score >= threshold:
            ctx.final_output = ctx.tier1_output
            ctx.tier_used = 1
            return ctx

    # ── Tier 2: Strong LLM (with tier-1 draft as context) ───────────
    augmented_prompt = (
        f"{ctx.user_prompt}\n\n"
        f"## Draft Output (review and improve)\n"
        f"{ctx.tier1_output[:2000]}\n\n"
        f"Refine the above draft into a complete, polished output. "
        f"Address any gaps, improve specificity, correct errors, "
        f"and ensure all acceptance criteria are covered."
    )

    ctx.tier2_output = strong_backend.complete(
        ctx.system_prompt, augmented_prompt, metadata=metadata
    )

    ctx.final_output = ctx.tier2_output
    ctx.tier_used = 2
    return ctx
