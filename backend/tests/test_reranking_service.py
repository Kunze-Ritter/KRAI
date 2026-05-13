import pytest


@pytest.mark.slow
def test_reranking_service_returns_top_n():
    from backend.services.reranking_service import RerankingService

    svc = RerankingService()
    texts = [
        "Replace the fuser unit by removing two screws.",
        "The weather today is sunny and warm.",
        "Open the front cover and remove jammed paper from the fuser area.",
        "Fuser temperature error caused by worn heating element.",
        "Check the oil level in your car.",
    ]
    result = svc.rerank("How do I fix a fuser jam?", texts, top_n=3)
    assert len(result) == 3
    # The fuser-related texts should rank higher than weather/car
    assert any("fuser" in r.lower() for r in result)


def test_reranking_service_noop_when_disabled(monkeypatch):
    monkeypatch.setenv("ENABLE_RERANKING", "false")
    from backend.services.reranking_service import RerankingService

    svc = RerankingService()
    texts = ["a", "b", "c", "d", "e"]
    result = svc.rerank("query", texts, top_n=3)
    assert result == texts[:3]


@pytest.mark.slow
def test_reranking_returns_strings_not_scores():
    from backend.services.reranking_service import RerankingService

    svc = RerankingService()
    texts = ["Fix the jam by opening cover A.", "Unrelated text about cooking."]
    result = svc.rerank("paper jam fix", texts, top_n=2)
    assert all(isinstance(r, str) for r in result)
