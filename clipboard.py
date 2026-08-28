"""clipboard.py — Đọc selected text qua wl-paste"""
import subprocess

def get_selected_text() -> str | None:
    """Đọc text user đang bôi đen (PRIMARY selection)."""
    for args in (
        ["wl-paste", "--primary", "--no-newline"],
        ["wl-paste", "--no-newline"],
    ):
        try:
            result = subprocess.run(args, capture_output=True, text=True, timeout=2)
            text = result.stdout.strip()
            if text:
                return text
        except Exception:
            continue
    return None
