
"""
Text Comparison and Change Tracker
Render deployment version
Python standard library only.
"""

import os
import csv
import io
import json
import html
import difflib
import threading

from pathlib import Path
from urllib.parse import parse_qs
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from email.parser import BytesParser
from email.policy import default


# ==================================================
# CONFIGURATION
# ==================================================

APP_TITLE = "Text Comparison and Change Tracker"

HOST = "0.0.0.0"
PORT = int(os.environ.get("PORT", "10000"))

MAX_TEXT_SIZE = 1_000_000
MAX_REQUEST_SIZE = 4_000_000

MODES = [
    "Exact",
    "Ignore case and repeated spaces"
]

LABELS = {
    "equal": "Unchanged",
    "replace": "Modified",
    "delete": "Removed",
    "insert": "Added"
}

# Use Render persistent disk path if configured.
# Otherwise use the project directory.

DATA_DIR = Path(
    os.environ.get(
        "DATA_DIR",
        str(Path(__file__).resolve().parent)
    )
)

DATA_DIR.mkdir(parents=True, exist_ok=True)

DATA_FILE = DATA_DIR / "data.json"

DEFAULT_DATA = {
    "old": (
        "The meeting is on Monday.\n"
        "Bring your notebook."
    ),
    "new": (
        "The meeting is on Tuesday.\n"
        "Bring your notebook.\n"
        "Arrive at 10 AM."
    ),
    "changes": []
}

store_lock = threading.Lock()


# ==================================================
# DATA STORAGE
# ==================================================

def load_data():

    if not DATA_FILE.exists():
        return DEFAULT_DATA.copy()

    try:
        with DATA_FILE.open("r", encoding="utf-8") as file:
            data = json.load(file)

        if not isinstance(data, dict):
            return DEFAULT_DATA.copy()

        return {
            "old": data.get("old", ""),
            "new": data.get("new", ""),
            "changes": data.get("changes", [])
        }

    except (OSError, json.JSONDecodeError):
        return DEFAULT_DATA.copy()


