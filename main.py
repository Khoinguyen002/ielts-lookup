#!/usr/bin/env python3
import sys, os, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config, api, popup

def kill_existing():
    try:
        r = subprocess.run(["pgrep","-f","ielts-lookup/main.py"],
                           capture_output=True,text=True)
        for pid in r.stdout.strip().split("\n"):
            if pid and pid != str(os.getpid()):
                subprocess.run(["kill",pid],capture_output=True)
    except: pass

def run_selection():
    from clipboard import get_selected_text
    text = get_selected_text()
    if not text:
        subprocess.run(["notify-send","-t","2000","IELTS Lookup","Không có text được chọn"],
                       capture_output=True); return
    if len(text.split()) <= config.WORD_THRESHOLD:
        popup.show_word_popup(text[:50],
            lambda oc,od,oe: api.stream_word(text,oc,od,oe))
    else:
        popup.show_paragraph_popup(text[:60],
            lambda oc,od,oe: api.stream_paragraph(text,oc,od,oe))

def run_ocr():
    from ocr import capture_and_ocr
    text = capture_and_ocr()
    if not text:
        subprocess.run(["notify-send","-t","2000","IELTS Lookup","OCR không nhận diện được chữ"],
                       capture_output=True); return
    if len(text.split()) <= config.WORD_THRESHOLD:
        popup.show_word_popup(text[:50],
            lambda oc,od,oe: api.stream_word(text,oc,od,oe))
    else:
        popup.show_paragraph_popup(text[:60],
            lambda oc,od,oe: api.stream_paragraph(text,oc,od,oe))

if __name__ == "__main__":
    kill_existing()
    mode = sys.argv[1] if len(sys.argv)>1 else "--selection"
    run_ocr() if mode=="--ocr" else run_selection()
