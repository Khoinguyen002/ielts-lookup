#!/usr/bin/env bash
# install.sh — Setup IELTS Lookup trên Ubuntu/GNOME
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=== IELTS Lookup Installer ==="
echo ""

# 1. Dependencies
echo "[1/4] Cài dependencies..."
sudo apt-get install -y \
    python3-gi python3-gi-cairo gir1.2-gtk-4.0 \
    python3-dotenv \
    xdotool wl-clipboard \
    ffmpeg 2>/dev/null || true

# 2. .env
echo ""
echo "[2/4] Cấu hình API key..."
if [ ! -f "$DIR/.env" ]; then
    read -rp "Nhập OpenRouter API key: " apikey
    echo "OPENROUTER_API_KEY=$apikey" > "$DIR/.env"
    echo "  → Đã tạo .env"
else
    echo "  → .env đã tồn tại, bỏ qua"
fi

# 3. GNOME keyboard shortcuts
echo ""
echo "[3/4] Tạo GNOME keyboard shortcuts..."

SCHEME="org.gnome.settings-daemon.plugins.media-keys"
CUSTOM_BASE="$SCHEME.custom-keybinding"
CUSTOM_PATH="/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings"

add_shortcut() {
    local name="$1" cmd="$2" binding="$3"
    local slug
    slug=$(echo "$name" | tr '[:upper:] ' '[:lower:]-')
    local path="$CUSTOM_PATH/$slug/"

    gsettings set "$CUSTOM_BASE:$path" name    "$name"
    gsettings set "$CUSTOM_BASE:$path" command "$cmd"
    gsettings set "$CUSTOM_BASE:$path" binding "$binding"

    echo "$path"
}

PATH_SEL=$(add_shortcut "IELTS Lookup Selection" \
    "python3 $DIR/main.py --selection" "<Alt>s")
PATH_OCR=$(add_shortcut "IELTS Lookup OCR" \
    "python3 $DIR/main.py --ocr"       "<Alt>a")

EXISTING=$(gsettings get $SCHEME custom-keybindings 2>/dev/null || echo "@as []")
EXISTING_CLEAN=$(echo "$EXISTING" | tr -d "[] '" | tr ',' '\n' | grep -v "^$\|ielts-lookup" || true)

NEW_LIST="['$PATH_SEL', '$PATH_OCR'"
while IFS= read -r p; do
    [ -n "$p" ] && NEW_LIST="$NEW_LIST, '$p'"
done <<< "$EXISTING_CLEAN"
NEW_LIST="$NEW_LIST]"

gsettings set $SCHEME custom-keybindings "$NEW_LIST"
echo "  → Alt+S: lookup selection"
echo "  → Alt+A: OCR screenshot"

# 4. Done
echo ""
echo "[4/4] Xong!"
echo ""
echo "  Cách dùng:"
echo "    Bôi đen từ/đoạn văn → Alt+S"
echo "    Screenshot OCR      → Alt+A"
echo ""
echo "  Hoặc chạy thủ công:"
echo "    python3 $DIR/main.py --selection"
echo "    python3 $DIR/main.py --ocr"
