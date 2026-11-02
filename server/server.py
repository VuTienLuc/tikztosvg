#!/usr/bin/env python3
"""Máy chủ biên dịch TikZ → SVG tự chứa (latex + dvisvgm).

Chỉ dùng thư viện chuẩn Python 3.9+. Chạy:  python3 server.py
Biến môi trường:
  PORT          cổng lắng nghe (mặc định 8765)
  HOST          địa chỉ lắng nghe (mặc định 127.0.0.1; dùng 0.0.0.0 trong Docker/cloud)
  API_TOKEN     nếu đặt, mọi yêu cầu /compile phải gửi header X-Token khớp giá trị này
  ALLOW_ORIGIN  giá trị Access-Control-Allow-Origin (mặc định *)
  MAX_JOBS      số hình biên dịch song song (mặc định 2)
  TIMEOUT       giây tối đa cho mỗi bước latex/dvisvgm (mặc định 40)
"""
import hashlib, json, os, re, shutil, subprocess, sys, tempfile, threading, time
from collections import OrderedDict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = int(os.environ.get('PORT', '8765'))
HOST = os.environ.get('HOST', '127.0.0.1')
TOKEN = os.environ.get('API_TOKEN', '')
ORIGIN = os.environ.get('ALLOW_ORIGIN', '*')
TIMEOUT = int(os.environ.get('TIMEOUT', '40'))
MAX_BODY = 400_000
SLOTS = threading.Semaphore(int(os.environ.get('MAX_JOBS', '2')))
CACHE, CACHE_LOCK, CACHE_SIZE = OrderedDict(), threading.Lock(), 500
VERSION = '1.0'

# macOS MacTeX cài vào /Library/TeX/texbin nhưng ứng dụng mở bằng bấm-đúp không thấy PATH đó.
for extra in ('/Library/TeX/texbin', '/usr/local/texlive/bin', '/opt/homebrew/bin', '/usr/local/bin'):
    if os.path.isdir(extra) and extra not in os.environ.get('PATH', ''):
        os.environ['PATH'] = os.environ.get('PATH', '') + os.pathsep + extra

def tool(name):
    path = shutil.which(name)
    if not path:
        sys.exit(f'Không tìm thấy "{name}". Hãy cài TeX Live/MacTeX (có sẵn {name}) rồi chạy lại.')
    return path

LATEX, DVISVGM, KPSEWHICH = tool('latex'), tool('dvisvgm'), tool('kpsewhich')

def has_file(name):
    try:
        return bool(subprocess.run([KPSEWHICH, name], capture_output=True, text=True, timeout=10).stdout.strip())
    except Exception:
        return False

VIETNAMESE = has_file('t5enc.def')
DVISVGM_VERSION = subprocess.run([DVISVGM, '--version'], capture_output=True, text=True).stdout.strip()
OPTIMIZE = '--optimize' in subprocess.run([DVISVGM, '--help'], capture_output=True, text=True).stdout

# Lệnh có thể đọc/ghi tệp hoặc gọi chương trình ngoài: từ chối thẳng.
FORBIDDEN = re.compile(r'\\(?:input|include|openin|openout|read|write|immediate|special|directlua|'
                       r'catcode|csname|endlinechar|everyeof|scantokens|ShellEscape|pdfshellescape|'
                       r'includegraphics|lstinputlisting|verbatiminput|usepackage|RequirePackage|documentclass)\b')
PKG_NAME = re.compile(r'^[A-Za-z0-9][A-Za-z0-9-]{0,40}$')
PKG_OPTS = re.compile(r'^[A-Za-z0-9=,.\- ]{0,120}$')
BASE_LIBS = 'arrows.meta,calc,patterns,angles,quotes,intersections,positioning,decorations.markings,through'

def strip_comments(text):
    return re.sub(r'(?<!\\)%[^\n]*', '', text)

