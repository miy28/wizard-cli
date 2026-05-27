from __future__ import annotations

import pytest

from wizardcli import metadata
from wizardcli.models import AudioAnalysisResult


class FakeResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, object]:
        return self._payload


def test_fetch_similar_artists_dedupes_and_sorts(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, object]] = []

    def fake_get(url: str, params: dict[str, object], timeout: int) -> FakeResponse:
        calls.append({"url": url, "params": params, "timeout": timeout})
        return FakeResponse(
            {
                "similarartists": {
                    "artist": [
                        {"name": "Uzi"},
                        {"name": "Carti"},
                        {"name": "Uzi"},
                        {},
                    ]
                }
            }
        )

    monkeypatch.setattr(metadata.requests, "get", fake_get)

    result = metadata.fetch_similar_artists("demo-key", ["Carti"], limit=5)

    assert result == ["Carti", "Uzi"]
    assert calls[0]["url"] == metadata.LASTFM_ENDPOINT
    assert calls[0]["params"]["artist"] == "Carti"
    assert calls[0]["params"]["limit"] == 5
    assert calls[0]["timeout"] == 15


def test_build_metadata_context_merges_lastfm_and_normalizes(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_fetch(api_key: str, artist_names: list[str], limit: int = 10) -> list[str]:
        assert api_key == "demo-key"
        assert artist_names == ["Lil Uzi Vert", "The Weeknd"]
        return ["Lil Baby", "The Weeknd", "Metro Boomin"]

    monkeypatch.setattr(metadata, "fetch_similar_artists", fake_fetch)

    analysis = AudioAnalysisResult(bpm=140.4, key="A minor", confidence=0.91)
    context = metadata.build_metadata_context(
        ["Lil Uzi Vert", "The Weeknd"],
        analysis,
        lastfm_api_key="demo-key",
    )

    assert context.artists == ["Lil Uzi Vert", "The Weeknd"]
    assert context.bpm == 140.4
    assert context.key == "A minor"
    assert context.keywords == ["Uzi Vert", "Weeknd", "Baby", "Metro Boomin", "A minor", "140 bpm"]
    assert context.summary == "Uzi Vert, Weeknd, Baby, Metro Boomin, A minor, 140 bpm"


def test_build_metadata_context_without_lastfm_key_skips_network() -> None:
    analysis = AudioAnalysisResult(bpm=128.2, key="C#", confidence=0.72)

    context = metadata.build_metadata_context(["Carti"], analysis, lastfm_api_key=None)

    assert context.keywords == ["Carti", "C#", "128 bpm"]
    assert context.summary == "Carti, C#, 128 bpm"
