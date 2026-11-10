"""Compare line sequences while preserving original text in the report."""
import sys
import csv
import difflib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import Store, form, heading, note, table, run

store = Store(Path(__file__).with_name('data.json'), {
    'old': 'The meeting is on Monday.\nBring your notebook.',
    'new': 'The meeting is on Tuesday.\nBring your notebook.\nArrive at 10 AM.',
    'changes': []})


def compare(old, new, mode):
    a, b = old.splitlines(), new.splitlines()
    if mode == 'Ignore case and repeated spaces':
        normalize = lambda line: ' '.join(line.lower().split())
    else:
        normalize = lambda line: line
    matcher = difflib.SequenceMatcher(None, [normalize(x) for x in a],
                                      [normalize(x) for x in b], autojunk=False)
    rows = []
    for tag, i, j, k, l in matcher.get_opcodes():
        labels = {'equal': 'Unchanged', 'replace': 'Modified',
                  'delete': 'Removed', 'insert': 'Added'}
        old_range = f'{i + 1}-{j}' if j > i else '-'
        new_range = f'{k + 1}-{l}' if l > k else '-'
        rows.append([labels[tag], old_range, new_range,
                     '\n'.join(a[i:j]), '\n'.join(b[k:l])])
    return rows


def view():
    out = note(
        'Compare plain text. The report describes edits; '
        'it does not judge authorship or plagiarism.'
    )

    out += form('compare', [
        ('old', 'Original text', 'textarea_optional', store.data['old']),
        ('new', 'Updated text', 'textarea_optional', store.data['new']),
        ('mode', 'Comparison mode', 'select',
         ['Exact', 'Ignore case and repeated spaces'])
    ], 'Compare text')

    out += form('files', [
        ('old_path', 'Original UTF-8 .txt file path', 'text', ''),
        ('new_path', 'Updated UTF-8 .txt file path', 'text', '')
    ], 'Load files and compare exactly')

    # Extension: count each type of change block
    labels = ['Added', 'Modified', 'Removed', 'Unchanged']

    counts = {
        label: sum(
            1 for row in store.data['changes']
            if row[0] == label
        )
        for label in labels
    }

    out += heading('Change Summary')
    out += note(
        'Added blocks: ' + str(counts['Added'])
        + ' | Modified blocks: ' + str(counts['Modified'])
        + ' | Removed blocks: ' + str(counts['Removed'])
        + ' | Unchanged blocks: ' + str(counts['Unchanged'])
    )

    out += heading('Comparison report')
    out += table(
        ['Change', 'Old lines', 'New lines', 'Original', 'Updated'],
        store.data['changes']
    )

    out += form('export', [], 'Export comparison report')
    return out

def handle(data):
    if data['action'] in ['compare', 'files']:
        if data['action'] == 'files':
            old = Path(data['old_path']).expanduser().read_text(encoding='utf-8')
            new = Path(data['new_path']).expanduser().read_text(encoding='utf-8')
            mode = 'Exact'
        else:
            old, new, mode = data['old'], data['new'], data['mode']
        if mode not in ['Exact', 'Ignore case and repeated spaces']:
            raise ValueError('Invalid comparison mode.')
        rows = compare(old, new, mode)
        store.data = {'old': old, 'new': new, 'changes': rows}
        store.save()
    elif data['action'] == 'export':
        if not store.data['changes']:
            raise ValueError('Compare text first.')
        path = Path(__file__).with_name('comparison.csv')
        with path.open('w', newline='', encoding='utf-8') as stream:
            writer = csv.writer(stream)
            writer.writerow(['change', 'old_lines', 'new_lines', 'original', 'updated'])
            writer.writerows(store.data['changes'])
        return note('Exported comparison.csv into this project folder.')
    else:
        raise ValueError('Unknown action.')


if __name__ == '__main__':
    run('Text Comparison and Change Tracker', view, handle)