#!/usr/bin/env python3
"""Tách các khối <script> của Studio và kiểm tra cú pháp bằng node --check."""
import os, re, subprocess, sys, tempfile

path = sys.argv[1] if len(sys.argv) > 1 else 'index.html'
html = open(path, encoding='utf-8').read()
blocks = re.findall(r'<script>\n(.*?)\n</script>', html, flags=re.S)
if not blocks:
    sys.exit('Không tìm thấy khối <script>.')
with tempfile.TemporaryDirectory() as tmp:
    for i, code in enumerate(blocks):
        f = os.path.join(tmp, f'block{i}.js')
        open(f, 'w', encoding='utf-8').write(code)
        r = subprocess.run(['node', '--check', f], capture_output=True, text=True)
        if r.returncode:
            sys.exit(f'Lỗi cú pháp ở khối script {i}:\n{r.stderr}')
        print(f'✓ khối script {i}: {len(code)} ký tự')
for needed in ('id="engine"', 'serverCompile', 'normalizeTikz', 'makeSelfContainedSVG'):
    if needed not in html:
        sys.exit(f'Thiếu thành phần: {needed}')
print('Studio hợp lệ.')
