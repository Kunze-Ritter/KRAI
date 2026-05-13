"""
Test if Firecrawl creates jobs in Redis queue when receiving scrape requests
"""

import asyncio
import os
import subprocess

import httpx
from dotenv import load_dotenv

load_dotenv()


def check_redis_queue(queue_name="bull:scrapeQueue:wait"):
    """Check Redis queue length"""
    try:
        result = subprocess.run(
            ["docker", "exec", "krai-redis-prod", "redis-cli", "LLEN", queue_name],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return int(result.stdout.strip())
        return None
    except Exception as e:
        print(f"Error checking Redis: {e}")
        return None


async def test_firecrawl_queue():
    """Test if Firecrawl API creates jobs in Redis queue"""

    firecrawl_url = os.getenv("FIRECRAWL_API_URL", "http://localhost:9004")
    api_key = os.getenv("FIRECRAWL_API_KEY", "fc-local-dev-key-not-required")

    print("=" * 80)
    print("🔍 Testing Firecrawl Redis Queue Integration")
    print("=" * 80)
    print()

    # Check initial queue state
    print("📊 Initial Redis Queue State:")
    initial_count = check_redis_queue()
    print(f"   Jobs in queue: {initial_count}")
    print()

    # Send scrape request
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    payload = {"url": "https://example.com", "formats": ["markdown"]}

    print("📤 Sending scrape request to Firecrawl API...")
    print(f"   URL: {firecrawl_url}/v0/scrape")
    print(f"   Payload: {payload}")
    print()

    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            response = await client.post(f"{firecrawl_url}/v0/scrape", json=payload, headers=headers)

            print(f"📥 Response Status: {response.status_code}")

            if response.status_code == 200:
                data = response.json()
                print(f"   Response: {data}")
            else:
                print(f"   Response: {response.text[:500]}")

        except httpx.TimeoutException:
            print("⏱️  Request timed out (5s)")
        except Exception as e:
            print(f"❌ Error: {type(e).__name__}: {e}")

    print()

    # Wait a bit for job to be queued
    print("⏳ Waiting 2 seconds for job to be queued...")
    await asyncio.sleep(2)

    # Check queue state after request
    print()
    print("📊 Redis Queue State After Request:")
    after_count = check_redis_queue()
    print(f"   Jobs in queue: {after_count}")

    if after_count is not None and initial_count is not None:
        diff = after_count - initial_count
        if diff > 0:
            print(f"   ✅ {diff} new job(s) added to queue!")
        else:
            print("   ❌ No jobs added to queue - this is the problem!")

    print()

    # Check all Firecrawl queues
    print("📊 All Firecrawl Queues:")
    queues = [
        "bull:scrapeQueue:wait",
        "bull:scrapeQueue:active",
        "bull:scrapeQueue:completed",
        "bull:scrapeQueue:failed",
        "bull:crawlQueue:wait",
        "bull:crawlQueue:active",
    ]

    for queue in queues:
        count = check_redis_queue(queue)
        if count is not None:
            print(f"   {queue:40} {count} jobs")

    print()
    print("=" * 80)
    print("✅ Test Complete")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(test_firecrawl_queue())
