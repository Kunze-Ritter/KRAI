# Tests for batch operations endpoints
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_batch_delete_documents(async_client: AsyncClient, admin_token: str):
    headers = {"Authorization": f"Bearer {admin_token}"}
    # Create two documents to delete
    payload1 = {"title": "Doc1", "content": "A", "product_id": 1, "manufacturer_id": 1}
    payload2 = {"title": "Doc2", "content": "B", "product_id": 1, "manufacturer_id": 1}
    resp1 = await async_client.post("/api/v1/documents", json=payload1, headers=headers)
    resp2 = await async_client.post("/api/v1/documents", json=payload2, headers=headers)
    ids = [resp1.json()["id"], resp2.json()["id"]]
    # Batch delete
    delete_resp = await async_client.post(
        "/api/v1/batch/delete", json={"ids": ids, "resource": "documents"}, headers=headers
    )
    assert delete_resp.status_code == 200
    result = delete_resp.json()
    assert result.get("deleted") == len(ids)
