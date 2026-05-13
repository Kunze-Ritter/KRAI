# Async WebSocket load test using websockets library
import asyncio
import json

from websockets import connect


async def ws_client(uri, token, messages=10):
    async with connect(uri, extra_headers={"Authorization": f"Bearer {token}"}) as ws:
        for i in range(messages):
            await ws.send(json.dumps({"type": "ping"}))
            resp = await ws.recv()
            data = json.loads(resp)
            assert data.get("type") == "pong"
        await ws.close()


async def main():
    # Replace with actual token generation or fixture
    token = "YOUR_TEST_TOKEN"
    uri = "ws://localhost:8000/api/v1/ws"
    tasks = [ws_client(uri, token) for _ in range(50)]  # 50 concurrent clients
    await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(main())
