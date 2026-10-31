"""Unit tests for the pure functions: chunking, fusion, schema validation."""
import pytest
from pydantic import ValidationError

from app.schemas import DocumentAnalysis
from app.services.chunking import chunk_words
from app.services.retrieval import reciprocal_rank_fusion


def test_chunks_overlap():
    text = " ".join(str(i) for i in range(10))
    chunks = chunk_words(text, size=4, overlap=2)
    assert chunks[0] == "0 1 2 3"
    assert chunks[1] == "2 3 4 5"          # last 2 words repeated
    assert chunks[-1].endswith("9")        # nothing lost at the end


def test_chunk_rejects_bad_overlap():
    with pytest.raises(ValueError):
        chunk_words("a b c", size=3, overlap=3)


def test_rrf_rewards_agreement():
    keyword = [3, 1, 2]
    vector = [1, 4, 3]
    assert reciprocal_rank_fusion([keyword, vector])[:2] == [1, 3]


def valid_analysis(**overrides):
    data = dict(department="Finance", confidence=0.9, reasoning="invoice", doc_type="Invoice",
                summary="An invoice.", urgency="Medium")
    data.update(overrides)
    return data


def test_schema_accepts_valid_output():
    assert DocumentAnalysis.model_validate(valid_analysis()).department == "Finance"


@pytest.mark.parametrize("bad", [
    {"department": "Marketing"},       # not a KMRL department
    {"confidence": 1.7},               # out of range
    {"urgency": "Whenever"},           # not an allowed value
])
def test_schema_rejects_invalid_output(bad):
    with pytest.raises(ValidationError):
        DocumentAnalysis.model_validate(valid_analysis(**bad))
