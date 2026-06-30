"""Tests for the retrieval evaluator."""

import pytest

from homomics_lab.evaluation.retrieval import RetrievalEvaluator, RetrievalExample


async def _fake_retrieve(query: str, top_k: int = 5):
    # Perfect retrieval: all relevant ids first, then irrelevant.
    return [{"id": f"r{i}"} for i in range(1, top_k + 1)]


@pytest.mark.asyncio
async def test_perfect_retrieval():
    examples = [
        RetrievalExample(query="q1", relevant_ids={"r1", "r2"}),
    ]
    evaluator = RetrievalEvaluator(retrieve=_fake_retrieve, id_fn=lambda x: x["id"])
    results = await evaluator.evaluate(examples, ks=[1, 2, 5])

    assert results["precision"]["1"] == 1.0
    assert results["recall"]["2"] == 1.0
    assert results["mrr"]["1"] == 1.0
    assert results["hit_rate"]["1"] == 1.0
    assert results["ndcg"]["2"] == 1.0


@pytest.mark.asyncio
async def test_partial_retrieval():
    async def retrieve(query: str, top_k: int = 5):
        return [{"id": "a"}, {"id": "b"}, {"id": "c"}]

    examples = [RetrievalExample(query="q", relevant_ids={"a", "d"})]
    evaluator = RetrievalEvaluator(retrieve=retrieve, id_fn=lambda x: x["id"])
    results = await evaluator.evaluate(examples, ks=[2])

    assert results["precision"]["2"] == 0.5
    assert results["recall"]["2"] == 0.5
    assert results["hit_rate"]["2"] == 1.0
    assert results["mrr"]["2"] == 1.0
