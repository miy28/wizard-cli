from __future__ import annotations

import os

import pytest

from wizardcli.metadata import build_metadata_context, fetch_similar_artists
from wizardcli.models import AudioAnalysisResult

pytestmark = pytest.mark.integration


def test_lastfm_round_trip_uses_api_and_builds_context() -> None:
    api_key = os.getenv("LASTFM_API_KEY")
    if not api_key:
        pytest.skip("Set LASTFM_API_KEY to run the Last.fm integration test")

    artist_names = ["Kendrick Lamar"]
    related = fetch_similar_artists(api_key, artist_names, limit=5)

    assert related
    assert all(isinstance(name, str) and name for name in related)
    assert related == sorted(set(related))

    analysis = AudioAnalysisResult(bpm=142.0, key="A minor", confidence=0.94)
    context = build_metadata_context(artist_names, analysis, lastfm_api_key=api_key)

    assert context.artists == artist_names
    assert context.bpm == 142.0
    assert context.key == "A minor"
    assert "Kendrick Lamar" in context.keywords
    assert "A minor" not in context.keywords
    assert "142 bpm" not in context.keywords
    assert context.summary.startswith("Kendrick Lamar")
