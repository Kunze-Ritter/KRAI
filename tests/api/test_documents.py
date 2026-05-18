# Tests for document CRUD endpoints
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_document(async_client: AsyncClient, admin_token: str):
    headers = {"Authorization": f"Bearer {admin_token}"}
    payload = {
        "title": "Test Document",
        "content": "Sample content",
        "product_id": 1,
        "manufacturer_id": 1,
    }
    response = await async_client.post("/api/v1/documents", json=payload, headers=headers)
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == payload["title"]


@pytest.mark.asyncio
async def test_get_documents(async_client: AsyncClient, admin_token: str):
    headers = {"Authorization": f"Bearer {admin_token}"}
    response = await async_client.get("/api/v1/documents", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


@pytest.mark.asyncio
async def test_update_document(async_client: AsyncClient, admin_token: str):
    headers = {"Authorization": f"Bearer {admin_token}"}
    # First create a document
    payload = {"title": "Doc to Update", "content": "Old", "product_id": 1, "manufacturer_id": 1}
    create_resp = await async_client.post("/api/v1/documents", json=payload, headers=headers)
    doc_id = create_resp.json()["id"]
    # Update
    update_payload = {"title": "Updated Title", "content": "New content"}
    resp = await async_client.patch(f"/api/v1/documents/{doc_id}", json=update_payload, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["title"] == "Updated Title"


@pytest.mark.asyncio
async def test_delete_document(async_client: AsyncClient, admin_token: str):
    headers = {"Authorization": f"Bearer {admin_token}"}
    payload = {"title": "Doc to Delete", "content": "Temp", "product_id": 1, "manufacturer_id": 1}
    create_resp = await async_client.post("/api/v1/documents", json=payload, headers=headers)
    doc_id = create_resp.json()["id"]
    del_resp = await async_client.delete(f"/api/v1/documents/{doc_id}", headers=headers)
    assert del_resp.status_code == 204
