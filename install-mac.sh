#!/bin/bash
# Cài máy chủ TikZ → SVG trên macOS; máy chủ tự bật mỗi khi đăng nhập máy.
# Chạy trong Terminal:
#   bash -c "$(curl -fsSL https://tikztosvg.vercel.app/install-mac.sh)"
# Chạy lại lệnh này bất cứ lúc nào để cập nhật lên bản mới nhất.
set -euo pipefail

BASE="${TIKZ_BASE:-https://tikztosvg.vercel.app}"
PORT="${TIKZ_PORT:-8765}"
LABEL="vn.vutienluc.tikz-svg-server"
APP_DIR="$HOME/Library/Application Support/TikzSvgServer"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
LOG="$HOME/Library/Logs/tikz-svg-server.log"
export PATH="/Library/TeX/texbin:/opt/homebrew/bin:/usr/local/bin:$PATH"

say()  { printf '\n\033[1;32m▸ %s\033[0m\n' "$*"; }
fail() { printf '\n\033[1;31m✗ %s\033[0m\n' "$*" >&2; exit 1; }

[ "$(uname -s)" = "Darwin" ] || fail "Bộ cài này dành cho macOS. Máy khác hãy dùng Docker (xem README)."

say "1/5 Kiểm tra Python 3"
command -v python3 >/dev/null || fail "Chưa có python3. Chạy: xcode-select --install rồi cài lại."
PY="$(python3 -c 'import sys; print(sys.executable)')"
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' || fail "Cần Python 3.9 trở lên ($PY)."
echo "   $PY"

say "2/5 Kiểm tra TeX (latex + dvisvgm)"
if ! command -v latex >/dev/null; then
  command -v brew >/dev/null || fail "Chưa có TeX và Homebrew. Cài MacTeX từ https://tug.org/mactex/ rồi chạy lại lệnh này."
  echo "   Chưa có TeX: cài BasicTeX (~300 MB). macOS sẽ hỏi mật khẩu máy."
  brew install --cask basictex
  export PATH="/Library/TeX/texbin:$PATH"
fi
echo "   $(latex --version | head -1)"

say "3/5 Kiểm tra các gói TeX cho hình Toán"
MISSING=()
command -v dvisvgm >/dev/null || MISSING+=(dvisvgm)
for f in standalone.cls pgfplots.sty tkz-euclide.sty tikz-cd.sty tkz-tab.sty t5enc.def; do
  if ! kpsewhich "$f" >/dev/null 2>&1; then
    case "$f" in t5enc.def) MISSING+=(vntex);; *) MISSING+=("${f%.*}");; esac
  fi
done
if [ ${#MISSING[@]} -gt 0 ]; then
  echo "   Cần cài thêm: ${MISSING[*]} (macOS sẽ hỏi mật khẩu máy)"
  sudo tlmgr update --self
  sudo tlmgr install "${MISSING[@]}"
else
  echo "   Đã đủ gói."
fi

say "4/5 Tải máy chủ"
mkdir -p "$APP_DIR" "$(dirname "$PLIST")" "$(dirname "$LOG")"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd || echo /nonexistent)"
if [ -f "$SCRIPT_DIR/server/server.py" ]; then
  cp "$SCRIPT_DIR/server/server.py" "$APP_DIR/server.py.new"          # chạy từ thư mục repo
else
  curl -fsSL "$BASE/server/server.py" -o "$APP_DIR/server.py.new" || fail "Không tải được $BASE/server/server.py"
fi
"$PY" -m py_compile "$APP_DIR/server.py.new" || fail "Tệp server.py tải về bị hỏng."
mv "$APP_DIR/server.py.new" "$APP_DIR/server.py"
rm -rf "$APP_DIR/__pycache__"

say "5/5 Đăng ký tự chạy khi mở máy"
cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key>
  <array><string>$PY</string><string>$APP_DIR/server.py</string></array>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key><string>/Library/TeX/texbin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
    <key>PORT</key><string>$PORT</string>
    <key>PYTHONUNBUFFERED</key><string>1</string>
  </dict>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>ThrottleInterval</key><integer>30</integer>
  <key>StandardOutPath</key><string>$LOG</string>
  <key>StandardErrorPath</key><string>$LOG</string>
</dict>
</plist>
EOF
plutil -lint "$PLIST" >/dev/null || fail "Tệp cấu hình LaunchAgent không hợp lệ."
launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
sleep 1
launchctl bootstrap "gui/$(id -u)" "$PLIST"

for _ in $(seq 1 30); do
  if curl -fs "http://127.0.0.1:$PORT/health" >/dev/null 2>&1; then
    say "Xong! Máy chủ đang chạy tại http://127.0.0.1:$PORT và sẽ tự bật mỗi khi mở máy."
    echo "   Mở Studio: $BASE/"
    echo "   Nhật ký:   $LOG"
    echo "   Gỡ cài:    bash -c \"\$(curl -fsSL $BASE/uninstall-mac.sh)\""
    exit 0
  fi
  sleep 1
done
tail -n 20 "$LOG" 2>/dev/null || true
fail "Máy chủ chưa phản hồi sau 30 giây. Xem nhật ký ở trên ($LOG). Nếu báo cổng $PORT đang bận, hãy tắt máy chủ đang chạy tay rồi cài lại."
