#!/bin/bash
# Gỡ máy chủ TikZ → SVG khỏi macOS (giữ nguyên TeX đã cài).
set -u
LABEL="vn.vutienluc.tikz-svg-server"
launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
rm -f "$HOME/Library/LaunchAgents/$LABEL.plist"
rm -rf "$HOME/Library/Application Support/TikzSvgServer"
rm -f "$HOME/Library/Logs/tikz-svg-server.log"
echo "Đã gỡ máy chủ TikZ → SVG. TeX (MacTeX/BasicTeX) vẫn giữ nguyên."
