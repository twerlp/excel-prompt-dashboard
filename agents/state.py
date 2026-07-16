"""Agent state passed through the LangChain pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class AgentContext:
    """Carries state between agent steps in the orchestrator pipeline."""

    # Input
    story: Dict[str, Any] = field(default_factory=dict)
    story_id: str = ""
    prompt_category: str = ""  # 'frs' or 'test_case'

    # RAG output
    retrieved_examples: List[Dict[str, Any]] = field(default_factory=list)

    # Prompt Crafter output
    active_prompt_name: str = ""
    system_prompt: str = ""
    user_prompt: str = ""

    # Cascade Generator output
    tier1_output: Optional[str] = None
    tier1_scores: Dict[str, float] = field(default_factory=dict)
    tier2_output: Optional[str] = None
    tier2_scores: Dict[str, float] = field(default_factory=dict)
    final_output: Optional[str] = None
    tier_used: int = 0  # 1 or 2

    # QA output
    evaluation: Dict[str, float] = field(default_factory=dict)
    critique: str = ""
    needs_human_review: bool = False
    human_review_reason: str = ""

    # Metadata
    experiment_id: str = ""
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in self.__dict__.items()}
