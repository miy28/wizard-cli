from __future__ import annotations

import random

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


def test_build_metadata_context_uses_guaranteed_and_sampled_modifiers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_fetch(api_key: str, artist_names: list[str], limit: int = 10) -> list[str]:
        assert api_key == "demo-key"
        assert artist_names == ["Lil Uzi Vert", "The Weeknd"]
        return ["Lil Baby", "The Weeknd", "Metro Boomin"]

    def fake_top_tags(api_key: str, artist_name: str, limit: int = 10) -> list[str]:
        assert api_key == "demo-key"
        return {
            "Lil Uzi Vert": ["rage", "trap", "hip hop"],
            "The Weeknd": ["rnb", "pop", "synthpop"],
        }[artist_name]

    monkeypatch.setattr(metadata, "fetch_similar_artists", fake_fetch)
    monkeypatch.setattr(metadata, "fetch_top_tags", fake_top_tags)

    analysis = AudioAnalysisResult(bpm=140.4, key="A minor", confidence=0.91)
    context = metadata.build_metadata_context(
        ["Lil Uzi Vert", "The Weeknd"],
        analysis,
        lastfm_api_key="demo-key",
        descriptors=["edm", "beat switch"],
        rng=random.Random(7),
    )

    assert context.artists == ["Lil Uzi Vert", "The Weeknd"]
    assert context.descriptors == ["edm", "beat switch"]
    assert context.bpm == 140.4
    assert context.key == "A minor"
    assert "Lil Uzi Vert type beat" in context.keywords
    assert "Lil Uzi Vert x The Weeknd type beat" in context.keywords
    assert "edm type beat" in context.keywords
    assert "beat switch type beat" in context.keywords
    assert any(keyword.startswith("Metro Boomin type beat") for keyword in context.keywords)
    assert context.summary.startswith("Lil Uzi Vert type beat")
    assert context.lastfm_enabled is True
    assert context.lastfm_similar_artists == ["Lil Baby", "The Weeknd", "Metro Boomin"]
    assert context.lastfm_discovered_descriptors == [
        "rage",
        "trap",
        "hip hop",
        "rnb",
        "pop",
        "synthpop",
    ]


def test_build_metadata_context_without_lastfm_key_skips_network() -> None:
    analysis = AudioAnalysisResult(bpm=128.2, key="C#", confidence=0.72)

    context = metadata.build_metadata_context(
        ["Carti"],
        analysis,
        lastfm_api_key=None,
        descriptors=["plugg"],
    )

    assert "Carti type beat" in context.keywords
    assert "plugg type beat" in context.keywords
    assert "C#" not in context.keywords
    assert "128 bpm" not in context.keywords
    assert context.key == "C#"
    assert context.bpm == 128.2
    assert context.lastfm_enabled is False


def test_build_metadata_context_includes_artist_top_tags_in_keywords(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_fetch(api_key: str, artist_names: list[str], limit: int = 10) -> list[str]:
        return []

    def fake_top_tags(api_key: str, artist_name: str, limit: int = 10) -> list[str]:
        assert api_key == "demo-key"
        assert artist_name == "Playboi Carti"
        return ["rage", "trap"]

    monkeypatch.setattr(metadata, "fetch_similar_artists", fake_fetch)
    monkeypatch.setattr(metadata, "fetch_top_tags", fake_top_tags)

    analysis = AudioAnalysisResult(bpm=150.0, key="D minor", confidence=0.84)
    context = metadata.build_metadata_context(
        ["Playboi Carti"],
        analysis,
        lastfm_api_key="demo-key",
    )

    assert "rage type beat" in context.keywords
    assert "trap type beat" in context.keywords
    assert "Playboi Carti rage type beat" in context.keywords


def test_generate_keyword_phrases_does_not_use_whole_prompt_as_single_seed() -> None:
    analysis = AudioAnalysisResult(bpm=160.0, key="F minor", confidence=0.8)

    keywords = metadata.generate_keyword_phrases(
        artist_modifiers=["Lil Uzi Vert"],
        descriptor_modifiers=["edm", "beat switch", "trap", "hardstyle", "dnb"],
        analysis=analysis,
    )

    assert "Lil Uzi Vert hardstyle type beat" in keywords
    assert "hardstyle Lil Uzi Vert type beat" in keywords
    assert "free hardstyle beat" in keywords
    assert "dnb type beat" in keywords
    assert "Lil Uzi Vert edm beat switch trap hardstyle dnb type beat" not in keywords


def test_generate_keyword_phrases_includes_descriptor_first_combo() -> None:
    analysis = AudioAnalysisResult(bpm=130.0, key="G minor", confidence=0.8)

    keywords = metadata.generate_keyword_phrases(
        artist_modifiers=["Izaya Tiji"],
        descriptor_modifiers=["ambient"],
        analysis=analysis,
    )

    assert "Izaya Tiji ambient type beat" in keywords
    assert "ambient Izaya Tiji type beat" in keywords


def test_build_modifier_pool_keeps_individual_artists_and_caps_combo_artist() -> None:
    pool = metadata.build_modifier_pool(
        ["Lil Uzi Vert", "Playboi Carti", "Yeat"],
        lastfm_api_key=None,
    )

    assert pool.guaranteed_artists == [
        "Lil Uzi Vert",
        "Playboi Carti",
        "Yeat",
        "Lil Uzi Vert x Playboi Carti",
    ]


def test_pack_keywords_limits_to_youtube_tag_character_budget() -> None:
    analysis = AudioAnalysisResult(bpm=150.0, key="D minor", confidence=0.8)

    keywords = metadata.generate_keyword_phrases(
        artist_modifiers=["Lil Uzi Vert", "Playboi Carti", "Future"],
        descriptor_modifiers=["rage", "hardstyle", "dnb", "edm", "trap"],
        analysis=analysis,
        max_keywords=100,
        max_characters=120,
    )

    assert len(", ".join(keywords)) <= 120
