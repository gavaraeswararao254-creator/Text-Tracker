"""Small local browser toolkit shared by all ten student projects."""
import html
import json
import os
import secrets
from decimal import Decimal, InvalidOperation
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs


def esc(value):
    return html.escape(str(value), quote=True)


def heading(text):
    return '<h2>' + esc(text) + '</h2>'


def note(text):
    return '<p>' + esc(text) + '</p>'


def table(headers, rows):
    cells = ''.join('<th>' + esc(x) + '</th>' for x in headers)
    body = ''.join('<tr>' + ''.join('<td>' + esc(x) + '</td>'
                   for x in row) + '</tr>' for row in rows)
    if not body:
        body = '<tr><td colspan="' + str(len(headers)) + '">No records</td></tr>'
    return '<div class="scroll"><table><tr>' + cells + '</tr>' + body + '</table></div>'


def form(action, fields, button):
    # A field is (name, label, kind, default). Select defaults are lists.
    out = '<form method="post"><input type="hidden" name="_csrf" value="{TOKEN}">'
    out += '<input type="hidden" name="action" value="' + esc(action) + '">'
    for name, label, kind, value in fields:
        out += '<label>' + esc(label)
        if kind in ['textarea', 'textarea_optional']:
            required = ' required' if kind == 'textarea' else ''
            out += '<textarea name="' + esc(name) + '"' + required + '>' + esc(value) + '</textarea>'
        elif kind == 'select':
            out += '<select name="' + esc(name) + '">'
            out += ''.join('<option>' + esc(v) + '</option>' for v in value)
            out += '</select>'
        else:
            out += '<input required type="' + esc(kind) + '" name="' + esc(name)
            out += '" value="' + esc(value) + '">'
        out += '</label>'
    return out + '<button>' + esc(button) + '</button></form>'


class Store:
    def __init__(self, path, default):
        self.path = Path(path)
        self.data = json.loads(self.path.read_text(encoding='utf-8')) if self.path.exists() else default

    def save(self):
        temp = self.path.with_suffix('.tmp')
        temp.write_text(json.dumps(self.data, indent=2), encoding='utf-8')
        temp.replace(self.path)


def money(text):
    try:
        value = Decimal(str(text))
        if not value.is_finite() or value <= 0:
            raise ValueError('Amount must be positive.')
        if value != value.quantize(Decimal('0.01')):
            raise ValueError('Use at most two decimal places.')
        return int(value * 100)
    except InvalidOperation:
        raise ValueError('Enter a valid amount such as 125.50.')


def rupees(paise):
    return f'Rs {paise / 100:.2f}'


def run(title, view, handle):
    token = secrets.token_urlsafe(24)
    port = int(os.environ.get('PORT', '8000'))

    class Handler(BaseHTTPRequestHandler):
        def send_page(self, extra=''):
            body = '<!doctype html><html><meta charset="utf-8">'
            body += '<meta name="viewport" content="width=device-width,initial-scale=1">'
            body += '<title>' + esc(title) + '</title><style>'
            body += 'body{font:16px system-ui;background:#eef2f6;margin:0;color:#182638}'
            body += 'main{max-width:1000px;margin:24px auto;padding:24px;background:white;border-radius:12px}'
            body += 'h1{font-size:28px}h2{font-size:21px;margin-top:30px}'
            body += 'form{padding:16px;border:1px solid #cbd5e1;border-radius:8px;margin:12px 0}'
            body += 'label{display:block;margin:10px 0}input,select,textarea{display:block;box-sizing:border-box;'
            body += 'width:100%;padding:9px;font:inherit;border:1px solid #94a3b8;border-radius:5px}'
            body += 'textarea{min-height:110px}button{background:#164e83;color:white;border:0;'
            body += 'padding:10px 18px;border-radius:5px;font:inherit;cursor:pointer}'
            body += 'table{border-collapse:collapse;width:100%}td,th{border:1px solid #cbd5e1;'
            body += 'padding:9px;text-align:left;white-space:pre-wrap}th{background:#e2e8f0}'
            body += '.scroll{overflow:auto}pre{white-space:pre-wrap}a{color:#164e83}'
            body += '</style><body><main><h1>' + esc(title) + '</h1>'
            body += note('DAA Project assignment | Local learning app')
            body += extra + view() + '</main></body></html>'
            body = body.replace('{TOKEN}', token).encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path != '/':
                self.send_error(404)
                return
            self.send_page()

        def do_POST(self):
            try:
                if self.path != '/':
                    raise ValueError('Unknown page.')
                length = int(self.headers.get('Content-Length', '0'))
                if length < 1 or length > 1_000_000:
                    raise ValueError('Request is empty or too large.')
                raw = self.rfile.read(length).decode('utf-8')
                data = {k: v[0] for k, v in parse_qs(raw, keep_blank_values=True).items()}
                if not secrets.compare_digest(data.get('_csrf', ''), token):
                    raise ValueError('Refresh the page and try again.')
                self.send_page(handle(data) or note('Saved successfully.'))
            except (ValueError, KeyError, OSError) as error:
                self.send_page(note('Please check: ' + str(error)))

        def log_message(self, *args):
            pass

    server = HTTPServer(('127.0.0.1', port), Handler)
    print(f'{title}: open http://127.0.0.1:{port}')
    print('Keep this terminal open. Press Ctrl+C to stop.')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
