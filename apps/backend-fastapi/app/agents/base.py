"""Agent base class: run() contract, prompt version, tracing."""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.llm.client import LLMClient


class Agent[InputT, OutputT](ABC):
    """Base class for pipeline agents.

    Each agent declares its ``prompt_version`` so runs are reproducible and can
    be attributed to a specific prompt template.
    """

    name: str = "agent"
    prompt_version: str = "v1"

    def __init__(self, llm: LLMClient) -> None:
        self.llm = llm

    @abstractmethod
    def run(self, payload: InputT) -> OutputT:
        """Execute the agent for a single unit of work."""
        raise NotImplementedError
