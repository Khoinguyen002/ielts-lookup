"""popup.py — GTK4 TextView, stream plain text with live tag coloring."""
import gi
gi.require_version("Gtk","4.0")
gi.require_version("Gdk","4.0")
from gi.repository import Gtk, Gdk, GLib, Pango
import subprocess, threading, sys, os, re
sys.path.insert(0, os.path.dirname(__file__))
import config
import tts as _tts

# ── Globals ───────────────────────────────────────────────────────────
_sub_windows: list = []   # keep refs to avoid GC
_opening_sub: list = [False]  # True trong khi _open_sub chạy
_main_app    = None       # Gtk.Application of main popup
_css_done    = False

SECTION_RE = re.compile(
    r"§(PHONETIC|MEANING|COLLOCATIONS|NUANCE|EXAMPLE|TRANSLATION|HIGHLIGHTS)"
    r"(?:\s+(A1|A2|B1|B2|C1|C2))?"
)

# ── CSS ───────────────────────────────────────────────────────────────
CSS = b"""
window { background:#1e1e2e; border-radius:12px; border:1px solid #313244; }
.hdr   { background:#181825; padding:7px 12px; border-radius:12px 12px 0 0;
          border-bottom:1px solid #313244; }
.wlbl  { color:#cdd6f4; font-size:13px; font-weight:bold; }
.ibtn  { background:none; border:none; color:#6c7086; padding:2px 5px;
          border-radius:4px; font-size:12px; min-width:0; min-height:0; }
.ibtn:hover { background:#313244; color:#cdd6f4; }
.lkbar { background:#181825; border-top:1px solid #313244;
          padding:4px 10px; border-radius:0 0 12px 12px; }
.lkbtn { background:#89b4fa; color:#1e1e2e; font-size:11px; font-weight:bold;
          border:none; border-radius:4px; padding:2px 10px;
          min-height:0; min-width:0; }
.lkbtn:hover { background:#74c7ec; }
textview      { background:transparent; padding:8px 12px 10px; }
textview text { background:transparent; }
"""

