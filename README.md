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

## Layout

- `src/wizardcli/` - app, CLI, analysis, pipeline, and publishing code

## Next step

Install dependencies and run `wizard-cli --help` once the first implementation slice is in place.
