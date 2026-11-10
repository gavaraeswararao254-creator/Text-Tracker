
"""Text Comparison and Change Tracker - Render deployment version."""

import sys
import csv
import io
import difflib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common import Store, form, heading, note, table, run


# --------------------------------------------------
# STORAGE
# --------------------------------------------------

store = Store(Path(__file__).with_name("data.json"), {
    "old": "The meeting is on Monday.\nBring your notebook.",
    "new": (
        "The meeting is on Tuesday.\n"
        "Bring your notebook.\n"
        "Arrive at 10 AM."
    ),
    "changes": []
})


# --------------------------------------------------
# TEXT COMPARISON
# --------------------------------------------------

MODES = [
    "Exact",
    "Ignore case and repeated spaces"
]


def normalize_line(line, mode):
    """Normalize text only for comparison, not for reporting."""

    if mode == "Ignore case and repeated spaces":
        return " ".join(line.lower().split())

    return line


def compare(old, new, mode):
    """Compare two line sequences and preserve original text."""

    if mode not in MODES:
        raise ValueError("Invalid comparison mode.")

    a = old.splitlines()
    b = new.splitlines()

    normalized_a = [
        normalize_line(line, mode) for line in a
    ]

    normalized_b = [
        normalize_line(line, mode) for line in b
    ]

    matcher = difflib.SequenceMatcher(
        None,
        normalized_a,
        normalized_b,
        autojunk=False
    )

    labels = {
        "equal": "Unchanged",
        "replace": "Modified",
        "delete": "Removed",
        "insert": "Added"
    }

    rows = []

    for tag, i, j, k, l in matcher.get_opcodes():

        old_range = (
            f"{i + 1}-{j}" if j > i else "-"
        )

        new_range = (
            f"{k + 1}-{l}" if l > k else "-"
        )

        rows.append([
            labels[tag],
            old_range,
            new_range,
            "\n".join(a[i:j]),
            "\n".join(b[k:l])
        ])

    return rows


# --------------------------------------------------
# CHANGE SUMMARY
# --------------------------------------------------

def get_counts():
    labels = [
        "Added",
        "Modified",
        "Removed",
        "Unchanged"
    ]

    return {
        label: sum(
            1 for row in store.data["changes"]
            if row[0] == label
        )
        for label in labels
    }


# --------------------------------------------------
# CSV EXPORT
# --------------------------------------------------

def create_csv():
    """Generate CSV content in memory."""

    if not store.data["changes"]:
        raise ValueError("Compare text first.")

    output = io.StringIO(newline="")

    writer = csv.writer(output)

    writer.writerow([
        "change",
        "old_lines",
        "new_lines",
        "original",
        "updated"
    ])

    writer.writerows(store.data["changes"])

    return output.getvalue()


# --------------------------------------------------
# USER INTERFACE
# --------------------------------------------------

def view():

    out = note(
        "Compare plain text and identify changes "
        "between original and updated versions. "
        "This tool does not judge authorship or plagiarism."
    )

    # Text comparison form

    out += form("compare", [
        (
            "old",
            "Original text",
            "textarea_optional",
            store.data["old"]
        ),
        (
            "new",
            "Updated text",
            "textarea_optional",
            store.data["new"]
        ),
        (
            "mode",
            "Comparison mode",
            "select",
            MODES
        )
    ], "Compare text")

    # Text file upload form
    # Requires common.py to implement these input types.

    out += note(
        "File upload is not enabled in this version. "
        "Use the text boxes to compare content."
    )

    # Change summary

    counts = get_counts()

    out += heading("Change Summary")

    out += note(
        "Added blocks: " + str(counts["Added"])
        + " | Modified blocks: " + str(counts["Modified"])
        + " | Removed blocks: " + str(counts["Removed"])
        + " | Unchanged blocks: " + str(counts["Unchanged"])
    )

    # Comparison report

    out += heading("Comparison Report")

    out += table(
        [
            "Change",
            "Old lines",
            "New lines",
            "Original",
            "Updated"
        ],
        store.data["changes"]
    )

    # Export form

    out += form(
        "export",
        [],
        "Export comparison report"
    )

    return out


# --------------------------------------------------
# REQUEST HANDLER
# --------------------------------------------------

def handle(data):

    action = data.get("action")

    if action == "compare":

        old = data.get("old", "")
        new = data.get("new", "")
        mode = data.get("mode", "Exact")

        if not isinstance(old, str) or not isinstance(new, str):
            raise ValueError("Text input must be valid text.")

        if len(old) > 1_000_000 or len(new) > 1_000_000:
            raise ValueError("Maximum text size is 1 MB per input.")

        if mode not in MODES:
            raise ValueError("Invalid comparison mode.")

        rows = compare(old, new, mode)

        store.data = {
            "old": old,
            "new": new,
            "changes": rows
        }

        store.save()

    elif action == "export":

        csv_content = create_csv()

        # Save in application folder as a fallback.
        # This is not permanent on Render's ephemeral filesystem.

        path = Path(__file__).with_name("comparison.csv")

        path.write_text(
            csv_content,
            encoding="utf-8"
        )

        return note(
            "CSV report created as comparison.csv. "
            "For browser downloads, common.py must provide "
            "a downloadable response."
        )

    else:
        raise ValueError("Unknown action.")


# --------------------------------------------------
# APPLICATION START
# --------------------------------------------------

if __name__ == "__main__":

    run(
        "Text Comparison and Change Tracker",
        view,
        handle
    )
