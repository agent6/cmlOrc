#!/usr/bin/env python3
import argparse
import sqlite3
import sys
from pathlib import Path


def _default_db_path() -> Path:
    repo_root = Path(__file__).resolve().parents[1]
    return repo_root / "db.sqlite3"


def main() -> int:
    parser = argparse.ArgumentParser(description="Print count of CML servers with status=in_use.")
    parser.add_argument(
        "--db",
        default=str(_default_db_path()),
        help="Path to db.sqlite3 (default: repo root db.sqlite3).",
    )
    parser.add_argument(
        "--status",
        default="in_use",
        help="Status value to count (default: in_use).",
    )
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print("0")
        print(f"db not found: {db_path}", file=sys.stderr)
        return 1

    try:
        with sqlite3.connect(str(db_path)) as conn:
            cur = conn.execute(
                "SELECT COUNT(*) FROM orchestrator_cmlserver WHERE status = ?",
                (args.status,),
            )
            row = cur.fetchone()
            print(str(row[0] if row else 0))
        return 0
    except Exception as exc:
        print("0")
        print(f"error reading {db_path}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
