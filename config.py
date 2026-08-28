"""config.py"""
import os
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
API_URL = "https://openrouter.ai/api/v1/chat/completions"
MODELS      = [
    "qwen/qwen3.7-flash",       # primary — fast, cheap
    "minimax/minimax-m3:free",  # fallback free — khi qwen bị 429
]
MAX_TOKENS  = 4000
TEMPERATURE = 0.1
WORD_THRESHOLD = 6

WORD_SYSTEM_PROMPT = """\
You are an IELTS vocabulary engine. Output ONLY in this exact format with no extra lines, no brackets, no markdown:

§PHONETIC
/IPA transcription British English/ | /IPA transcription American English/

§MEANING B2
Vietnamese definition here.

§COLLOCATIONS
collocation one | Vietnamese meaning one
collocation two | Vietnamese meaning two
collocation three | Vietnamese meaning three

§NUANCE
Nuance and pitfall explanation in Vietnamese here.

§EXAMPLE
One IELTS Band 8.5 academic sentence here.\
"""
WORD_USER_TEMPLATE = "{text}"

PARAGRAPH_SYSTEM_PROMPT = """\
You are an IELTS reading assistant. Output ONLY in this exact format with no extra lines, no brackets, no markdown:

§TRANSLATION
Natural Vietnamese translation of the full paragraph here.

§HIGHLIGHTS
word or collocation | Vietnamese meaning | C1
word or collocation | Vietnamese meaning | B2
word or collocation | Vietnamese meaning | C1

Rules: 4-6 highlights max, B2+ only, prefer multi-word collocations, words must appear exactly as in original.\
"""
PARAGRAPH_USER_TEMPLATE = "{text}"

POPUP_WORD_WIDTH = 420
POPUP_PARA_WIDTH = 540
POPUP_MAX_HEIGHT = 480
