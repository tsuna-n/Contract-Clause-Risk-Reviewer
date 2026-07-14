"""Agent base class: run() contract, prompt version, tracing."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Generic, TypeVar

from app.llm.client import LLMClient

I = TypeVar("I")
O = TypeVar("O")


class Agent(ABC, Generic[I, O]):
    """Base class for pipeline agents.

    Each agent declares its ``prompt_version`` so runs are reproducible and can
    be attributed to a specific prompt template.
    """

    name: str = "agent"
    prompt_version: str = "v1"

    def __init__(self, llm: LLMClient) -> None:
        self.llm = llm

    @abstractmethod
    def run(self, payload: I) -> O:
        """Execute the agent for a single unit of work."""
        raise NotImplementedError
