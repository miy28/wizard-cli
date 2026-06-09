this was totally vibe coded

# wizard-cli

Hybrid Textual/CLI pipeline for selecting beats and covers from Google Drive-mounted folders, generating metadata, rendering video with ffmpeg, and publishing to YouTube.

## Defaults

- Beats: `G:/My Drive/studio/cooks`
- Covers: `G:/My Drive/studio/covers`

You can override those roots with `--songs-dir`, `--covers-dir`, or the matching `WIZARDCLI_SONGS_DIR` / `WIZARDCLI_COVERS_DIR` environment variables.

## Audio preview

- `wizardcli` now uses `mpv` for live preview playback.
- Install `mpv` and make sure it is on `PATH`.
- Move through beats to preview immediately, then use left/right to seek while a beat is active.

## Metadata and tag generation

Headless runs can generate YouTube-shaped keyword phrases from artists and descriptors:

```powershell
wizard-cli run --beat beat.wav --cover cover.png --artists "Lil Uzi Vert, Playboi Carti" --descriptors "ambient, rage, dnb, beat switch"
```

Current flow:

- User-provided artists are guaranteed modifiers.
- If two or more artists are provided, wizard-cli also adds one combined modifier from the first two artists, such as `Lil Uzi Vert x Playboi Carti`.
- User-provided descriptors are guaranteed modifiers. Descriptors can be genres, moods, structures, or loose search terms.
- If a Last.fm API key is configured, `artist.getSimilar` fills a sampled similar-artist bucket.
- If a Last.fm API key is configured, `artist.getTopTags` fills a sampled descriptor bucket.
- The generator creates single-seed phrases such as `{seed} type beat`, `{seed} type beat 2026`, `free {seed} type beat`, `free {seed} beat`, `{seed} beat`, and `{seed} instrumental`.
- The generator also creates artist/descriptor combinations in both orders, such as `ambient Izaya Tiji type beat` and `Izaya Tiji ambient type beat`.
- Keywords are SEO/tag phrases only. Audio analysis fields like BPM and key stay separate and are available through `{bpm}` and `{key}` in the description template.
- Keywords are deduped and packed into a 500-character, 30-keyword budget before being rendered into the description template.

Not wired yet:

- UI-mode controls for entering artists/descriptors and invoking this generator.
- Persistent candidate pools for regenerating without requerying Last.fm.
- YouTube autocomplete expansion for RapidTags-style search phrases.
- YouTube competitor tag extraction.
- A dedicated YouTube upload `tags` field. Generated keywords currently render through the description template.

## Layout

- `src/wizardcli/` - app, CLI, analysis, pipeline, and publishing code

## Next step

Install dependencies and run `wizard-cli --help` once the first implementation slice is in place.
