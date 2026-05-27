from __future__ import annotations

import requests

from .models import AudioAnalysisResult, MetadataContext


LASTFM_ENDPOINT = "https://ws.audioscrobbler.com/2.0/"


class MetadataError(RuntimeError):
    pass


def fetch_similar_artists(api_key: str, artist_names: list[str], limit: int = 10) -> list[str]:
    if not api_key:
        return []

    related: set[str] = set()
    for artist in artist_names:
        params = {
            "method": "artist.getsimilar",
            "artist": artist,
            "api_key": api_key,
            "format": "json",
            "limit": limit,
        }
        response = requests.get(LASTFM_ENDPOINT, params=params, timeout=15)
        response.raise_for_status()
        payload = response.json()
        for item in payload.get("similarartists", {}).get("artist", []):
            name = item.get("name")
            if name:
                related.add(name)
    return sorted(related)


def build_metadata_context(
    artist_names: list[str],
    analysis: AudioAnalysisResult,
    lastfm_api_key: str | None = None,
) -> MetadataContext:
    related = fetch_similar_artists(lastfm_api_key or "", artist_names) if lastfm_api_key else []
    keywords = _normalize_keywords([*artist_names, *related, analysis.key, f"{int(round(analysis.bpm))} bpm"])
    summary = ", ".join(keywords[:12])
    return MetadataContext(
        keywords=keywords,
        artists=artist_names,
        summary=summary,
        bpm=analysis.bpm,
        key=analysis.key,
    )


def _normalize_keywords(values: list[str]) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = value.strip()
        if not text:
            continue
        lowered = text.lower()
        for token in ("lil ", "the ", "feat. ", "ft. "):
            if lowered.startswith(token):
                text = text[len(token) :]
                lowered = text.lower()
        if lowered not in seen:
            seen.add(lowered)
            cleaned.append(text)
    return cleaned
