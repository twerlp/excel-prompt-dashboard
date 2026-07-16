"""Storage Agent — persists experiment results to Qdrant and SQLite."""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone

from .state import AgentContext


def persist(ctx: AgentContext, qdrant_store, knowledge_base) -> AgentContext:
    """
    Write the experiment result to both Qdrant and SQLite.
    Assigns ctx.experiment_id.
    """
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    experiment_id = str(uuid.uuid4())
    ctx.experiment_id = experiment_id

    final = ctx.final_output or ""
    content_hash = hashlib.sha256(final.encode()).hexdigest()[:12]
    category = ctx.prompt_category

    # ── SQLite ──────────────────────────────────────────────────────
    try:
        knowledge_base.insert_experiment({
            "id": experiment_id,
            "story_id": ctx.story_id,
            "prompt_name": ctx.active_prompt_name,
            "category": "frs" if category.startswith("frs") else "test_case",
            "backend": "Cascade",
            "model": f"tier-{ctx.tier_used}",
            "tier": ctx.tier_used,
            "temperature": 0.2,
            "timestamp": timestamp,
            "generated_content": final[:10000],
            "generated_content_hash": content_hash,
            "prompt_hash": _hash_prompt(ctx.system_prompt, ctx.user_prompt),
            "ac_coverage": ctx.evaluation.get("ac_coverage"),
            "fr_precision": ctx.evaluation.get("fr_precision"),
            "format_compliance": ctx.evaluation.get("format_compliance"),
            "semantic_f1": ctx.evaluation.get("semantic_f1"),
            "completeness": ctx.evaluation.get("completeness"),
            "tc_count_score": ctx.evaluation.get("tc_count_score"),
            "tc_type_diversity": ctx.evaluation.get("tc_type_diversity"),
            "tc_step_specificity": ctx.evaluation.get("tc_step_specificity"),
            "tc_expected_measurability": ctx.evaluation.get("tc_expected_measurability"),
            "tc_completeness": ctx.evaluation.get("tc_completeness"),
            "error": ctx.error,
        })

        # Store generated FRs / TCs as normalized rows
        if category.startswith("frs"):
            knowledge_base.insert_generated_frs(
                ctx.story_id, experiment_id, final
            )
        else:
            import json
            try:
                tcs = json.loads(final)
                if isinstance(tcs, list):
                    knowledge_base.insert_generated_tcs(
                        ctx.story_id, experiment_id, tcs
                    )
            except json.JSONDecodeError:
                pass
    except Exception as exc:
        if not ctx.error:
            ctx.error = f"SQLite storage failed: {exc}"

    # ── Qdrant ──────────────────────────────────────────────────────
    try:
        if category.startswith("frs"):
            qdrant_store.upsert_frs_output(
                experiment_id=experiment_id,
                story_id=ctx.story_id,
                prompt_name=ctx.active_prompt_name,
                model=f"tier-{ctx.tier_used}",
                tier=ctx.tier_used,
                fr_lines=final,
                scores=ctx.evaluation if ctx.evaluation else None,
            )
        else:
            qdrant_store.upsert_tc_output(
                experiment_id=experiment_id,
                story_id=ctx.story_id,
                prompt_name=ctx.active_prompt_name,
                model=f"tier-{ctx.tier_used}",
                tier=ctx.tier_used,
                tc_text=final,
                scores=ctx.evaluation if ctx.evaluation else None,
            )
    except Exception as exc:
        if not ctx.error:
            ctx.error = f"Qdrant storage failed: {exc}"

    return ctx


def _hash_prompt(system_prompt: str, user_prompt: str) -> str:
    combined = f"{system_prompt}\n---\n{user_prompt}"
    return hashlib.sha256(combined.encode()).hexdigest()[:12]
