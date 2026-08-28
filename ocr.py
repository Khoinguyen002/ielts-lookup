"""ocr.py — XDG portal screenshot + Tesseract OCR"""
import dbus
import dbus.mainloop.glib
from gi.repository import GLib
import subprocess
import random
import string
import os
from urllib.parse import unquote


def capture_and_ocr() -> str | None:
    """
    Mở GNOME screenshot UI → user chọn vùng → Tesseract OCR → trả về text.
    Return None nếu user hủy hoặc không nhận diện được chữ.
    """
    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    bus = dbus.SessionBus()
    loop = GLib.MainLoop()

    token = "ielts_" + "".join(random.choices(string.ascii_lowercase, k=6))
    uid   = bus.get_unique_name()[1:].replace(".", "_")
    rpath = f"/org/freedesktop/portal/desktop/request/{uid}/{token}"

    result = {"uri": None}

    def on_response(resp, results):
        if resp == 0 and "uri" in results:
            result["uri"] = unquote(str(results["uri"])[7:])  # strip file://
        loop.quit()

    bus.add_signal_receiver(
        on_response,
        signal_name="Response",
        dbus_interface="org.freedesktop.portal.Request",
        path=rpath,
    )

    portal = bus.get_object(
        "org.freedesktop.portal.Desktop",
        "/org/freedesktop/portal/desktop",
    )
    iface = dbus.Interface(portal, "org.freedesktop.portal.Screenshot")
    opts  = dbus.Dictionary({
        "handle_token": dbus.String(token),
        "interactive":  dbus.Boolean(True),
    }, signature="sv")
    iface.Screenshot("", opts)

    GLib.timeout_add_seconds(30, loop.quit)
    loop.run()

    path = result["uri"]
    if not path or not os.path.exists(path):
        return None

    # Tesseract OCR
    proc = subprocess.run(
        ["tesseract", path, "stdout", "-l", "eng+vie", "--psm", "6"],
        capture_output=True, text=True,
    )
    text = " ".join(proc.stdout.split())
    return text if text else None