def save_data(data):

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    temporary_file = DATA_DIR / "data.tmp"

    with temporary_file.open("w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=4)
        file.flush()
        os.fsync(file.fileno())

    temporary_file.replace(DATA_FILE)


store = load_data()


# ==================================================
# TEXT NORMALIZATION
# ==================================================

def normalize_line(line, mode):

    if mode == "Ignore case and repeated spaces":
        return " ".join(line.lower().split())

    return line


# ==================================================
# COMPARISON ALGORITHM
# ==================================================

def compare(old, new, mode):

    if mode not in MODES:
        raise ValueError("Invalid comparison mode.")

    old_lines = old.splitlines()
    new_lines = new.splitlines()

    normalized_old = [
        normalize_line(line, mode)
        for line in old_lines
    ]

    normalized_new = [
        normalize_line(line, mode)
        for line in new_lines
    ]

    matcher = difflib.SequenceMatcher(
        None,
        normalized_old,
        normalized_new,
        autojunk=False
    )

    rows = []

    for tag, i, j, k, l in matcher.get_opcodes():

        old_range = (
            f"{i + 1}-{j}" if j > i else "-"
        )

        new_range = (
            f"{k + 1}-{l}" if l > k else "-"
        )

        rows.append([
            LABELS[tag],
            old_range,
            new_range,
            "\n".join(old_lines[i:j]),
            "\n".join(new_lines[k:l])
        ])

    return rows


# ==================================================
# CHANGE SUMMARY
# ==================================================

def get_counts(changes):

    labels = [
        "Added",
        "Modified",
        "Removed",
        "Unchanged"
    ]

    return {
        label: sum(
            1 for row in changes
            if row[0] == label
        )
        for label in labels
    }


# ==================================================
# CSV EXPORT
# ==================================================

def create_csv(changes):

    if not changes:
        raise ValueError("Compare text before exporting.")

    output = io.StringIO(newline="")

    writer = csv.writer(output)

    writer.writerow([
        "Change",
        "Old Lines",
        "New Lines",
        "Original",
        "Updated"
    ])

    writer.writerows(changes)

    return output.getvalue()


# ==================================================
# FILE UPLOAD
# ==================================================

def parse_uploaded_files(content_type, body):

    headers = (
        "Content-Type: " + content_type + "\r\n"
        "MIME-Version: 1.0\r\n\r\n"
    ).encode("utf-8")

    message = BytesParser(policy=default).parsebytes(
        headers + body
    )

    uploaded = {}

    for part in message.iter_parts():

        field_name = part.get_param(
            "name",
            header="content-disposition"
        )

        filename = part.get_filename()

        if not field_name or not filename:
            continue

        if not filename.lower().endswith(".txt"):
            raise ValueError("Only .txt files are allowed.")

        content = part.get_payload(decode=True) or b""

        if len(content) > MAX_TEXT_SIZE:
            raise ValueError("Each file must be under 1 MB.")

        try:
            uploaded[field_name] = content.decode("utf-8-sig")
        except UnicodeDecodeError:
            raise ValueError(
                "Files must use UTF-8 encoding."
            )

    return uploaded


# ==================================================
# HTML HELPERS
# ==================================================

def esc(value):
    return html.escape(str(value), quote=True)


def render_page(message="", error=False):

    old = esc(store["old"])
    new = esc(store["new"])

    counts = get_counts(store["changes"])

    rows_html = ""

    for row in store["changes"]:

        rows_html += """
        <tr>
            <td>{}</td>
            <td>{}</td>
            <td>{}</td>
            <td><pre>{}</pre></td>
            <td><pre>{}</pre></td>
        </tr>
        """.format(
            esc(row[0]),
            esc(row[1]),
            esc(row[2]),
            esc(row[3]),
            esc(row[4])
        )

    if not rows_html:
        rows_html = """
        <tr>
            <td colspan="5" class="empty">
                No comparison available. Enter text and click Compare.
            </td>
        </tr>
        """

    message_html = ""

    if message:
        message_class = "error" if error else "success"
        message_html = (
            f'<div class="{message_class}">{esc(message)}</div>'
        )

    return f"""
<!DOCTYPE html>
<html lang="en">

<head>

<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">

<title>{APP_TITLE}</title>

<style>

* {{
    box-sizing: border-box;
}}

body {{
    margin: 0;
    font-family: Arial, sans-serif;
    background: #f4f6fa;
    color: #202b3c;
}}

header {{
    background: #172554;
    color: white;
    padding: 30px 18px;
    text-align: center;
}}

header h1 {{
    margin: 0 0 10px;
    font-size: 27px;
}}

header p {{
    margin: 0;
    color: #dbeafe;
}}

.container {{
    max-width: 1100px;
    margin: 30px auto;
    padding: 0 16px;
}}

.card {{
    background: white;
    padding: 24px;
    margin-bottom: 22px;
    border-radius: 12px;
    box-shadow: 0 3px 12px rgba(0,0,0,0.06);
}}

h2 {{
    margin-top: 0;
    color: #172554;
}}

textarea {{
    width: 100%;
    min-height: 180px;
    padding: 13px;
    border: 1px solid #cbd5e1;
    border-radius: 8px;
    font-family: monospace;
    font-size: 14px;
    resize: vertical;
}}

label {{
    display: block;
    font-weight: bold;
    margin: 14px 0 8px;
}}

select, input[type=file] {{
    width: 100%;
    padding: 12px;
    border: 1px solid #cbd5e1;
    border-radius: 8px;
    background: white;
}}

.text-grid {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 20px;
}}

button, .download {{
    display: inline-block;
    border: none;
    border-radius: 8px;
    background: #2563eb;
    color: white;
    padding: 12px 20px;
    margin-top: 18px;
    cursor: pointer;
    text-decoration: none;
    font-size: 15px;
    font-weight: bold;
}}

button:hover, .download:hover {{
    background: #1d4ed8;
}}

.summary {{
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 12px;
}}

.stat {{
    padding: 18px;
    background: #eff6ff;
    border-radius: 9px;
    text-align: center;
}}

.stat strong {{
    display: block;
    font-size: 27px;
    color: #1d4ed8;
}}

.stat span {{
    font-size: 13px;
}}

.table-wrap {{
    overflow-x: auto;
}}

table {{
    width: 100%;
    border-collapse: collapse;
    min-width: 750px;
}}

th, td {{
    padding: 12px;
    border: 1px solid #e2e8f0;
    text-align: left;
    vertical-align: top;
}}

th {{
    background: #172554;
    color: white;
}}

pre {{
    white-space: pre-wrap;
    overflow-wrap: anywhere;
    font-family: monospace;
    margin: 0;
}}

.empty {{
    text-align: center;
    color: #64748b;
    padding: 25px;
}}

.success {{
    padding: 14px;
    margin-bottom: 18px;
    background: #dcfce7;
    color: #166534;
    border-radius: 8px;
}}

.error {{
    padding: 14px;
    margin-bottom: 18px;
    background: #fee2e2;
    color: #991b1b;
    border-radius: 8px;
}}

small {{
    color: #64748b;
}}

footer {{
    text-align: center;
    padding: 25px;
    color: #64748b;
}}

@media(max-width: 700px) {{

    .text-grid {{
        grid-template-columns: 1fr;
    }}

    .summary {{
        grid-template-columns: repeat(2, 1fr);
    }}

    header h1 {{
        font-size: 21px;
    }}

    .card {{
        padding: 17px;
    }}
}}

</style>

</head>

<body>

<header>
    <h1>{APP_TITLE}</h1>
    <p>Compare text, identify changes and export reports.</p>
</header>

<main class="container">

    {message_html}

    <section class="card">

        <h2>Text Comparison</h2>

        <form method="POST" action="/compare">

            <div class="text-grid">

                <div>
                    <label>Original Text</label>
                    <textarea name="old" required>{old}</textarea>
                </div>

                <div>
                    <label>Updated Text</label>
                    <textarea name="new" required>{new}</textarea>
                </div>

            </div>

            <label>Comparison Mode</label>

            <select name="mode">

                <option value="Exact">Exact</option>

                <option value="Ignore case and repeated spaces">
                    Ignore case and repeated spaces
                </option>

            </select>

            <button type="submit">Compare Text</button>

        </form>

    </section>

    <section class="card">

        <h2>Upload Text Files</h2>

        <small>
            Upload two UTF-8 .txt files. Maximum 1 MB per file.
        </small>

        <form method="POST" action="/upload"
              enctype="multipart/form-data">

            <label>Original .txt File</label>
            <input type="file" name="old_file"
                   accept=".txt,text/plain" required>

            <label>Updated .txt File</label>
            <input type="file" name="new_file"
                   accept=".txt,text/plain" required>

            <button type="submit">Upload and Compare</button>

        </form>

    </section>

    <section class="card">

        <h2>Change Summary</h2>

        <div class="summary">

            <div class="stat">
                <strong>{counts["Added"]}</strong>
                <span>Added Blocks</span>
            </div>

            <div class="stat">
                <strong>{counts["Modified"]}</strong>
                <span>Modified Blocks</span>
            </div>

            <div class="stat">
                <strong>{counts["Removed"]}</strong>
                <span>Removed Blocks</span>
            </div>

            <div class="stat">
                <strong>{counts["Unchanged"]}</strong>
                <span>Unchanged Blocks</span>
            </div>

        </div>

    </section>

    <section class="card">

        <h2>Comparison Report</h2>

        <div class="table-wrap">

            <table>

                <thead>
                    <tr>
                        <th>Change</th>
                        <th>Old Lines</th>
                        <th>New Lines</th>
                        <th>Original</th>
                        <th>Updated</th>
                    </tr>
                </thead>

                <tbody>
                    {rows_html}
                </tbody>

            </table>

        </div>

        <a class="download" href="/export.csv">
            Download CSV Report
        </a>

    </section>

    <section class="card">
        <small>
            This tool compares plain text. It does not determine
            authorship or plagiarism.
        </small>
    </section>

</main>

<footer>
    DAA Project 9 | Text Comparison and Change Tracker
</footer>

</body>
</html>
"""


# ==================================================
# HTTP SERVER
# ==================================================

class AppHandler(BaseHTTPRequestHandler):

    def send_html(self, content, status=200):

        body = content.encode("utf-8")

        self.send_response(status)

        self.send_header(
            "Content-Type",
            "text/html; charset=utf-8"
        )

        self.send_header(
            "Content-Length",
            str(len(body))
        )

        self.send_header("X-Content-Type-Options", "nosniff")

        self.send_header("Cache-Control", "no-store")

        self.end_headers()

        self.wfile.write(body)

    def send_error_page(self, message, status=400):

        self.send_html(render_page(message, error=True), status)

    def do_GET(self):

        if self.path == "/health":

            body = b"OK"

            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

            return

        if self.path == "/export.csv":

            try:
                with store_lock:
                    content = create_csv(store["changes"])

                body = content.encode("utf-8-sig")

                self.send_response(200)

                self.send_header(
                    "Content-Type",
                    "text/csv; charset=utf-8"
                )

                self.send_header(
                    "Content-Disposition",
                    'attachment; filename="comparison.csv"'
                )

                self.send_header(
                    "Content-Length",
                    str(len(body))
                )

                self.end_headers()
                self.wfile.write(body)

            except ValueError as error:
                self.send_error_page(str(error))

            return

        if self.path not in ("/", "/index.html"):

            self.send_error_page("Page not found.", 404)
            return

        with store_lock:
            page = render_page()

        self.send_html(page)

    def do_POST(self):

        global store

        content_length = int(
            self.headers.get("Content-Length", "0")
        )

        if content_length <= 0 or content_length > MAX_REQUEST_SIZE:
            self.send_error_page("Invalid or oversized request.", 413)
            return

        body = self.rfile.read(content_length)

        try:

            if self.path == "/compare":

                form_data = parse_qs(
                    body.decode("utf-8"),
                    keep_blank_values=True
                )

                old = form_data.get("old", [""])[0]
                new = form_data.get("new", [""])[0]
                mode = form_data.get("mode", ["Exact"])[0]

            elif self.path == "/upload":

                content_type = self.headers.get(
                    "Content-Type", ""
                )

                if not content_type.startswith("multipart/form-data"):
                    raise ValueError("Invalid upload request.")

                uploaded = parse_uploaded_files(
                    content_type,
                    body
                )

                if "old_file" not in uploaded or "new_file" not in uploaded:
                    raise ValueError("Please upload both text files.")

                old = uploaded["old_file"]
                new = uploaded["new_file"]
                mode = "Exact"

            else:

                self.send_error_page("Unknown action.", 404)
                return

            if not isinstance(old, str) or not isinstance(new, str):
                raise ValueError("Invalid text input.")

            if len(old) > MAX_TEXT_SIZE or len(new) > MAX_TEXT_SIZE:
                raise ValueError("Maximum text size is 1 MB per input.")

            if mode not in MODES:
                raise ValueError("Invalid comparison mode.")

            changes = compare(old, new, mode)

            new_data = {
                "old": old,
                "new": new,
                "changes": changes
            }

            with store_lock:

                save_data(new_data)
                store = new_data

            self.send_html(
                render_page("Comparison completed successfully.")
            )

        except (ValueError, UnicodeDecodeError, OSError) as error:

            self.send_error_page(str(error))

        except Exception:

            print("Unexpected request error:", flush=True)
            self.send_error_page(
                "An unexpected server error occurred.",
                500
            )

    def log_message(self, format, *args):

        print(
            "%s - %s" % (self.address_string(), format % args),
            flush=True
        )


# ==================================================
# APPLICATION START
# ==================================================

def main():

    server = ThreadingHTTPServer(
        (HOST, PORT),
        AppHandler
    )

    print("=" * 55, flush=True)
    print(APP_TITLE, flush=True)
    print("Server host: " + HOST, flush=True)
    print("Server port: " + str(PORT), flush=True)
    print("Health endpoint: /health", flush=True)
    print("Server is ready!", flush=True)
    print("=" * 55, flush=True)

    try:
        server.serve_forever()

    except KeyboardInterrupt:
        print("Server shutting down...", flush=True)

    finally:
        server.server_close()


if __name__ == "__main__":
    main()