def build_document(body, preamble, packages):
    for chunk in (body, preamble):
        bad = FORBIDDEN.search(strip_comments(chunk))
        if bad:
            raise ValueError(f'Lệnh {bad.group(0)} không được phép trên máy chủ (đọc/ghi tệp hoặc gọi chương trình ngoài).')
    # Thư viện nạp trong thân tài liệu dễ lỗi: chuyển lên preamble.
    libs = re.findall(r'\\use(?:tikz|pgfplots)library\s*(?:\[[^\]]*\])?\s*\{[^}]*\}', body)
    for lib in libs:
        body = body.replace(lib, '', 1)
    preamble = '\n'.join(libs + [preamble])
    if not re.search(r'\\begin\s*\{(tikzpicture|tikzcd)\}', body):
        raise ValueError('Cần khối \\begin{tikzpicture}…\\end{tikzpicture} (hoặc tikzcd).')
    pkg_lines = []
    for p in packages[:20]:
        name, opts = str(p.get('name', '')), str(p.get('opts', ''))
        if not PKG_NAME.match(name) or not PKG_OPTS.match(opts):
            raise ValueError(f'Tên gói không hợp lệ: {name}')
        if name in ('tikz', 'pgf', 'xcolor', 'amsmath', 'amssymb', 'inputenc', 'fontenc', 'standalone'):
            continue
        if not has_file(name + '.sty'):
            raise ValueError(f'Máy chủ chưa cài gói "{name}". Cài thêm bằng tlmgr install {name}.')
        pkg_lines.append(f'\\usepackage[{opts}]{{{name}}}' if opts else f'\\usepackage{{{name}}}')
    if any(re.match(r'\\usepackage(\[.*\])?\{pgfplots\}', l) for l in pkg_lines):
        pkg_lines.append('\\pgfplotsset{compat=1.18}')
    viet = '\\usepackage[T5]{fontenc}\n' if VIETNAMESE else ''
    return ('\\def\\pgfsysdriver{pgfsys-dvisvgm.def}\n'
            '\\documentclass[border=1pt]{standalone}\n'
            '\\usepackage[utf8]{inputenc}\n' + viet +
            '\\usepackage{amsmath,amssymb}\n\\usepackage{tikz}\n'
            f'\\usetikzlibrary{{{BASE_LIBS}}}\n' + '\n'.join(pkg_lines) + '\n' +
            preamble + '\n\\begin{document}\n' + body + '\n\\end{document}\n')

def tex_error(log):
    lines, out = log.splitlines(), []
    for i, line in enumerate(lines):
        if line.startswith('!'):
            out.append(' '.join(l.strip() for l in lines[i:i + 3] if l.strip()))
        if len(out) >= 4:
            break
    for i, line in enumerate(lines):
        m = re.match(r'l\.(\d+)', line)
        if m:
            out.append('Dòng ' + m.group(1) + ' của tài liệu ghép: ' + line[len(m.group(0)):].strip())
            break
    return '\n'.join(out) or 'LaTeX dừng mà không báo lỗi cụ thể.'

def clean_svg(svg):
    svg = re.sub(r'<\?xml[^>]*\?>', '', svg)
    svg = re.sub(r'<!--.*?-->', '', svg, flags=re.S)
    svg = re.sub(r'<!DOCTYPE[^>]*>', '', svg)
    # style="a:b; c:d" → a="b" c="d" (SVG tự chứa, không phụ thuộc CSS).
    def to_attrs(m):
        out = []
        for part in m.group(2).split(';'):
            if ':' in part:
                k, v = (x.strip() for x in part.split(':', 1))
                if re.fullmatch(r'[a-z-]+', k):
                    out.append(f' {k}="{v.replace(chr(34), "&quot;")}"')
        return ''.join(out)
    svg = re.sub(r'\sstyle=([\'"])(.*?)\1', to_attrs, svg)
    return svg.strip()

def run(cmd, cwd, env):
    return subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True, errors='replace', timeout=TIMEOUT)

