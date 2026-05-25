#!/usr/bin/env python3
"""Create a timestamped backup archive for the app DATA_DIR."""

from __future__ import annotations

import argparse
import os
import tarfile
from datetime import datetime
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Back up Greenside AI DATA_DIR into a .tar.gz archive.")
    parser.add_argument("--data-dir", default=os.getenv("DATA_DIR", "data"), help="Path to the DATA_DIR to back up.")
    parser.add_argument("--output-dir", default="backups", help="Directory to write the backup archive into.")
    args = parser.parse_args()

    data_dir = Path(args.data_dir).expanduser().resolve()
    if not data_dir.exists():
        raise SystemExit(f"DATA_DIR does not exist: {data_dir}")

    output_dir = Path(args.output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    archive_path = output_dir / f"greenside-data-backup-{stamp}.tar.gz"

    with tarfile.open(archive_path, "w:gz") as archive:
        archive.add(data_dir, arcname=data_dir.name)

    print(str(archive_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
