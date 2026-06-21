# wizard-cli

**A hardware-accelerated, keyboard-first publishing workstation for turning deep beat archives into finished SEO-optimized uploads.**

Move through your massive library of cooks, hear each track immediately, seek without leaving the keyboard, commit the right song, and pair it with the desired visual.

The metadata generator, FFmpeg renderer, and eventual YouTube uploader are one pipeline attached to that browsing experience. The goal is to preserve creative momentum from rediscovering a beat through packaging and publishing it.

## Intended Workflow

The interface is organized around four user actions:

1. **Song** - browse, preview, seek, and commit an mp3.
2. **Cover** - browse and commit still or animated (gif) artwork.
3. **Description** - enter artists and descriptors, generate metadata, adjust seeds, or regenerate a new variation.
4. **Review** - validate the assembled job, render the MP4 with accelerated FFmpeg (currently macOS only), review it, and publish.

## Current Status

Working today:

- Stage-based Textual browser for beat and cover libraries
- Four-stage keyboard navigation with a stage-aware preview pane
- Automatic Google Drive for Desktop discovery on macOS
- Immediate beat preview through a persistent `mpv` process
- Keyboard seeking, pause, mute, sorting, and quick navigation
- Independent beat and cover selection
- UI description draft generation from artists, descriptors, and optional title
- Headless metadata generation, description compilation, and FFmpeg rendering
- Last.fm-assisted similar-artist and descriptor discovery
- YouTube-shaped keyword generation within a 500-character budget

Still being built:

- Review, validation, render progress, and cancellation
- Rendered-video approval
- YouTube OAuth, tags, and upload

## macOS System Dependencies

Install the external command-line tools with Homebrew:

```bash
brew install mpv ffmpeg chafa
```

- `mpv` provides fast audio preview and seeking.
- `ffmpeg` renders the selected song and cover into a YouTube-ready MP4.
- `chafa` renders cover images and GIF still frames inside the terminal preview pane.

Verify the tools are available:

```bash
mpv --version
ffmpeg -version
chafa --version
```

## Controls

| Key | Action |
| --- | --- |
| `Up` / `Down` | Browse files and preview highlighted beats |
| `Left` / `Right` | Seek backward or forward 5 seconds |
| `Shift+Left` / `Shift+Right` | Seek backward or forward 10 seconds |
| `Space` | Play or pause |
| `m` | Mute or unmute |
| `p` | Restart the highlighted preview |
| `s` | Cycle sorting mode |
| `Ctrl+Up` / `Ctrl+Down` | Jump to the top or bottom |
| `Enter` | Commit the selected beat or cover; committed covers open a large preview |
| `Enter` on stage 3 fields | Move to the next description field |
| `Enter` on Generate | Generate or regenerate the description draft |
| `Escape` | Return from the large cover preview to the browser |
| `1` / `2` / `3` / `4` | Switch between Song, Cover, Description, and Review |
| `q` | Quit |

## Media Libraries

Default locations:

- Windows: `G:/My Drive/studio/cooks` and `G:/My Drive/studio/covers`
- macOS: auto-detected under `~/Library/CloudStorage/GoogleDrive-*/My Drive/studio`
- Other platforms: `~/Music/wizard-cli/songs` and `~/Music/wizard-cli/covers`

Override either location with CLI arguments:

```bash
wizard-cli \
  --songs-dir "/path/to/beats" \
  --covers-dir "/path/to/covers" \
  ui
```

Or environment variables:

```bash
export WIZARDCLI_SONGS_DIR="/path/to/beats"
export WIZARDCLI_COVERS_DIR="/path/to/covers"
```

For Google Drive libraries, marking the folders **Available offline** avoids a download delay on the first preview.

## Headless Pipeline

The current end-to-end local pipeline is available through `run`:

```bash
wizard-cli run \
  --beat "beat.mp3" \
  --cover "cover.png" \
  --artists "Lil Uzi Vert, Playboi Carti" \
  --descriptors "ambient, rage, dnb, beat switch" \
  --title "Beat title" \
  --body "Description body"
```

This resolves the media files, generates metadata, compiles `template.md`, and renders a 2560x1440 MP4 into `artifacts/`.

The `--publish` flag is reserved for YouTube publishing, which is not wired yet.

## Metadata Generation

- User-provided artists and descriptors are always included.
- The first two artists also produce a combined modifier such as `Lil Uzi Vert x Playboi Carti`.
- A configured Last.fm API key can add sampled similar artists and top tags.
- Phrases include variants such as `{seed} type beat`, `free {seed} beat`, and `{seed} instrumental`.
- Artist and descriptor combinations are generated in both orders.
- BPM and key remain separate template fields rather than SEO keywords.
- Keywords are deduplicated and packed into a maximum of 30 phrases and 500 characters.

## Project Layout

- `src/wizardcli/ui.py` - Textual application and interaction state
- `src/wizardcli/browser.py` - media browsing and sorting
- `src/wizardcli/audio.py` - persistent `mpv` playback controller
- `src/wizardcli/pipeline.py` - analysis, metadata, description, and FFmpeg orchestration
- `src/wizardcli/metadata.py` - Last.fm enrichment and keyword generation
- `src/wizardcli/publisher.py` - future YouTube publishing
- `tests/` - unit and integration tests
