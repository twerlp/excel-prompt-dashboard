"""Orchestrator — LangChain pipeline that coordinates all agents."""

from __future__ import annotations

from typing import Any, Dict, List

from langchain_core.runnables import RunnableLambda

from .state import AgentContext
from . import rag_agent, prompt_crafter, compliance_agent, qa_agent, storage_agent


def run_pipeline(
    story: Dict[str, Any],
    category: str,
    prompt_templates: Dict[str, Dict[str, str]],
    cheap_backend,
    strong_backend,
    qdrant_store,
    knowledge_base,
    always_both: bool = True,
) -> AgentContext:
    """
    Execute the full agent pipeline for a single story + category.

    Steps:
      1. RAG — retrieve similar stories from Qdrant
      2. Prompt Crafter — select best prompt + inject few-shot examples
      3. Compliance Agent — iterative generate → evaluate → refine loop
         until score ≥ threshold or max iterations reached
      4. Storage — persist to Qdrant + SQLite

    Returns the final AgentContext with all outputs and scores.
    """
    ctx = AgentContext(
        story=story,
        story_id=story.get("story_id", ""),
        prompt_category=category,
    )

    try:
        ctx = rag_agent.retrieve(ctx, qdrant_store)
        ctx = prompt_crafter.build(ctx, prompt_templates, knowledge_base)

        # Compliance loop replaces old cascade + QA steps
        ctx = compliance_agent.refine_until_compliant(
            ctx, cheap_backend, strong_backend, knowledge_base,
            always_both=always_both,
        )

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
