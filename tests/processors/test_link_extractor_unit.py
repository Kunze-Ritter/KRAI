from typing import Any

import pytest

from backend.processors.link_extractor import LinkExtractor

pytestmark = [pytest.mark.unit, pytest.mark.link]


def _make_extractor(youtube_api_key: str | None = None) -> LinkExtractor:
    return LinkExtractor(youtube_api_key=youtube_api_key)


class TestUrlExtraction:
    def test_extract_text_links_http_https(self) -> None:
        extractor = _make_extractor()
        text = "See http://real.example.net for details and " "https://docs.example.org/guide for the full guide."

        links = extractor._extract_text_links(text, page_num=1)  # type: ignore[attr-defined]

        urls = {l["url"] for l in links}
        assert "http://real.example.net" in urls
        assert "https://docs.example.org/guide" in urls
        for link in links:
            assert link["page_number"] == 1
            assert link["confidence_score"] >= 0.7

    def test_extract_text_links_skip_placeholders(self) -> None:
        extractor = _make_extractor()
        text = "Use http://example.com or http://x.x.x.x or http://0.0.0.0 but they are placeholders"

        links = extractor._extract_text_links(text, page_num=1)  # type: ignore[attr-defined]
        urls = {l["url"] for l in links}

        # example.com and x.x.x.x should be filtered as placeholders
        assert all("example.com" not in u for u in urls)
        assert all("x.x.x.x" not in u for u in urls)
        assert all("0.0.0.0" not in u for u in urls)

    def test_extract_text_links_with_context_description(self) -> None:
        extractor = _make_extractor()
        text = (
            "For detailed troubleshooting instructions, visit "
            "http://support.example.com/kb/90001 where all steps are documented."
        )

        links = extractor._extract_text_links(text, page_num=2)  # type: ignore[attr-defined]
        assert len(links) == 1
        link = links[0]
        assert link["url"].startswith("http://support.example.com")
        # Description should contain some human-readable context
        assert "troubleshooting" in link["description"].lower()


