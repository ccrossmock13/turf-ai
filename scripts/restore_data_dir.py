#!/usr/bin/env python3
"""Restore a Greenside AI DATA_DIR backup archive."""

from __future__ import annotations

import argparse
import shutil
import tarfile
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Restore a Greenside AI DATA_DIR backup archive.")
    parser.add_argument("archive", help="Backup archive created by backup_data_dir.py")
    parser.add_argument("--target-dir", default=".", help="Directory where the DATA_DIR folder should be restored.")
    parser.add_argument("--force", action="store_true", help="Allow overwriting an existing restored folder.")
    args = parser.parse_args()

    archive_path = Path(args.archive).expanduser().resolve()
    if not archive_path.exists():
        raise SystemExit(f"Archive does not exist: {archive_path}")

    target_dir = Path(args.target_dir).expanduser().resolve()
    target_dir.mkdir(parents=True, exist_ok=True)

    with tarfile.open(archive_path, "r:gz") as archive:
        members = archive.getmembers()
        top_level_names = sorted({member.name.split("/", 1)[0] for member in members if member.name})
        if len(top_level_names) != 1:
            raise SystemExit("Archive must contain exactly one top-level DATA_DIR folder.")
        restore_name = top_level_names[0]
        restore_path = target_dir / restore_name
        if restore_path.exists():
            if not args.force:
                raise SystemExit(f"Restore target already exists: {restore_path}. Use --force to overwrite.")
            shutil.rmtree(restore_path)
        archive.extractall(target_dir)

    print(str(restore_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
