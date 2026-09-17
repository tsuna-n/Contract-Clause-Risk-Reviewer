"""The scorer copies evidence from real positions and rejects invented IDs."""

import pytest
from pydantic import ValidationError

from app.ai.agents import RiskScorer, RiskScorerInput
from app.schemas import Clause, ClauseType, PlaybookPosition, RetrievalHit, Span


class StructuredAnswer:
    def __init__(self, answer):
        self.answer = answer
        self.prompt = ""

    def complete_structured(self, **kwargs):
        self.prompt = kwargs["prompt"]
        return kwargs["response_model"].model_validate(self.answer)


def payload():
    position = PlaybookPosition(
        id="pb-termination",
        title="Termination notice",
        clause_type=ClauseType.TERMINATION,
        preferred_language="Either party may terminate on thirty (30) days' notice.",
        fallback_language="Either party may terminate on sixty (60) days' notice.",
    )
    return RiskScorerInput(
        clause=Clause(id="c1", text="Termination without notice.", span=Span(start=0, end=27)),
        hits=[RetrievalHit(position=position, score=1)],
    )


def test_citations_and_fallback_are_copied_verbatim_and_duplicates_removed():
    item = payload()
    llm = StructuredAnswer(
        {
            "risk_level": "medium",
            "rationale": "The notice protection is missing.",
            "citations": [
                {"playbook_position_id": "pb-termination", "language": "preferred"},
                {"playbook_position_id": "pb-termination", "language": "preferred"},
            ],
            "suggested_fallback_position_id": "pb-termination",
        }
    )
    result = RiskScorer(llm).run(item)
    assert len(result.citations) == 1
    assert result.citations[0].excerpt == item.hits[0].position.preferred_language
    assert result.suggested_fallback == item.hits[0].position.fallback_language
    assert "Risk if absent:" in llm.prompt


@pytest.mark.parametrize("field", ["citations", "suggested_fallback_position_id"])
def test_unknown_position_ids_cannot_pass_the_structured_output_model(field):
    answer = {"risk_level": "high", "rationale": "Missing protection."}
    answer[field] = (
        [{"playbook_position_id": "invented", "language": "preferred"}]
        if field == "citations"
        else "invented"
    )
    with pytest.raises(ValidationError):
        RiskScorer(StructuredAnswer(answer)).run(payload())


def test_fallback_selection_is_cited_even_if_no_other_citation_was_selected():
    item = payload()
    llm = StructuredAnswer(
        {
            "risk_level": "medium",
            "rationale": "Missing notice protection.",
            "suggested_fallback_position_id": "pb-termination",
        }
    )
    result = RiskScorer(llm).run(item)
    assert result.citations[0].playbook_position_id == "pb-termination"
    assert result.citations[0].excerpt == result.suggested_fallback


def test_no_retrieved_position_does_not_call_the_model():
    item = payload()
    item.hits = []
    result = RiskScorer(None).run(item)
    assert result.risk_level.value == "unknown"
    assert not result.citations