def compile_tikz(body, preamble, packages):
    doc = build_document(body, preamble, packages)
    key = hashlib.sha256(doc.encode()).hexdigest()
    with CACHE_LOCK:
        if key in CACHE:
            CACHE.move_to_end(key)
            return CACHE[key], True
    env = dict(os.environ, openin_any='p', openout_any='p', shell_escape='f', TEXMFOUTPUT='')
    with SLOTS, tempfile.TemporaryDirectory(prefix='tikz-') as tmp:
        with open(os.path.join(tmp, 'hinh.tex'), 'w', encoding='utf-8') as f:
            f.write(doc)
        try:
            r = run([LATEX, '-no-shell-escape', '-interaction=nonstopmode', '-halt-on-error', 'hinh.tex'], tmp, env)
        except subprocess.TimeoutExpired:
            raise ValueError(f'LaTeX chạy quá {TIMEOUT} giây (vòng lặp vô hạn hoặc hình quá nặng).')
        log_path = os.path.join(tmp, 'hinh.log')
        log = open(log_path, encoding='utf-8', errors='replace').read() if os.path.exists(log_path) else r.stdout
        if r.returncode != 0 or not os.path.exists(os.path.join(tmp, 'hinh.dvi')):
            raise ValueError(tex_error(log))
        base = [DVISVGM, '--no-fonts=1', '--exact-bbox', '--precision=3', '--stdout', 'hinh.dvi']
        attempts = [base[:1] + ['--optimize'] + base[1:], base] if OPTIMIZE else [base]
        for cmd in attempts:
            try:
                d = run(cmd, tmp, env)
            except subprocess.TimeoutExpired:
                raise ValueError(f'dvisvgm chạy quá {TIMEOUT} giây.')
            if d.returncode == 0 and '<svg' in d.stdout:
                break
        else:
            raise ValueError('dvisvgm không tạo được SVG: ' + d.stderr.strip()[-600:])
    svg = clean_svg(d.stdout)
    with CACHE_LOCK:
        CACHE[key] = svg
        while len(CACHE) > CACHE_SIZE:
            CACHE.popitem(last=False)
    return svg, False

class Handler(BaseHTTPRequestHandler):
    server_version = 'TikzSvgServer/' + VERSION

    def cors(self):
        self.send_header('Access-Control-Allow-Origin', ORIGIN)
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, X-Token')
        self.send_header('Access-Control-Allow-Private-Network', 'true')
        self.send_header('Access-Control-Max-Age', '600')

    def reply(self, code, data):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(code)
        self.cors()
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.cors()
        self.end_headers()

    def do_GET(self):
        if self.path.split('?')[0] in ('/', '/health'):
            self.reply(200, {'ok': True, 'engine': 'latex + dvisvgm', 'version': VERSION, 'dvisvgm': DVISVGM_VERSION,
                             'vietnamese': VIETNAMESE, 'token': bool(TOKEN),
                             'packages': {p: has_file(p + '.sty') for p in ('pgfplots', 'tkz-euclide', 'tikz-cd', 'tkz-tab', 'circuitikz')}})
        else:
            self.reply(404, {'error': 'Không có đường dẫn này.'})

    def do_POST(self):
        if self.path.split('?')[0] != '/compile':
            return self.reply(404, {'error': 'Không có đường dẫn này.'})
        if TOKEN and self.headers.get('X-Token') != TOKEN:
            return self.reply(401, {'error': 'Sai hoặc thiếu mã truy cập (X-Token).'})
        length = int(self.headers.get('Content-Length') or 0)
        if length <= 0 or length > MAX_BODY:
            return self.reply(413, {'error': 'Dữ liệu rỗng hoặc vượt 400 KB.'})
        try:
            data = json.loads(self.rfile.read(length).decode('utf-8'))
            body, preamble = str(data.get('body', '')), str(data.get('preamble', ''))
            packages = data.get('packages') or []
            if not isinstance(packages, list):
                raise ValueError('packages phải là mảng.')
            t = time.time()
            svg, cached = compile_tikz(body, preamble, packages)
            self.reply(200, {'svg': svg, 'cached': cached, 'ms': int((time.time() - t) * 1000)})
        except (ValueError, json.JSONDecodeError) as e:
            self.reply(422, {'error': str(e)})
        except Exception as e:
            self.reply(500, {'error': 'Lỗi máy chủ: ' + str(e)[:300]})

    def log_message(self, fmt, *args):
        sys.stderr.write('[%s] %s\n' % (time.strftime('%H:%M:%S'), fmt % args))

if __name__ == '__main__':
    print(f'TikZ → SVG server {VERSION}  ·  http://{HOST}:{PORT}')
    print(f'  {DVISVGM_VERSION}  ·  tiếng Việt (T5): {"có" if VIETNAMESE else "không"}  ·  token: {"bật" if TOKEN else "tắt"}')
    print('  Nhấn Ctrl+C để dừng.')
    try:
        ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
    except KeyboardInterrupt:
        print('\nĐã dừng máy chủ.')
