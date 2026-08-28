"""api.py — stream plain text, dùng OpenRouter native fallback"""
import threading, urllib.request, json as _json
from gi.repository import GLib
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
import config

def _stream(sys_prompt, user_text, on_chunk, on_done, on_error):
    threading.Thread(target=_do,
        args=(sys_prompt, user_text, on_chunk, on_done, on_error),
        daemon=True).start()

def _do(sys_prompt, user_text, on_chunk, on_done, on_error):
    payload = {
        # OpenRouter native fallback — thử từng model theo thứ tự, tự động khi 429/5xx
        "models": config.MODELS,
        "route":  "fallback",
        "stream": True,
        "temperature": config.TEMPERATURE,
        "max_tokens":  config.MAX_TOKENS,
        "reasoning":   {"effort": "none"},
        "messages": [
            {"role": "system", "content": sys_prompt},
            {"role": "user",   "content": user_text},
        ],
    }
    req = urllib.request.Request(
        config.API_URL,
        data=_json.dumps(payload).encode(),
        headers={"Authorization": f"Bearer {config.API_KEY}",
                 "Content-Type": "application/json"},
    )
    full = ""; buf = ""; in_think = False; used_model = ""
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            for raw in resp:
                line = raw.decode().strip()
                if not line.startswith("data:"): continue
                data = line[5:].strip()
                if data == "[DONE]": break
                buf += data
                try:
                    obj = _json.loads(buf); buf = ""
                    # Lấy model thực tế OpenRouter dùng (có thể là fallback)
                    if not used_model:
                        used_model = obj.get("model", "")
                    chunk = obj["choices"][0]["delta"].get("content", "") or ""
                    if chunk:
                        if "<think>" in chunk:
                            in_think = True
                        if in_think:
                            if "</think>" in chunk:
                                in_think = False
                                chunk = chunk.split("</think>", 1)[-1]
                            else:
                                continue
                    if chunk:
                        full += chunk
                        GLib.idle_add(on_chunk, chunk)
                except _json.JSONDecodeError:
                    pass
        GLib.idle_add(on_done, full, used_model)
    except Exception as e:
        GLib.idle_add(on_error, str(e))

def stream_word(text, on_chunk, on_done, on_error):
    _stream(config.WORD_SYSTEM_PROMPT,
            config.WORD_USER_TEMPLATE.format(text=text),
            on_chunk, on_done, on_error)

def stream_paragraph(text, on_chunk, on_done, on_error):
    _stream(config.PARAGRAPH_SYSTEM_PROMPT,
            config.PARAGRAPH_USER_TEMPLATE.format(text=text),
            on_chunk, on_done, on_error)