def _css():
    global _css_done
    if _css_done: return
    p = Gtk.CssProvider(); p.load_from_data(CSS)
    Gtk.StyleContext.add_provider_for_display(
        Gdk.Display.get_default(), p,
        Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
    _css_done = True

# ── Tags ──────────────────────────────────────────────────────────────
def _tags(buf):
    def t(n, **k): return buf.create_tag(n, **k)
    return {
        "sec": t("sec", foreground="#89b4fa", weight=Pango.Weight.BOLD,
                  size_points=10, pixels_above_lines=8, pixels_below_lines=1),
        "ipa": t("ipa", foreground="#cba6f7", size_points=12,
                  pixels_above_lines=1, pixels_below_lines=2),
        "txt": t("txt", foreground="#cdd6f4", size_points=11),
        "ph":  t("ph",  foreground="#f5c2e7", weight=Pango.Weight.BOLD, size_points=11),
        "mn":  t("mn",  foreground="#bac2de", size_points=11),
        "nu":  t("nu",  foreground="#fab387", size_points=11),
        "ex":  t("ex",  foreground="#a6e3a1", size_points=11, style=Pango.Style.ITALIC),
        "cf":  t("cf",  foreground="#89b4fa", size_points=10, weight=Pango.Weight.BOLD),
        "dim": t("dim", foreground="#45475a", size_points=11),
        "mdl": t("mdl", foreground="#45475a", size_points=9, pixels_above_lines=6),
    }

def _ins(buf, text, *tgs):
    buf.insert_with_tags(buf.get_end_iter(), text, *tgs)

# ── Header ────────────────────────────────────────────────────────────
def _hdr(root, text, width, close_fn, extra_btns=None):
    box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
    box.add_css_class("hdr")
    lbl = Gtk.Label(label=f'🔍 "{text}"')
    lbl.add_css_class("wlbl")
    lbl.set_ellipsize(Pango.EllipsizeMode.END)
    lbl.set_max_width_chars(int(width / 11))
    lbl.set_hexpand(True); lbl.set_xalign(0)
    box.append(lbl)
    for icon, fn in (extra_btns or []):
        b = Gtk.Button(label=icon); b.add_css_class("ibtn")
        b.connect("clicked", lambda _, f=fn: f())
        box.append(b)
    b = Gtk.Button(label="✕"); b.add_css_class("ibtn")
    b.connect("clicked", lambda _: close_fn())
    box.append(b)
    root.append(box)

# ── Focus / ESC ───────────────────────────────────────────────────────
def _focus_esc(win, guard_fn=None):
    """Close popup on focus-loss. Workspace switch = no surface focused → keep."""
    fc = Gtk.EventControllerFocus()
    def _on_leave(_):
        if _opening_sub[0] or (guard_fn and guard_fn()):
            return
        def _get_focused():
            try: return Gdk.Display.get_default().get_focused_surface()
            except: return None
        def _stage1():
            if _opening_sub[0] or (guard_fn and guard_fn()):
                return False
            focused = _get_focused()
            if focused is not None:
                win.close(); return False   # app khác focused → đóng
            # None = workspace switch OR desktop → đợi thêm
            GLib.timeout_add(700, _stage2)
            return False
        def _stage2():
            if _opening_sub[0] or (guard_fn and guard_fn()):
                return False
            # Workspace switch: user quay lại → win.is_active() = True
            # Desktop click: win không bao giờ active lại → đóng
            if not win.is_active():
                win.close()
            return False
        GLib.timeout_add(200, _stage1)
    fc.connect("leave", _on_leave)
    win.add_controller(fc)
    kc = Gtk.EventControllerKey()
    kc.connect("key-pressed",
               lambda c, k, *_: win.close() if k == Gdk.KEY_Escape else None)
    win.add_controller(kc)

# ── StreamRenderer ────────────────────────────────────────────────────
class StreamRenderer:
    SECTION_LABELS = {
        "PHONETIC":     None,
        "MEANING":      "MEANING",
        "COLLOCATIONS": "TOP COLLOCATIONS",
        "NUANCE":       "⚠  NUANCE & PITFALL",
        "EXAMPLE":      "📝  IELTS BAND 8.5 EXAMPLE",
        "TRANSLATION":  "TRANSLATION",
        "HIGHLIGHTS":   "HIGHLIGHTED WORDS",
    }
    SECTION_TAG = {
        "PHONETIC":     "ipa",
        "MEANING":      "txt",
        "COLLOCATIONS": None,
        "NUANCE":       "nu",
        "EXAMPLE":      "ex",
        "TRANSLATION":  "txt",
        "HIGHLIGHTS":   None,
    }
    BUFFERED_SECTIONS = {"COLLOCATIONS", "HIGHLIGHTS", "PHONETIC"}
    TICK_MS        = 16
    CHARS_PER_TICK = 4

    def __init__(self, buf, tgs, skip_sections=None):
        self.buf     = buf
        self.tgs     = tgs
        self.section = None
        self._skip   = skip_sections or set()
        self._pending = ""
        self._queue   = []
        self._timer   = None

    # ── Public ────────────────────────────────────────────────────────
    def feed(self, chunk: str):
        self._queue.extend(chunk)
        self._ensure_timer()

    def flush(self):
        if self._queue:
            self._process("".join(self._queue)); self._queue = []
            if self._timer:
                GLib.source_remove(self._timer); self._timer = None
        if self._pending:
            self._emit_line(self._pending); self._pending = ""

    # ── Timer ─────────────────────────────────────────────────────────
    def _ensure_timer(self):
        if self._timer is None:
            self._timer = GLib.timeout_add(self.TICK_MS, self._tick)

    def _tick(self):
        if not self._queue:
            self._timer = None; return False
        chars = self._queue[:self.CHARS_PER_TICK]
        self._queue = self._queue[self.CHARS_PER_TICK:]
        self._process("".join(chars))
        return True

    # ── Line assembly ─────────────────────────────────────────────────
    def _process(self, text: str):
        self._pending += text
        while "\n" in self._pending:
            line, self._pending = self._pending.split("\n", 1)
            self._emit_line(line + "\n")
        # Partial emit for non-buffered sections
        if self._pending and self.section and \
                not self._pending.startswith("§") and \
                self.section not in self.BUFFERED_SECTIONS:
            tag = self.SECTION_TAG.get(self.section, "txt")
            if tag:
                _ins(self.buf, self._pending, self.tgs[tag])
                self._pending = ""

    def _emit_line(self, line: str):
        stripped = line.rstrip("\n")

        # Section header
        m = SECTION_RE.match(stripped.strip())
        if m:
            self.section = m.group(1)
            if self.section in self._skip:
                return   # bỏ qua section bị skip
            cefr  = m.group(2) or ""
            label = self.SECTION_LABELS[self.section]
            if label is None:
                return   # PHONETIC: no header label
            # Đảm bảo section header luôn ở dòng mới
            si = self.buf.get_start_iter(); ei = self.buf.get_end_iter()
            cur = self.buf.get_text(si, ei, False)
            if cur and not cur.endswith("\n"):
                _ins(self.buf, "\n", self.tgs["txt"])
            header = label + (f"  [{cefr}]" if cefr else "") + "\n"
            _ins(self.buf, header, self.tgs["sec"])
            return

        # Ignore unrecognized §XXX lines
        if stripped.strip().startswith("§"):
            return

        if not stripped.strip() or not self.section:
            return  # bỏ qua empty lines

        if self.section in self._skip:
            return  # bỏ qua content của section bị skip

        tag_name = self.SECTION_TAG.get(self.section, "txt")

        if tag_name is None:
            parts = [p.strip() for p in stripped.split("|")]
            if self.section == "PHONETIC":
                for i, p in enumerate(parts):
                    if p:
                        flag = "🇬🇧" if i == 0 else "🇺🇸"
                        _ins(self.buf, f"{flag} {p}  ", self.tgs["ipa"])
                _ins(self.buf, "\n", self.tgs["txt"])
            elif len(parts) >= 2:
                _ins(self.buf, "  • ", self.tgs["mn"])
                _ins(self.buf, parts[0], self.tgs["ph"])
                _ins(self.buf, "  —  " + parts[1], self.tgs["mn"])
                _ins(self.buf, "\n", self.tgs["txt"])
                return
                if len(parts) >= 3:
                    _ins(self.buf, "  [" + parts[2] + "]", self.tgs["cf"])
                _ins(self.buf, "\n", self.tgs["txt"])
        else:
            _ins(self.buf, stripped + "\n", self.tgs[tag_name])

# ── BasePopup ─────────────────────────────────────────────────────────
class BasePopup(Gtk.ApplicationWindow):
    def __init__(self, app, text, width, extra_btns=None):
        super().__init__(application=app)
        self.input_text = text
        _css()
        self.set_decorated(False); self.set_resizable(False)
        self.set_default_size(width, -1)
        self.root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_child(self.root)
        _hdr(self.root, text, width, self.close, extra_btns=extra_btns)

        sc = Gtk.ScrolledWindow()
        sc.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        sc.set_max_content_height(config.POPUP_MAX_HEIGHT)
        sc.set_propagate_natural_height(True)
        self.root.append(sc)

        self._tv = Gtk.TextView()
        self._tv.set_editable(False); self._tv.set_cursor_visible(False)
        self._tv.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self._buf = self._tv.get_buffer()
        sc.set_child(self._tv)

        self._tgs = _tags(self._buf)
        self._renderer = StreamRenderer(self._buf, self._tgs,
                                        skip_sections=getattr(self, "_skip_sections", None))
        _ins(self._buf, "⏳  Analyzing…", self._tgs["dim"])

        # Lookup bar
        self._lkbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self._lkbar.add_css_class("lkbar")
        self._lkbar.set_visible(False)
        lkbtn = Gtk.Button(label="🔍  Lookup")
        lkbtn.add_css_class("lkbtn")
        lkbtn.connect("clicked", self._on_lookup)
        self._lkbar.append(lkbtn)
        self.root.append(self._lkbar)
        self._buf.connect("notify::has-selection", self._on_sel)

        _focus_esc(self, guard_fn=lambda: bool(_sub_windows))

    def _on_sel(self, buf, *_):
        self._lkbar.set_visible(buf.get_has_selection())

    def _on_lookup(self, _):
        if not self._buf.get_has_selection(): return
        s, e = self._buf.get_selection_bounds()
        text = self._buf.get_text(s, e, False).strip()
        self._buf.select_range(self._buf.get_start_iter(), self._buf.get_start_iter())
        if text:
            _open_sub(text)

    def on_chunk(self, chunk: str):
        if self._buf.get_char_count() > 0:
            s = self._buf.get_start_iter(); e = self._buf.get_end_iter()
            if self._buf.get_text(s, e, False).startswith("⏳"):
                self._buf.delete(s, e)
        self._renderer.feed(chunk)
        return False

    def on_done(self, _full, model=""):
        self._renderer.flush()
        if model:
            short = model.split("/")[-1]
            _ins(self._buf, f"\n─── {short} ───\n", self._tgs["mdl"])
        return False

    def on_error(self, msg):
        self._buf.delete(self._buf.get_start_iter(), self._buf.get_end_iter())
        _ins(self._buf, f"❌ {msg}", self._tgs["nu"]); return False

# ── WordPopup ─────────────────────────────────────────────────────────
class WordPopup(BasePopup):
    def __init__(self, app, text):
        super().__init__(app, text, config.POPUP_WORD_WIDTH,
                         extra_btns=[("🔊", lambda: _tts.speak(text))])

# ── ParagraphPopup ────────────────────────────────────────────────────
class ParagraphPopup(BasePopup):
    def __init__(self, app, text):
        self._skip_sections = {"PHONETIC"}
        super().__init__(app, text, config.POPUP_PARA_WIDTH)

# ── SubWordWindow ─────────────────────────────────────────────────────
class SubWordWindow(Gtk.ApplicationWindow):
    def __init__(self, label: str):
        super().__init__(application=_main_app)
        _css()
        self.set_decorated(False); self.set_resizable(False)
        self.set_default_size(config.POPUP_WORD_WIDTH, -1)

        self.root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_child(self.root)
        _hdr(self.root, label, config.POPUP_WORD_WIDTH, self.close,
             extra_btns=[("🔊", lambda: _tts.speak(label))])

        sc = Gtk.ScrolledWindow()
        sc.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        sc.set_max_content_height(config.POPUP_MAX_HEIGHT)
        sc.set_propagate_natural_height(True)
        self.root.append(sc)

        self._tv = Gtk.TextView()
        self._tv.set_editable(False); self._tv.set_cursor_visible(False)
        self._tv.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self._buf = self._tv.get_buffer()
        sc.set_child(self._tv)

        self._tgs = _tags(self._buf)
        self._renderer = StreamRenderer(self._buf, self._tgs)
        _ins(self._buf, "⏳  Analyzing…", self._tgs["dim"])

        # Lookup bar
        self._lkbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self._lkbar.add_css_class("lkbar")
        self._lkbar.set_visible(False)
        lkbtn = Gtk.Button(label="🔍  Lookup")
        lkbtn.add_css_class("lkbtn")
        lkbtn.connect("clicked", self._on_lookup)
        self._lkbar.append(lkbtn)
        self.root.append(self._lkbar)
        self._buf.connect("notify::has-selection",
                          lambda b, *_: self._lkbar.set_visible(b.get_has_selection()))

        # ESC only — no focus-out close
        kc = Gtk.EventControllerKey()
        kc.connect("key-pressed",
                   lambda c, k, *_: self.close() if k == Gdk.KEY_Escape else None)
        self.add_controller(kc)

    def _on_lookup(self, _):
        if not self._buf.get_has_selection(): return
        s, e = self._buf.get_selection_bounds()
        text = self._buf.get_text(s, e, False).strip()
        self._buf.select_range(self._buf.get_start_iter(), self._buf.get_start_iter())
        if text: _open_sub(text)

    def on_chunk(self, chunk: str):
        if self._buf.get_char_count() > 0:
            s = self._buf.get_start_iter(); e = self._buf.get_end_iter()
            if self._buf.get_text(s, e, False).startswith("⏳"):
                self._buf.delete(s, e)
        self._renderer.feed(chunk); return False

    def on_done(self, _full, model=""):
        self._renderer.flush()
        if model:
            short = model.split("/")[-1]
            _ins(self._buf, f"\n─── {short} ───\n", self._tgs["mdl"])
        return False

    def on_error(self, msg):
        self._buf.delete(self._buf.get_start_iter(), self._buf.get_end_iter())
        _ins(self._buf, f"❌ {msg}", self._tgs["nu"]); return False

# ── Sub-popup launcher ────────────────────────────────────────────────
def _open_sub(text: str):
    import api as _api
    _opening_sub[0] = True          # block focus-leave trong khi tạo sub-window
    try:
        win = SubWordWindow(text[:60])
        _sub_windows.append(win)
    finally:
        _opening_sub[0] = False
    win.connect("destroy", lambda w: _sub_windows.remove(w) if w in _sub_windows else None)
    win.present()
    is_para = len(text.split()) > config.WORD_THRESHOLD
    fetch = _api.stream_paragraph if is_para else _api.stream_word
    fetch(text,
          lambda c: (GLib.idle_add(win.on_chunk, c), False)[1],
          lambda f, m="": (GLib.idle_add(win.on_done, f, m), False)[1],
          lambda e: (GLib.idle_add(win.on_error, e), False)[1])

# ── Public ────────────────────────────────────────────────────────────
def show_word_popup(text, fetch_fn):
    global _main_app
    app = Gtk.Application(application_id="com.ielts.lookup.word")
    def on_act(application):
        global _main_app; _main_app = application
        win = WordPopup(application, text); win.present()
        fetch_fn(
            lambda c: (GLib.idle_add(win.on_chunk, c), False)[1],
            lambda f, m="": (GLib.idle_add(win.on_done, f, m), False)[1],
            lambda e: (GLib.idle_add(win.on_error, e), False)[1])
    app.connect("activate", on_act); app.run([])

def show_paragraph_popup(text, fetch_fn):
    global _main_app
    app = Gtk.Application(application_id="com.ielts.lookup.para")
    def on_act(application):
        global _main_app; _main_app = application
        win = ParagraphPopup(application, text); win.present()
        fetch_fn(
            lambda c: (GLib.idle_add(win.on_chunk, c), False)[1],
            lambda f, m="": (GLib.idle_add(win.on_done, f, m), False)[1],
            lambda e: (GLib.idle_add(win.on_error, e), False)[1])
    app.connect("activate", on_act); app.run([])
