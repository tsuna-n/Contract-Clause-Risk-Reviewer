"""Playbook matcher: retrieve positions relevant to a clause."""

from __future__ import annotations

from app.agents.base import Agent
from app.llm.client import LLMClient
from app.rag.retriever import Retriever
from app.schemas.clause import Clause
from app.schemas.playbook import RetrievalHit


class Matcher(Agent[Clause, list[RetrievalHit]]):
    """Maps a clause to candidate playbook positions via the retriever."""

    name = "matcher"

    def __init__(self, llm: LLMClient, retriever: Retriever) -> None:
        super().__init__(llm)
        self.retriever = retriever

    def run(self, payload: Clause) -> list[RetrievalHit]:
        """Return playbook positions matching ``payload``."""
        return self.retriever.retrieve(payload)
