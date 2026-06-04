from __future__ import annotations

import os

import pytest

from wizardcli import metadata
from wizardcli.config import get_lastfm_api_key


@pytest.mark.integration
@pytest.mark.skipif(not get_lastfm_api_key(), reason="Set a Last.fm API key to run the live top-tags experiment")
def test_live_top_tags_experiment() -> None:
    api_key = get_lastfm_api_key()
    assert api_key is not None

    artist_name = os.getenv("WIZARDCLI_TOP_TAGS_ARTIST", "Playboi Carti")
    limit = int(os.getenv("WIZARDCLI_TOP_TAGS_LIMIT", "10"))

    tags = metadata.fetch_top_tags(api_key, artist_name, limit=limit)

    print(f"Artist: {artist_name}")
    print(f"Top tags ({len(tags)}):")
    for index, tag in enumerate(tags, start=1):
        print(f"{index}. {tag}")
