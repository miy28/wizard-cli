from __future__ import annotations

# Keep these mirrored with wizardcli.tcss until Textual/Rich inline styles can
# read TCSS variables directly.
WIZARD_ACCENT = "#ff358d"
WIZARD_STATUS_FG = "#ecf4fe"
WIZARD_READY = "#22c55e"
WIZARD_MUTED = "#b7bbc2"
WIZARD_PLACEHOLDER = "#686a6f"
WIZARD_ERROR = "#f87171"

STYLE_ACCENT_BOLD = f"bold {WIZARD_ACCENT}"
STYLE_STATUS = WIZARD_STATUS_FG
STYLE_READY = WIZARD_READY
STYLE_READY_BOLD = f"bold {WIZARD_READY}"
STYLE_MUTED = WIZARD_MUTED
STYLE_ERROR_BOLD = f"bold {WIZARD_ERROR}"
