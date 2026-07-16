"""Prompt Crafter Agent — selects the best prompt and injects few-shot examples."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .state import AgentContext


def build(
    ctx: AgentContext,
    prompt_templates: Dict[str, Dict[str, str]],
    knowledge_base,
) -> AgentContext:
    """
    Select a prompt template and format it with story data and few-shot examples.

    Strategy (graph-enhanced):
      1. If graph data exists, use graph queries that consider AC keyword
         profiles, coverage gaps, structural complexity, and human reviews.
      2. Fall back to simple domain-based SQL aggregation if graph not available.
      3. Inject retrieved similar stories as few-shot examples.
    """
    category = ctx.prompt_category
    story = ctx.story

    best_name, reason = _get_best_prompt(knowledge_base, category, story)

    if not best_name or best_name not in prompt_templates:
        best_name = _default_prompt(category)
        reason = "default (no experiments yet)"

    ctx.active_prompt_name = best_name
    template = prompt_templates[best_name]

    ctx.system_prompt = template.get("system_prompt", "")
    ctx.user_prompt = _format_prompt(
        template.get("user_prompt_template", ""),
        story,
        ctx.retrieved_examples,
        category,
    )

    return ctx


def _get_best_prompt(knowledge_base, category: str,
                     story: Dict[str, Any]) -> tuple:
    """
    Select best prompt using graph queries when available.
    Returns (prompt_name, reason).
    """
    try:
        G = knowledge_base.build_graph()
        if G.number_of_nodes() > 0:
            from graph_queries import select_best_prompt
            db_category = "frs" if category.startswith("frs") else "test_case"
            name, reason = select_best_prompt(G, story, db_category)
            if name:
                return name, f"graph: {reason}"
    except Exception:
        pass

    # Fallback: simple domain-based SQL query
    try:
        domain = story.get("domain", "")
        db_category = "frs" if category.startswith("frs") else "test_case"
        results = knowledge_base.query_best_prompt(
            category=db_category, domain=domain, metric="completeness"
        )
        if results:
            return results[0][0], f"sql: domain={domain} avg_score={results[0][1]:.3f}"
    except Exception:
        pass

    return "", ""


def _default_prompt(category: str) -> str:
    if category.startswith("frs"):
        return "frs_few_shot"
    return "tc_few_shot"


def _format_prompt(
    user_template: str,
    story: Dict[str, Any],
    examples: List[Dict[str, Any]],
    category: str,
) -> str:
    few_shot_block = ""
    if examples:
        few_shot_block = "## Similar Stories (for reference)\n"
        for i, ex in enumerate(examples, 1):
            few_shot_block += (
                f"### Example {i}: {ex.get('title', 'N/A')}\n"
                f"**Domain:** {ex.get('domain', '')}\n"
                f"**User Story:** {ex.get('user_story', '')}\n"
                f"**Acceptance Criteria:**\n{ex.get('acceptance_criteria', '')}\n\n"
            )

    try:
        prompt = user_template.format(
            next_fr_num=200, next_tc_prefix="GEN",
            title=story.get("title", ""),
            domain=story.get("domain", ""),
            priority=story.get("priority", ""),
            user_story=story.get("user_story", ""),
            acceptance_criteria=story.get("acceptance_criteria", ""),
            dependencies=story.get("dependencies", "None"),
            frs=story.get("frs", ""),
        )
    except KeyError:
        prompt = user_template

    return few_shot_block + prompt
