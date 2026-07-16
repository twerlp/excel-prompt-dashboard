"""RAG Agent — retrieves similar stories from Qdrant for few-shot context."""

from __future__ import annotations

from typing import Any, Dict, List

from .state import AgentContext


def retrieve(ctx: AgentContext, qdrant_store) -> AgentContext:
    """
    Query Qdrant for stories similar to the current one.
    Populates ctx.retrieved_examples.
    """
    story = ctx.story
    query_text = story.get("story_text") or (
        story.get("user_story", "") + "\n" + story.get("acceptance_criteria", "")
    )

    if not query_text.strip():
        return ctx

    domain = story.get("domain", "")
    results = qdrant_store.search_similar_stories(
        query_text,
        top_k=4,
        min_score=0.2,
    )

    # Filter out the current story itself, take top 3
    examples = [r for r in results if r.get("story_id") != ctx.story_id][:3]
    ctx.retrieved_examples = examples
    return ctx
