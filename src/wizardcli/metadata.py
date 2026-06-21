from __future__ import annotations

import random
import requests

from .models import AudioAnalysisResult, MetadataContext, ModifierPool


LASTFM_ENDPOINT = "https://ws.audioscrobbler.com/2.0/"
CURRENT_TAG_YEAR = 2026

SEED_PATTERNS = [
    "{seed} type beat",
    "{seed} type beat {year}",
    "free {seed} type beat",
    "free {seed} beat",
    "{seed} beat",
    "{seed} instrumental",
]

ARTIST_DESCRIPTOR_PATTERNS = [
    "{artist} {descriptor} type beat",
    "{descriptor} {artist} type beat",
    "{artist} {descriptor} type beat {year}",
    "{descriptor} {artist} type beat {year}",
    "free {artist} {descriptor} type beat",
]


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


def fetch_top_tags(api_key: str, artist_name: str, limit: int = 10) -> list[str]:
    if not api_key or not artist_name:
        return []

    params = {
        "method": "artist.getTopTags",
        "artist": artist_name,
        "api_key": api_key,
        "format": "json",
        "limit": limit,
    }
    response = requests.get(LASTFM_ENDPOINT, params=params, timeout=15)
    response.raise_for_status()
    payload = response.json()
    tags = payload.get("toptags", {}).get("tag", [])
    results: list[str] = []
    for item in tags:
        name = item.get("name") if isinstance(item, dict) else None
        if name:
            results.append(name)
    return results


def build_modifier_pool(
    artist_names: list[str],
    descriptors: list[str] | None = None,
    lastfm_api_key: str | None = None,
    similar_artist_limit: int = 10,
    top_tag_limit: int = 10,
) -> ModifierPool:
    guaranteed_artists = _dedupe_terms([*artist_names, _combined_artist_modifier(artist_names)])
    guaranteed_descriptors = _dedupe_terms(descriptors or [])

    if not lastfm_api_key:
        return ModifierPool(
            guaranteed_artists=guaranteed_artists,
            guaranteed_descriptors=guaranteed_descriptors,
        )

    similar_artists = fetch_similar_artists(
        lastfm_api_key,
        artist_names,
        limit=similar_artist_limit,
    )
    discovered_descriptors: list[str] = []
    for artist in artist_names:
        discovered_descriptors.extend(fetch_top_tags(lastfm_api_key, artist, limit=top_tag_limit))

    return ModifierPool(
        guaranteed_artists=guaranteed_artists,
        guaranteed_descriptors=guaranteed_descriptors,
        similar_artists=_dedupe_terms(similar_artists),
        discovered_descriptors=_dedupe_terms(discovered_descriptors),
    )


def sample_modifier_pool(
    pool: ModifierPool,
    rng: random.Random | None = None,
    similar_artist_count: int = 3,
    discovered_descriptor_count: int = 5,
) -> tuple[list[str], list[str]]:
    randomizer = rng or random.Random()
    sampled_artists = _sample_terms(pool.similar_artists, similar_artist_count, randomizer)
    sampled_descriptors = _sample_terms(
        pool.discovered_descriptors,
        discovered_descriptor_count,
        randomizer,
    )
    artists = _dedupe_terms([*pool.guaranteed_artists, *sampled_artists])
    descriptors = _dedupe_terms([*pool.guaranteed_descriptors, *sampled_descriptors])
    return artists, descriptors


def generate_keyword_phrases(
    artist_modifiers: list[str],
    descriptor_modifiers: list[str],
    analysis: AudioAnalysisResult,
    max_keywords: int = 30,
    max_characters: int = 500,
    year: int = CURRENT_TAG_YEAR,
) -> list[str]:
    candidates: list[str] = []

    for artist in artist_modifiers:
        candidates.append(_format_seed_pattern(SEED_PATTERNS[0], artist, year))

    for descriptor in descriptor_modifiers:
        candidates.append(_format_seed_pattern(SEED_PATTERNS[0], descriptor, year))
        candidates.append(_format_seed_pattern("free {seed} beat", descriptor, year))

    primary_artists = artist_modifiers[:2]
    primary_descriptors = descriptor_modifiers[:4]
    for artist in primary_artists:
        for descriptor in primary_descriptors:
            candidates.append(f"{artist} {descriptor} type beat")
            candidates.append(f"{descriptor} {artist} type beat")

    seed_modifiers = _dedupe_terms([*artist_modifiers, *descriptor_modifiers])
    for seed in seed_modifiers:
        candidates.extend(
            _format_seed_pattern(pattern, seed, year)
            for pattern in SEED_PATTERNS
            if pattern not in {"{seed} type beat", "free {seed} beat"}
        )

    for artist in primary_artists:
        for descriptor in primary_descriptors:
            candidates.extend(
                pattern.format(artist=artist, descriptor=descriptor, year=year)
                for pattern in ARTIST_DESCRIPTOR_PATTERNS
            )

    return _pack_keywords(_dedupe_terms(candidates), max_keywords=max_keywords, max_characters=max_characters)


def build_metadata_context(
    artist_names: list[str],
    analysis: AudioAnalysisResult | None = None,
    lastfm_api_key: str | None = None,
    lastfm_session_key: str | None = None,
    descriptors: list[str] | None = None,
    rng: random.Random | None = None,
) -> MetadataContext:
    # The session key is accepted and forwarded for future authenticated calls.
    pool = build_modifier_pool(
        artist_names=artist_names,
        descriptors=descriptors,
        lastfm_api_key=lastfm_api_key,
    )
    artist_modifiers, descriptor_modifiers = sample_modifier_pool(pool, rng=rng)
    keywords = generate_keyword_phrases(artist_modifiers, descriptor_modifiers, analysis)
    summary = ", ".join(keywords[:12])
    return MetadataContext(
        keywords=keywords,
        artists=artist_names,
        descriptors=_dedupe_terms(descriptors or []),
        summary=summary,
        bpm=analysis.bpm if analysis is not None else None,
        key=analysis.key if analysis is not None else None,
        lastfm_enabled=bool(lastfm_api_key),
        lastfm_similar_artists=pool.similar_artists,
        lastfm_discovered_descriptors=pool.discovered_descriptors,
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


def _dedupe_terms(values: list[str]) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = " ".join(value.strip().split()) if value else ""
        if not text:
            continue
        lowered = text.lower()
        if lowered not in seen:
            seen.add(lowered)
            cleaned.append(text)
    return cleaned


def _combined_artist_modifier(artist_names: list[str]) -> str:
    artists = _dedupe_terms(artist_names)
    if len(artists) < 2:
        return ""
    return " x ".join(artists[:2])


def _format_seed_pattern(pattern: str, seed: str, year: int) -> str:
    return pattern.format(seed=seed, year=year)


def _sample_terms(values: list[str], count: int, rng: random.Random) -> list[str]:
    if count <= 0:
        return []
    values = _dedupe_terms(values)
    if len(values) <= count:
        return values
    return rng.sample(values, count)


def _pack_keywords(values: list[str], max_keywords: int, max_characters: int) -> list[str]:
    packed: list[str] = []
    current_length = 0
    for value in values:
        separator_length = 2 if packed else 0
        next_length = current_length + separator_length + len(value)
        if len(packed) >= max_keywords or next_length > max_characters:
            break
        packed.append(value)
        current_length = next_length
    return packed