class TestYouTubeDetection:
    @pytest.mark.parametrize(
        "url,expected",
        [
            ("https://www.youtube.com/watch?v=ABCDEFGHIJK", "ABCDEFGHIJK"),
            ("http://youtube.com/watch?v=ABCDEFGHIJK", "ABCDEFGHIJK"),
            ("https://youtu.be/ABCDEFGHIJK", "ABCDEFGHIJK"),
            ("https://www.youtube.com/embed/ABCDEFGHIJK", "ABCDEFGHIJK"),
        ],
    )
    def test_extract_youtube_id_variants(self, url: str, expected: str) -> None:
        extractor = _make_extractor()
        video_id = extractor._extract_youtube_id(url)  # type: ignore[attr-defined]
        assert video_id == expected

    @pytest.mark.parametrize(
        "duration,expected",
        [
            ("PT15M33S", 15 * 60 + 33),
            ("PT1H2M10S", 1 * 3600 + 2 * 60 + 10),
            ("PT45S", 45),
            ("", None),
            ("INVALID", None),
        ],
    )
    def test_parse_youtube_duration(self, duration: str, expected: int | None) -> None:
        extractor = _make_extractor()
        value = extractor._parse_youtube_duration(duration)  # type: ignore[attr-defined]
        assert value == expected

    def test_fetch_youtube_metadata_with_api_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        extractor = _make_extractor(youtube_api_key="TEST_KEY")

        class FakeResponse:
            def __init__(self, payload: dict[str, Any]):
                self._payload = payload

            def raise_for_status(self) -> None:  # pragma: no cover - simple stub
                return None

            def json(self) -> dict[str, Any]:
                return self._payload

        def fake_get(url: str, params: dict[str, Any], timeout: int = 10) -> FakeResponse:  # type: ignore[override]
            assert params["id"] == "ABCDEFGHIJK"
            data = {
                "items": [
                    {
                        "snippet": {
                            "title": "Test Video",
                            "description": "Description",
                            "channelId": "CHAN",
                            "channelTitle": "Channel",
                            "publishedAt": "2024-01-01T00:00:00Z",
                            "thumbnails": {
                                "high": {"url": "http://thumb"},
                            },
                        },
                        "contentDetails": {"duration": "PT15M33S"},
                        "statistics": {},
                    }
                ]
            }
            return FakeResponse(data)

        monkeypatch.setattr("backend.processors.link_extractor.requests.get", fake_get)

        meta = extractor._fetch_youtube_metadata("ABCDEFGHIJK")  # type: ignore[attr-defined]
        assert meta is not None
        assert meta["title"] == "Test Video"
        assert meta["duration"] == 15 * 60 + 33
        assert meta["thumbnail_url"] == "http://thumb"

    def test_fetch_youtube_metadata_oembed_fallback(self, monkeypatch: pytest.MonkeyPatch) -> None:
        extractor = _make_extractor(youtube_api_key=None)

        class FakeResponse:
            def __init__(self, payload: dict[str, Any]):
                self._payload = payload

            def raise_for_status(self) -> None:  # pragma: no cover - simple stub
                return None

            def json(self) -> dict[str, Any]:
                return self._payload

        def fake_get(url: str, params: dict[str, Any], timeout: int = 10) -> FakeResponse:  # type: ignore[override]
            assert "oembed" in url
            assert "watch?v=ABCDEFGHIJK" in params["url"]
            payload = {
                "title": "OEmbed Title",
                "thumbnail_url": "http://thumb-oembed",
                "author_name": "Author",
                "provider_name": "YouTube",
                "provider_url": "https://youtube.com",
            }
            return FakeResponse(payload)

        monkeypatch.setattr("backend.processors.link_extractor.requests.get", fake_get)

        meta = extractor._fetch_youtube_metadata("ABCDEFGHIJK")  # type: ignore[attr-defined]
        assert meta is not None
        assert meta["title"] == "OEmbed Title"
        assert meta["thumbnail_url"] == "http://thumb-oembed"

    def test_fetch_youtube_metadata_handles_request_exception(self, monkeypatch: pytest.MonkeyPatch) -> None:
        extractor = _make_extractor(youtube_api_key="TEST_KEY")

        def fake_get(*_args: Any, **_kwargs: Any) -> Any:
            raise RuntimeError("network failure")

        monkeypatch.setattr("backend.processors.link_extractor.requests.get", fake_get)

        meta = extractor._fetch_youtube_metadata("ABCDEFGHIJK")  # type: ignore[attr-defined]
        assert meta is None

    @pytest.mark.parametrize(
        "payload",
        [
            {},
            {"items": []},
        ],
    )
    def test_fetch_youtube_metadata_handles_missing_items(
        self,
        monkeypatch: pytest.MonkeyPatch,
        payload: dict[str, Any],
    ) -> None:
        extractor = _make_extractor(youtube_api_key="TEST_KEY")

        class FakeResponse:
            def __init__(self, data: dict[str, Any]) -> None:
                self._data = data

            def raise_for_status(self) -> None:  # pragma: no cover - simple stub
                return None

            def json(self) -> dict[str, Any]:
                return self._data

        def fake_get(*_args: Any, **_kwargs: Any) -> FakeResponse:
            return FakeResponse(payload)

        monkeypatch.setattr("backend.processors.link_extractor.requests.get", fake_get)

        meta = extractor._fetch_youtube_metadata("ABCDEFGHIJK")  # type: ignore[attr-defined]
        assert meta is None


