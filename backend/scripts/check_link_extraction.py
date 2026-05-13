#!/usr/bin/env python3
"""Check link extraction configuration and test"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

from processors.link_extractor import LinkExtractor

# Load environment
load_dotenv()

print("=" * 60)
print("LINK EXTRACTION CONFIGURATION CHECK")
print("=" * 60)

# Check YouTube API Key
youtube_key = os.getenv("YOUTUBE_API_KEY")
print(f"\n1. YouTube API Key: {'✅ SET' if youtube_key else '❌ NOT SET'}")
if youtube_key:
    print(f"   Length: {len(youtube_key)} chars")
    print(f"   Preview: {youtube_key[:10]}...{youtube_key[-5:]}")
else:
    print("   ⚠️  Without API key, only basic metadata available (oEmbed)")

# Check Vimeo API Key
vimeo_key = os.getenv("VIMEO_API_KEY")
print(f"\n2. Vimeo API Key: {'✅ SET' if vimeo_key else '❌ NOT SET'}")
if vimeo_key:
    print(f"   Length: {len(vimeo_key)} chars")

# Initialize LinkExtractor
print("\n3. Initializing LinkExtractor...")
try:
    extractor = LinkExtractor(youtube_api_key=youtube_key)
    print("   ✅ LinkExtractor initialized")
except Exception as e:
    print(f"   ❌ Failed: {e}")
    sys.exit(1)

# Test URL patterns
print("\n4. Testing URL patterns:")
test_urls = [
    "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    "https://youtu.be/dQw4w9WgXcQ",
    "https://www.youtube.com/embed/dQw4w9WgXcQ",
    "https://vimeo.com/123456789",
    "https://support.hp.com/us-en/document/c01234567",
]

for url in test_urls:
    youtube_id = extractor._extract_youtube_id(url)
    link_type = extractor._classify_link(url)

    print(f"\n   URL: {url}")
    print(f"   YouTube ID: {youtube_id if youtube_id else 'N/A'}")
    print(f"   Type: {link_type}")

# Test YouTube metadata fetch
if youtube_key:
    print("\n5. Testing YouTube API:")
    test_video_id = "dQw4w9WgXcQ"  # Rick Astley - Never Gonna Give You Up
    try:
        metadata = extractor._fetch_youtube_metadata(test_video_id)
        if metadata:
            print("   ✅ API working!")
            print(f"   Title: {metadata.get('title', 'N/A')[:50]}...")
            print(f"   Duration: {metadata.get('duration_seconds', 0)} seconds")
            print(f"   Views: {metadata.get('view_count', 0):,}")
        else:
            print("   ❌ No metadata returned")
    except Exception as e:
        print(f"   ❌ API Error: {e}")
else:
    print("\n5. Testing YouTube oEmbed (fallback):")
    test_video_id = "dQw4w9WgXcQ"
    try:
        metadata = extractor._fetch_youtube_metadata(test_video_id)
        if metadata:
            print("   ✅ oEmbed working!")
            print(f"   Title: {metadata.get('title', 'N/A')[:50]}...")
            print("   Note: Limited metadata (no views, duration, etc.)")
        else:
            print("   ❌ No metadata returned")
    except Exception as e:
        print(f"   ❌ Error: {e}")

print("\n" + "=" * 60)
print("SUMMARY")
print("=" * 60)

if youtube_key:
    print("✅ Full YouTube metadata extraction enabled")
else:
    print("⚠️  Basic YouTube metadata only (oEmbed)")
    print("   To enable full metadata:")
    print("   1. Get API key: https://console.cloud.google.com/apis/credentials")
    print("   2. Enable YouTube Data API v3")
    print("   3. Add to .env: YOUTUBE_API_KEY=your_key_here")

print("\n✅ Link extraction is configured and ready!")
