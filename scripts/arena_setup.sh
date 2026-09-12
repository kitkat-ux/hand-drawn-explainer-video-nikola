#!/usr/bin/env bash
# arena_setup.sh — gói khối SETUP của INSTRUCTIONS_FOR_NEW_CHAT.md thành script idempotent.
# Mỗi bước tự kiểm tra "đã đạt chưa": đạt thì bỏ qua, chưa đạt thì cài.
# Nhánh chính dùng sudo khi có; nhánh dự phòng KHÔNG sudo:
#   ffmpeg   -> ~/.local/bin/ffmpeg
#   fonts    -> ~/.fonts
#   fontconfig -> ~/.config/fontconfig/fonts.conf
# Kết thúc bằng scripts/stroke_story_preflight.py và in rõ "passed true/false".
# Cách chạy: bash scripts/arena_setup.sh        (đặt INSTALL_NOTO_CJK=1 để cài thêm Noto CJK)
set -uo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO"

log()  { printf '\n== %s\n' "$*"; }
skip() { printf '   SKIP (đã đạt): %s\n' "$*"; }

# ── 0. sudo capability ──
SUDO=0
if command -v sudo >/dev/null 2>&1 && sudo -n true >/dev/null 2>&1; then SUDO=1; fi
log "sudo khả dụng: $SUDO (0 => dùng nhánh user-local, không sudo)"

# ── 1. capability report ──
log "setup_check.py (báo cáo năng lực hiện tại)"
python3 scripts/setup_check.py || log "setup_check.py trả lỗi khác 0 (tiếp tục, các bước dưới tự vá)"

# ── 2. venv backend (PyAV/OpenCV/...) ──
VENV_PY="vendor/srt-whiteboard-animation/.venv/bin/python"
if [ -x "$VENV_PY" ]; then
  skip "venv backend ($VENV_PY)"
else
  log "tạo venv backend qua prepare_env.py"
  python3 vendor/srt-whiteboard-animation/scripts/prepare_env.py
fi

# ── 3. ffmpeg ──
if command -v ffmpeg >/dev/null 2>&1; then
  skip "ffmpeg ($(command -v ffmpeg))"
else
  log "cài ffmpeg qua imageio-ffmpeg"
  python3 -m pip install --target /tmp/ffmod imageio-ffmpeg
  FF="$(python3 -c "import sys;sys.path.insert(0,'/tmp/ffmod');import imageio_ffmpeg;print(imageio_ffmpeg.get_ffmpeg_exe())")"
  if [ "$SUDO" = 1 ]; then
    sudo cp "$FF" /usr/local/bin/ffmpeg
    sudo chmod +x /usr/local/bin/ffmpeg
  else
    mkdir -p "$HOME/.local/bin"
    cp "$FF" "$HOME/.local/bin/ffmpeg"
    chmod +x "$HOME/.local/bin/ffmpeg"
    log "KHONG sudo: ffmpeg đặt tại ~/.local/bin/ffmpeg — thêm dòng sau vào ~/.bashrc nếu PATH chưa có:"
    log "  export PATH=\"\$HOME/.local/bin:\$PATH\""
  fi
fi
export PATH="$HOME/.local/bin:$PATH"   # đảm bảo nhánh user-local nhìn thấy ffmpeg ở các bước sau
command -v ffmpeg >/dev/null 2>&1 || { log "LỖI: vẫn không thấy ffmpeg trong PATH"; }

# ── 4. Font Be Vietnam Pro (+ Noto CJK tùy chọn) ──
if command -v fc-list >/dev/null 2>&1 && fc-list 2>/dev/null | grep -qi "Be Vietnam Pro"; then
  skip "font Be Vietnam Pro (fc-list)"
