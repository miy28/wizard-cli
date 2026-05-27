from pathlib import Path

from wizardcli.compiler import compile_description, load_template
from wizardcli.models import MetadataContext


def test_compile_description(tmp_path: Path) -> None:
    template = tmp_path / "template.md"
    template.write_text("{title}\n{artists}\n{keywords}\n", encoding="utf-8")
    metadata = MetadataContext(keywords=["Carti", "Uzi"], artists=["Carti", "Uzi"], summary="Carti, Uzi")

    output = compile_description(load_template(template), metadata, title="Beat", body="Body")

    assert "Beat" in output
    assert "Carti" in output
    assert "Uzi" in output
