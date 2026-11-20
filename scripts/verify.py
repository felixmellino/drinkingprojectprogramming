"""Run local/CI checks; database suites use disposable PostgreSQL fixtures."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from time import monotonic

ROOT = Path(__file__).resolve().parents[1]
COMPONENTS = ("camera_component", "location_component", "reaction_component")
DATABASE = (
    "migration_chain", "scoring_postgres", "chug_duel_postgres",
    "quiz_postgres", "focus_postgres", "focus_complete_postgres",
    "time_postgres", "reaction_postgres",
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--group", nargs="+", choices=("python", "components", "database", "mutations", "postgres", "browser"),
                        default=["python", "components", "database", "mutations"])
    parser.add_argument("--coverage", action="store_true", help="Measure Python branch coverage (requires requirements-verification.txt)")
    parser.add_argument("--report", type=Path, default=Path(".venv/verification.json"))
    args = parser.parse_args()
    env = dict(os.environ, SCORING_PYTHON=sys.executable)
    module = ROOT / "node_modules/@electric-sql/pglite/dist/index.cjs"
    env["PGLITE_MODULE"] = str(module)
    node = shutil.which("node")
    checks = []
    if "python" in args.group:
        prefix = [sys.executable, '-m', 'coverage', 'run', '--branch', '--source=core,data', '-m'] if args.coverage else [sys.executable, '-m']
        checks.append(("Python rules and Streamlit forms", prefix + ["pytest", "-q", "--junitxml=.venv/pytest.xml"]))
        if args.coverage:
            checks.extend([
                ('Coverage JSON', [sys.executable, '-m', 'coverage', 'json', '-o', '.venv/coverage.json']),
                ('Coverage HTML', [sys.executable, '-m', 'coverage', 'html', '-d', '.venv/coverage-html']),
            ])
    if "components" in args.group:
        checks.extend((name, [node or "node", f"tests/{name}.cjs"]) for name in COMPONENTS)
    if "database" in args.group:
        checks.extend((name, [node or "node", f"tests/{name}.cjs", str(module)]) for name in DATABASE)
    if 'mutations' in args.group:
        checks.append(('Critical rule mutations', [sys.executable, 'scripts/verify_mutations.py']))
    if 'postgres' in args.group:
        if not env.get('VERIFICATION_DATABASE_URL'):
            parser.error('The postgres group requires VERIFICATION_DATABASE_URL for the designated local test service.')
        checks.append(('Real PostgreSQL transactions', [sys.executable, '-m', 'pytest', '-q', 'tests/postgres_transactions.py', '--junitxml=.venv/postgres.xml']))
    if 'browser' in args.group:
        checks.append(('Two-player browser', [node or 'node', 'tests/quiz_browser.cjs', str(ROOT / 'node_modules/playwright')]))

    # Test databases live here even when Python is installed in another environment.
    (ROOT / ".venv").mkdir(exist_ok=True)
    # Snapshot provenance before the checks, not after someone may commit during a run.
    commit, dirty = None, None
    git = shutil.which("git")
    if git:
        revision = subprocess.run([git, "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=False)
        status = subprocess.run([git, "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True, check=False)
        if revision.returncode == 0:
            commit = revision.stdout.strip()
            dirty = bool(status.stdout) if status.returncode == 0 else None
    results = []
    for name, command in checks:
        print(f"\nChecking {name}...", flush=True)
        started = monotonic()
        error = None
        try:
            if command[0] != sys.executable and not node:
                raise RuntimeError("Install Node.js 24, then retry.")
            if name in DATABASE and not module.is_file():
                raise RuntimeError("PostgreSQL test dependency missing. Run npm ci --ignore-scripts first.")
            completed = subprocess.run(command, cwd=ROOT, env=env, timeout=600, check=False)
            code = completed.returncode
        except (OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
            error = str(exc)
            print(error, file=sys.stderr, flush=True)
            code = 1
        results.append({"name": name, "passed": code == 0, "exit_code": code,
                        "seconds": round(monotonic() - started, 2), "error": error})

    report = args.report if args.report.is_absolute() else ROOT / args.report
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps({
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "commit": commit, "working_tree_dirty": dirty, "groups": args.group, "checks": results,
    }, indent=2) + "\n", encoding="utf-8")
    passed = sum(result["passed"] for result in results)
    print(f"\n{passed}/{len(results)} checks passed. Report: {report}", flush=True)
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
