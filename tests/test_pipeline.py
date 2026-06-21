from __future__ import annotations

from pathlib import Path

from wizardcli import pipeline
from wizardcli.config import default_config
from wizardcli.models import DescriptionInputs, MetadataContext, RenderResult


def test_generate_description_draft_auto_titles_and_skips_render(
    monkeypatch,
    tmp_path: Path,
) -> None:
    beat = tmp_path / "beat.mp3"
    beat.write_text("x", encoding="utf-8")
    template = tmp_path / "template.md"
    template.write_text("{title}\n\n{body}\n\n{keywords}", encoding="utf-8")
    render_calls = []

    def fake_metadata(
        artist_names,
        analysis,
        lastfm_api_key=None,
        lastfm_session_key=None,
        descriptors=None,
    ) -> MetadataContext:
        assert analysis is None
        return MetadataContext(
            keywords=["Carti type beat", "rage type beat"],
            artists=artist_names,
            descriptors=descriptors or [],
            summary="Carti type beat, rage type beat",
        )

    monkeypatch.setattr(pipeline, "build_metadata_context", fake_metadata)
    monkeypatch.setattr(pipeline, "render_video", lambda *args: render_calls.append(args))

    draft = pipeline.generate_description_draft(
        default_config(root_dir=tmp_path),
        beat=beat,
        inputs=DescriptionInputs(
            artist_names=[" Playboi Carti ", "playboi carti"],
            descriptors=[" rage ", "ambient"],
        ),
    )

    assert draft.title == "Playboi Carti type beat"
    assert draft.inputs.artist_names == ["Playboi Carti"]
    assert draft.inputs.descriptors == ["rage", "ambient"]
    assert draft.analysis is None
    assert "Carti type beat" in draft.description
    assert render_calls == []


def test_run_pipeline_uses_draft_then_renders(monkeypatch, tmp_path: Path) -> None:
    beat = tmp_path / "beat.mp3"
    cover = tmp_path / "cover.png"
    beat.write_text("x", encoding="utf-8")
    cover.write_text("x", encoding="utf-8")
    template = tmp_path / "template.md"
    template.write_text("{title}\n{body}\n{keywords}", encoding="utf-8")

    metadata = MetadataContext(
        keywords=["Uzi type beat"],
        artists=["Lil Uzi Vert"],
        descriptors=[],
        summary="Uzi type beat",
    )

    monkeypatch.setattr(
        pipeline,
        "build_metadata_context",
        lambda *args, **kwargs: metadata,
    )
    monkeypatch.setattr(
        pipeline,
        "render_video",
        lambda config, selection, analysis: RenderResult(
            output_path=tmp_path / "out.mp4",
            video_codec="fake",
            audio_source=selection.beat,
            cover_source=selection.cover,
        ),
    )

    result = pipeline.run_pipeline(
        default_config(root_dir=tmp_path),
        beat=beat,
        cover=cover,
        artist_names=["Lil Uzi Vert"],
        descriptors=[],
        title="",
        body="Generated body",
    )

    assert result.description.startswith("Lil Uzi Vert type beat")
    assert result.analysis is None
    assert result.rendered_video == tmp_path / "out.mp4"