else
  log "tải + cài font Be Vietnam Pro"
  curl -sL -o /tmp/bvp.tar.gz https://codeload.github.com/bettergui/BeVietnamPro/tar.gz/refs/heads/main
  tar xzf /tmp/bvp.tar.gz -C /tmp
  if [ "$SUDO" = 1 ]; then
    sudo mkdir -p /usr/local/share/fonts/bevietnampro
    sudo cp /tmp/BeVietnamPro-main/fonts/ttf/BeVietnamPro-{Regular,Medium,SemiBold,Bold,Italic}.ttf /usr/local/share/fonts/bevietnampro/
  else
    mkdir -p "$HOME/.fonts"
    cp /tmp/BeVietnamPro-main/fonts/ttf/BeVietnamPro-{Regular,Medium,SemiBold,Bold,Italic}.ttf "$HOME/.fonts/"
  fi
  command -v fc-cache >/dev/null 2>&1 && fc-cache -f >/dev/null 2>&1 || log "không có fc-cache, bỏ qua cache refresh"
fi

if [ "${INSTALL_NOTO_CJK:-0}" = 1 ]; then
  if command -v fc-list >/dev/null 2>&1 && fc-list 2>/dev/null | grep -qi "Noto Sans CJK"; then
    skip "font Noto CJK (fc-list)"
  else
    log "tải + cài Noto CJK (tùy chọn, cho case chữ Trung cũ)"
    curl -sL -o /tmp/notocjk.tar.gz https://github.com/notofonts/noto-cjk/raw/main/Sans/OTF/SimplifiedChinese/NotoSansCJKsc-Regular.otf || true
    if [ "$SUDO" = 1 ]; then
      sudo mkdir -p /usr/local/share/fonts/notocjk
      sudo cp /tmp/notocjk.tar.gz /usr/local/share/fonts/notocjk/ 2>/dev/null || true
    else
      mkdir -p "$HOME/.fonts"
      cp /tmp/notocjk.tar.gz "$HOME/.fonts/" 2>/dev/null || true
    fi
  fi
else
  skip "Noto CJK (tùy chọn — đặt INSTALL_NOTO_CJK=1 nếu cần)"
fi

# ── 5. fontconfig alias (Be Vietnam Pro + Noto CJK cho sans-serif) ──
FC_MARKER="<family>Be Vietnam Pro</family>"
write_fontconfig() {
  cat > "$1" <<'EOF'
<?xml version="1.0"?>
<!DOCTYPE fontconfig SYSTEM "fonts.dtd">
<fontconfig>
  <alias><family>Microsoft YaHei</family><prefer><family>Noto Sans CJK SC</family></prefer></alias>
  <alias><family>sans-serif</family><prefer><family>Be Vietnam Pro</family><family>Noto Sans CJK SC</family></prefer></alias>
</fontconfig>
EOF
}
if [ "$SUDO" = 1 ]; then
  FC_TARGET=/etc/fonts/fonts.conf
else
  FC_TARGET="$HOME/.config/fontconfig/fonts.conf"
fi
if [ -f "$FC_TARGET" ] && grep -q "$FC_MARKER" "$FC_TARGET"; then
  skip "fontconfig alias tại $FC_TARGET"
else
  log "ghi fontconfig alias vào $FC_TARGET"
  if [ "$SUDO" = 1 ]; then
    write_fontconfig /tmp/fonts.conf.new
    sudo tee /etc/fonts/fonts.conf >/dev/null < /tmp/fonts.conf.new
    rm -f /tmp/fonts.conf.new
  else
    mkdir -p "$HOME/.config/fontconfig"
    write_fontconfig "$FC_TARGET"
  fi
fi

# ── 6. prelight bắt buộc cuối cùng ──
log "stroke_story_preflight.py"
python3 scripts/stroke_story_preflight.py --report /tmp/preflight.json
PF_EXIT=$?
PASSED="$(python3 -c "import json;print('true' if json.load(open('/tmp/preflight.json')).get('passed') else 'false')" 2>/dev/null || echo false)"
echo "────────────────────────────────────────"
echo "PREFLIGHT passed: $PASSED"
echo "────────────────────────────────────────"
[ "$PASSED" = "true" ] && exit 0 || exit "$PF_EXIT"
