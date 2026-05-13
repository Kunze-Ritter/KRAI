# Tests for WebSocket endpoints
import json

import pytest
from httpx import AsyncClient
from websockets import connect


@pytest.mark.asyncio
async def test_websocket_connect(async_client: AsyncClient, admin_token: str):
    # Obtain a WebSocket URL from the API (assuming endpoint provides it)
    headers = {"Authorization": f"Bearer {admin_token}"}
    resp = await async_client.get("/api/v1/websocket/url", headers=headers)
    assert resp.status_code == 200
    ws_url = resp.json().get("url")
    assert ws_url
    # Connect using websockets library
    async with connect(ws_url, extra_headers={"Authorization": f"Bearer {admin_token}"}) as websocket:
        # Send a ping or simple message if protocol defines one
        await websocket.send(json.dumps({"type": "ping"}))
        msg = await websocket.recv()
        data = json.loads(msg)
        assert data.get("type") == "pong"