class TestVideoPlatformDetection:
    @pytest.mark.parametrize(
        "url,expected",
        [
            ("https://example.com/video.mp4", True),
            ("https://example.com/video.MKV", True),
            ("https://example.com/file.txt", False),
        ],
    )
    def test_is_direct_video_url(self, url: str, expected: bool) -> None:
        extractor = _make_extractor()
        assert extractor._is_direct_video_url(url) == expected  # type: ignore[attr-defined]

    @pytest.mark.parametrize(
        "url,platform",
        [
            ("https://vimeo.com/123", "vimeo"),
            ("https://player.brightcove.com/?videoId=1", "brightcove"),
            ("https://wistia.com/medias/abc", "wistia"),
        ],
    )
    def test_detect_video_platform(self, url: str, platform: str) -> None:
        extractor = _make_extractor()
        assert extractor._is_video_platform(url)  # type: ignore[attr-defined]
        detected = extractor._detect_video_platform(url)  # type: ignore[attr-defined]
        assert detected == platform

    def test_create_direct_video_metadata(self) -> None:
        extractor = _make_extractor()
        meta = extractor._create_direct_video_metadata(  # type: ignore[attr-defined]
            "https://cdn.example.com/path/tutorial-video.mp4",
            "link-1",
        )
        assert meta["platform"] == "direct"
        assert meta["link_id"] == "link-1"
        assert meta["video_url"].endswith("tutorial-video.mp4")
        assert "Direct video file" in meta["description"]


class TestLinkClassification:
    @pytest.mark.parametrize(
        "url,expected",
        [
            ("mailto:support@example.com", "email"),
            ("tel:+491234567", "phone"),
            ("https://support.example.com/kb", "support"),
            ("https://download.example.com/driver.exe", "download"),
            ("https://www.youtube.com/watch?v=ABCDEFGHIJK", "video"),
            ("https://example.com/tutorials/how-to-reset", "tutorial"),
            ("https://example.com/other", "external"),
        ],
    )
    def test_classify_link(self, url: str, expected: str) -> None:
        extractor = _make_extractor()
        t = extractor._classify_link(url)  # type: ignore[attr-defined]
        assert t == expected

    @pytest.mark.parametrize(
        "url,expected",
        [
            ("https://www.youtube.com/watch?v=ABCDEFGHIJK", "youtube"),
            ("https://youtu.be/ABCDEFGHIJK", "youtube"),
            ("https://vimeo.com/123456", "vimeo"),
            ("https://support.example.com", "support_portal"),
            ("https://driver.example.com", "download_portal"),
            ("https://example.com", "external"),
        ],
    )
    def test_categorize_link(self, url: str, expected: str) -> None:
        extractor = _make_extractor()
        category = extractor._categorize_link(url)  # type: ignore[attr-defined]
        assert category == expected


class TestDeduplicationAndPlaceholders:
    def test_deduplicate_links_prefers_higher_confidence(self) -> None:
        extractor = _make_extractor()
        links = [
            {
                "url": "http://example.com/page",
                "page_number": 1,
                "description": "low",
                "position_data": {},
                "confidence_score": 0.5,
            },
            {
                "url": "http://example.com/page/",
                "page_number": 2,
                "description": "high",
                "position_data": {},
                "confidence_score": 0.9,
            },
        ]

        deduped = extractor._deduplicate_links(links)  # type: ignore[attr-defined]
        assert len(deduped) == 1
        assert deduped[0]["page_number"] == 2
        assert deduped[0]["confidence_score"] == 0.9

    @pytest.mark.parametrize(
        "url,expected",
        [
            ("http://x.x.x.x/path", True),
            ("http://0.0.0.0/path", True),
            ("http://127.0.0.1/path", True),
            ("http://example.com/path", True),
            ("http://real.example.net", False),
        ],
    )
    def test_is_placeholder_url(self, url: str, expected: bool) -> None:
        extractor = _make_extractor()
        result = extractor._is_placeholder_url(url)  # type: ignore[attr-defined]
        assert result is expected


class TestDescriptionExtraction:
    def test_extract_link_description_removes_url_and_prefix(self) -> None:
        extractor = _make_extractor()
        url = "http://example.com/manual"
        context = "For more information: visit " f"{url} which contains the full service manual."

        description = extractor._extract_link_description(context, url)  # type: ignore[attr-defined]
        desc_lower = description.lower()
        assert url not in description
        assert "for more information" not in desc_lower
        assert "service manual" in desc_lower
