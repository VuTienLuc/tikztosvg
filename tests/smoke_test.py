#!/usr/bin/env python3
"""Chạy thử máy chủ với hình thật. Thoát mã 1 nếu có ca nào sai.

Dùng:  python3 tests/smoke_test.py
"""
import json, os, re, subprocess, sys, time, urllib.error, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORT = int(os.environ.get('SMOKE_PORT', '8799'))
BASE = f'http://127.0.0.1:{PORT}'

OK_CASES = {
    'tam-giac-tieng-viet': {'body': r'\begin{tikzpicture}\draw (0,0)--(4,0)--(1.5,3)--cycle;'
                                    r'\node[above] at (1.5,3){Đỉnh $C$};\end{tikzpicture}'},
    'pgfplots': {'body': r'\begin{tikzpicture}\begin{axis}[axis lines=middle]\addplot[domain=-2:2]{x^2-1};'
                         r'\end{axis}\end{tikzpicture}', 'packages': [{'name': 'pgfplots'}]},
    'tkz-euclide': {'body': r'\begin{tikzpicture}\tkzDefPoints{0/0/A,4/0/B,1/3/C}\tkzDrawPolygon(A,B,C)'
                            r'\tkzLabelPoints(A,B)\end{tikzpicture}', 'packages': [{'name': 'tkz-euclide'}]},
    'tikz-cd': {'body': r'\begin{tikzcd}A \arrow[r,"f"] & B\end{tikzcd}', 'packages': [{'name': 'tikz-cd'}]},
    'to-mau': {'body': r'\begin{tikzpicture}\shade[left color=red,right color=blue] (0,0) rectangle (3,1);'
                       r'\end{tikzpicture}'},
    'thu-vien-trong-than': {'body': r'\usetikzlibrary{arrows.meta}\begin{tikzpicture}\draw[-Stealth] (0,0)--(1,0);'
                                    r'\end{tikzpicture}'},
}
ERROR_CASES = {
    'macro-chua-dinh-nghia': ({'body': r'\begin{tikzpicture}\draw (0,0)--(\chuaCo,1);\end{tikzpicture}'}, 'Undefined control sequence'),
    'chan-input': ({'body': r'\input{/etc/passwd}\begin{tikzpicture}\end{tikzpicture}'}, 'không được phép'),
    'chan-goi-la': ({'body': r'\begin{tikzpicture}\end{tikzpicture}', 'packages': [{'name': 'goi-khong-ton-tai'}]}, 'chưa cài gói'),
    'thieu-hinh': ({'body': r'xin chao'}, 'tikzpicture'),
}
# SVG phải tự chứa: không chữ dạng <text>, không CSS, không tài nguyên ngoài.
BANNED = [r'<text', r'<style', r'\sstyle=', r'https?://(?!www\.w3\.org)', r'<script', r'<image', r'@import']

def post(payload):
    req = urllib.request.Request(BASE + '/compile', json.dumps(payload).encode(), {'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            return r.status, json.load(r)
    except urllib.error.HTTPError as e:
        return e.code, json.load(e)

def main():
    env = dict(os.environ, PORT=str(PORT), HOST='127.0.0.1')
    proc = subprocess.Popen([sys.executable, os.path.join(ROOT, 'server', 'server.py')], env=env)
    failures = []
    try:
        for _ in range(60):
            try:
                health = json.load(urllib.request.urlopen(BASE + '/health', timeout=2))
                break
            except Exception:
                time.sleep(0.5)
        else:
            sys.exit('Máy chủ không khởi động được.')
        print('health:', json.dumps(health, ensure_ascii=False))
        if not health.get('vietnamese'):
            failures.append('health: thiếu hỗ trợ tiếng Việt (vntex)')

        for name, payload in OK_CASES.items():
            code, data = post(payload)
            svg = data.get('svg', '')
            bad = [p for p in BANNED if re.search(p, svg)]
            ok = code == 200 and svg.startswith('<svg') and 'viewBox' in svg and not bad
            print(f"{'✓' if ok else '✗'} {name}: HTTP {code}, {len(svg)} byte, {data.get('ms')} ms", bad or data.get('error', ''))
            if not ok:
                failures.append(name)

        code, data = post(OK_CASES['to-mau'])
        if not data.get('cached'):
            failures.append('bộ nhớ đệm không hoạt động')
        print(f"{'✓' if data.get('cached') else '✗'} bộ nhớ đệm")

        for name, (payload, expect) in ERROR_CASES.items():
            code, data = post(payload)
            ok = code == 422 and expect in data.get('error', '')
            print(f"{'✓' if ok else '✗'} {name}: HTTP {code} · {data.get('error', '')[:90]!r}")
            if not ok:
                failures.append(name)
    finally:
        proc.terminate()
        proc.wait(timeout=10)
    if failures:
        sys.exit('THẤT BẠI: ' + ', '.join(failures))
    print('Tất cả ca thử đều đạt.')

if __name__ == '__main__':
    main()
