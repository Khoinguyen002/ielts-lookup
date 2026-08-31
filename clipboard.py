"""clipboard.py — Đọc selected text qua wl-paste (Wayland)"""
import subprocess


def clear_primary() -> None:
    """Xóa PRIMARY selection để tránh lưu rác/stale selection sang các lần gọi sau."""
    try:
        subprocess.run(["wl-copy", "--primary", "--clear"], capture_output=True, timeout=1)
    except Exception:
        pass


def get_selected_text() -> str | None:
    """
    Đọc text user đang bôi đen hoặc vừa copy:
    1. Ưu tiên đọc PRIMARY selection (vừa kéo chuột bôi đen trong app native / web thường).
       - Nếu có text: clear PRIMARY ngay sau khi lấy để lần sau không bị dính text cũ.
    2. Nếu PRIMARY rỗng (VD: trong Chrome PDF viewer không bắn PRIMARY ra Wayland):
       - Fallback sang CLIPBOARD selection (user bấm Ctrl+C).
    """
    # 1. Thử PRIMARY selection
    try:
        res = subprocess.run(
            ["wl-paste", "--primary", "--no-newline"],
            capture_output=True,
            text=True,
            timeout=1,
        )
        if res.returncode == 0:
            text = res.stdout.strip()
            if text:
                clear_primary()
                return text
    except Exception:
        pass

    # 2. Fallback sang CLIPBOARD selection (Ctrl+C)
    try:
        res = subprocess.run(
            ["wl-paste", "--no-newline"],
            capture_output=True,
            text=True,
            timeout=1,
        )
        if res.returncode == 0:
            text = res.stdout.strip()
            if text:
                return text
    except Exception:
        pass

    return None

