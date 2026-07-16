"""Orchestrator — LangChain pipeline that coordinates all agents."""

from __future__ import annotations

from typing import Any, Dict, List

from langchain_core.runnables import RunnableLambda

from .state import AgentContext
from . import rag_agent, prompt_crafter, cascade_generator, qa_agent, storage_agent


def run_pipeline(
    story: Dict[str, Any],
    category: str,
    prompt_templates: Dict[str, Dict[str, str]],
    cheap_backend,
    strong_backend,
    qdrant_store,
    knowledge_base,
    always_both: bool = True,
    frs_threshold: float = 0.7,
    tc_threshold: float = 0.65,
) -> AgentContext:
    """
    Execute the full agent pipeline for a single story + category.

    Returns the final AgentContext with all outputs and scores.
    """
    ctx = AgentContext(
        story=story,
        story_id=story.get("story_id", ""),
        prompt_category=category,
    )

    try:
        # Step 1: Retrieve similar stories
        ctx = rag_agent.retrieve(ctx, qdrant_store)

        # Step 2: Select and build prompt
        ctx = prompt_crafter.build(ctx, prompt_templates, knowledge_base)

        # Step 3: Generate with cascade
        ctx = cascade_generator.generate(
            ctx, cheap_backend, strong_backend,
            always_both=always_both,
            frs_threshold=frs_threshold,
            tc_threshold=tc_threshold,
        )

        # Step 4: Evaluate
        ctx = qa_agent.evaluate(ctx, knowledge_base)

        # Step 5: Persist
        ctx = storage_agent.persist(ctx, qdrant_store, knowledge_base)

    except Exception as exc:
        ctx.error = str(exc)

    return ctx


def build_langchain_pipeline(
    prompt_templates: Dict[str, Dict[str, str]],
    cheap_backend,
    strong_backend,
    qdrant_store,
    knowledge_base,
    always_both: bool = True,
):
    """
    Build a LangChain RunnableSequence for batch processing.

    Returns a callable that takes a dict with keys:
      story, category, prompt_templates (already provided)
    """
    def _run_pipeline(inputs: Dict[str, Any]) -> AgentContext:
        return run_pipeline(
            story=inputs["story"],
            category=inputs["category"],
            prompt_templates=prompt_templates,
            cheap_backend=cheap_backend,
            strong_backend=strong_backend,
            qdrant_store=qdrant_store,
            knowledge_base=knowledge_base,
            always_both=always_both,
        )

    return RunnableLambda(_run_pipeline)
