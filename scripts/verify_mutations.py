"""Prove selected critical assertions detect deliberately wrong rule changes.

Mutations are made only in temporary copies, never in the working tree.
This is a small targeted mutation check, not a claim of exhaustive mutation coverage.
"""
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
CASES = [
    ('Reject GPS exactly at 50 m', 'core/location.py',
     'accuracy_m > MAX_GPS_ACCURACY_M', 'accuracy_m >= MAX_GPS_ACCURACY_M',
     'tests/test_location.py::test_exactly_50_m_accuracy_is_accepted'),
    ('Let the later player steal a tied territory', 'core/scoring_v1.py',
     'totals[member] > totals[owner]', 'totals[member] >= totals[owner]',
     'tests/test_scoring_invariants.py'),
    ('Double territory-owner income', 'core/scoring_v1.py',
     '+ bonus\n', '+ bonus * 2\n', 'tests/test_scoring_v1.py::test_full_capture_sequence_and_no_self_income'),
    ('Accept a drink exactly at weekly close', 'core/scoring_v1.py',
     'utc(start) <= at < utc(end)', 'utc(start) <= at <= utc(end)',
     'tests/test_scoring_v1.py::test_weekly_boundaries'),
    ('Allow corrections exactly at the deadline', 'core/scoring_v1.py',
     'utc(entry.submitted_at) <= at < utc(entry.submitted_at)',
     'utc(entry.submitted_at) <= at <= utc(entry.submitted_at)', 'tests/test_scoring_v1.py'),
]


def run(directory, target):
    return subprocess.run([sys.executable, '-m', 'pytest', '-q', target], cwd=directory,
                          capture_output=True, text=True, timeout=120)


def main():
    results = []
    with TemporaryDirectory(prefix='wegopub-mutations-') as temp:
        copy = Path(temp)
        shutil.copytree(ROOT / 'core', copy / 'core', ignore=shutil.ignore_patterns('__pycache__'))
        (copy / 'tests').mkdir()
        for name in ['__init__.py', 'test_location.py', 'test_scoring_v1.py', 'test_scoring_invariants.py', 'test_checkins.py']:
            shutil.copyfile(ROOT / 'tests' / name, copy / 'tests' / name)
        # A pre-existing failure must never masquerade as a detected mutation.
        baseline = run(copy, 'tests')
        if baseline.returncode:
            print(baseline.stdout + baseline.stderr)
            return 1
        for name, file, old, new, target in CASES:
            path = copy / file
            original = path.read_text(encoding='utf-8')
            if original.count(old) != 1:
                raise RuntimeError(f'{name}: mutation anchor must occur exactly once')
            path.write_text(original.replace(old, new), encoding='utf-8')
            try:
                outcome = run(copy, target)
                # Exit 1 means failed test assertions; collection/tool errors do not count.
                detected = outcome.returncode == 1 and ' failed' in outcome.stdout
                results.append({'mutation': name, 'detected': detected, 'exit_code': outcome.returncode})
                print(('DETECTED: ' if detected else 'NOT DETECTED: ') + name, flush=True)
                if not detected:
                    print(outcome.stdout + outcome.stderr)
            finally:
                path.write_text(original, encoding='utf-8')
                shutil.rmtree(copy / 'core/__pycache__', ignore_errors=True)
    report = ROOT / '.venv/mutations.json'
    report.parent.mkdir(exist_ok=True)
    report.write_text(json.dumps({'checked_at_utc': datetime.now(timezone.utc).isoformat(), 'checks': results}, indent=2) + '\n')
    return 0 if all(result['detected'] for result in results) else 1


if __name__ == '__main__':
    raise SystemExit(main())
