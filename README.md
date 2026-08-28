# ielts-lookup

GNOME Wayland popup tool tra từ / dịch đoạn văn nhanh, dùng OpenRouter API.

## Features

- **Alt+S** — Tra từ/đoạn đang bôi chọn (primary selection)
- **Alt+A** — OCR screenshot → dịch (XDG portal)
- Auto-detect: ≤6 từ → Word mode, >6 từ → Paragraph mode
- Typewriter streaming effect
- 🔊 Phát âm (Google TTS + ffplay)
- IPA phonetic (UK + US)
- Lookup bar — bôi text trong popup → 🔍 Lookup để tra thêm
- Sub-popup chain (Lookup trong Lookup)
- Model name hiển thị ở footer
- Auto-close khi focus app khác, giữ khi chuyển workspace

## Models

Primary: `qwen/qwen3.7-flash`
Fallback: `minimax/minimax-m3:free`
Route: OpenRouter native fallback (`"route": "fallback"`)

## Structure

```
main.py       — Entry point, parse args, dispatch word/para popup
config.py     — API key, models, system prompts, thresholds
api.py        — OpenRouter SSE streaming, fallback routing
popup.py      — GTK4 popup UI, StreamRenderer, focus management
clipboard.py  — wl-paste primary selection
tts.py        — Google TTS + ffplay pronunciation
```

## Install

Files live at `~/.local/bin/ielts-lookup/`. GNOME custom keybindings:

| Shortcut | Command |
|---|---|
| Alt+S | `python3 ~/.local/bin/ielts-lookup/main.py --selection` |
| Alt+A | `python3 ~/.local/bin/ielts-lookup/main.py --ocr` |

## Requirements

- Python 3.10+
- `python3-gi` (GTK4 GObject bindings)
- `wl-paste`, `wl-copy` (wl-clipboard)
- `ffplay` (ffmpeg)
- GNOME Shell 45+ / Wayland
