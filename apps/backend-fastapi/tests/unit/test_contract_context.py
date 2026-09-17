"""References must resolve to real text and never choose ambiguous numbering."""

from pathlib import Path

from app.ai.agents import Segmenter
from app.ai.context import ContractContext
from app.parsers import parse_txt


def index(text):
    document = parse_txt(text.encode())
    clauses = Segmenter(None).run(document)
    return document, clauses, ContractContext(document, clauses)


def test_real_sell_off_clause_resolves_its_appendix_duration():
    path = Path("data/contracts/datacalltechnologies-content-license-agreement.txt")
    document, clauses, context = index(path.read_text())
    clause = next(c for c in clauses if c.text.startswith("7.5 "))
    sources = context.sources_for(clause)
    appendix = next(s for s in sources if s.label == "Appendix 2")
    assert "2.4 Sell-off period: 3 months after termination" in appendix.text
    assert document.text[appendix.span.start : appendix.span.end] == appendix.text
    assert not appendix.truncated


def test_parent_section_reference_includes_its_subsections_and_deduplicates():
    text = (
        "1. Liability. Except as provided in Section 2 and Section 2.1.\n\n"
        "2. Exceptions.\n\n2.1 Fraud is uncapped.\n\n3. Notices. Written notice."
    )
    document, clauses, context = index(text)
    sources = context.sources_for(clauses[0])
    assert len(sources) == 1
    assert "Fraud is uncapped" in sources[0].text
    assert "3. Notices" not in sources[0].text
    assert sources[0].text == document.text[sources[0].span.start : sources[0].span.end]


def test_missing_and_ambiguous_references_are_not_invented():
    _, clauses, context = index(
        "1. Liability. See Section 2 and Section 99.\n\n2. Main terms.\n\n"
        "APPENDIX A\n\n2. Other terms."
    )
    assert not context.sources_for(clauses[0])


def test_thai_reference_can_match_arabic_numbering():
    _, clauses, context = index("ข้อ 1. ความรับผิดตามข้อ ๒\n\nข้อ 2. ข้อยกเว้นความรับผิด\n\nข้อ 3. หนังสือแจ้ง")
    sources = context.sources_for(clauses[0])
    assert len(sources) == 1
    assert "ข้อยกเว้นความรับผิด" in sources[0].text


def test_context_size_is_bounded_and_partial_text_is_marked():
    _, clauses, context = index(
        "1. Liability. See Appendix A.\n\n2. Notices. Written notice.\n\nAPPENDIX A\n"
        + "Detailed terms. " * 1000
    )
    sources = context.sources_for(clauses[0])
    assert len(sources) == 1
    assert len(sources[0].text) <= 3500
    assert sources[0].truncated


def test_self_reference_does_not_duplicate_clause_text():
    _, clauses, context = index("1. Terms. This Section 1 defines the obligations.\n\n2. Notices.")
    assert not context.sources_for(clauses[0])
