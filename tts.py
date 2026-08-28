"""tts.py — Google TTS pronunciation via ffplay"""
import urllib.request, urllib.parse, subprocess, threading, os, tempfile

def speak(word: str, lang: str = "en-GB", speed: float = 0.9):
    """Play pronunciation of word in background thread."""
    threading.Thread(target=_play, args=(word, lang, speed), daemon=True).start()

def _play(word: str, lang: str, speed: float):
    params = urllib.parse.urlencode({
        "ie": "UTF-8", "q": word.strip(),
        "tl": lang, "client": "tw-ob",
        "ttsspeed": str(speed),
    })
    url = f"https://translate.google.com/translate_tts?{params}"
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
    })
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            audio = resp.read()
        # Write to temp file rồi play
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            f.write(audio)
            tmp = f.name
        subprocess.run(
            ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", tmp],
            timeout=15,
        )
    except Exception:
        pass
    finally:
        try: os.unlink(tmp)
        except: pass
