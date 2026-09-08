#!/usr/bin/env python3
"""Acquire the checksum-locked Meteo@UniParthenope NetCDF demo frame."""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import shutil
import tempfile
import urllib.request
from pathlib import Path

LOGGER = logging.getLogger(__name__)
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
LOCK = Path(__file__).with_name("sources.lock.json")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def acquire(root: Path, cache: Path, timeout: float) -> list[Path]:
    """Install verified sources under the server's normative archive layout."""
    records = json.loads(LOCK.read_text(encoding="utf-8"))["sources"]
    outputs: list[Path] = []
    for record in records:
        target = root / Path(record["archive_path"])
        cached = cache / Path(record["url"]).name
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.is_file() and sha256(target) == record["sha256"]:
            LOGGER.info("Verified existing archive frame %s", target)
            outputs.append(target)
            continue
        downloaded = False
        if cached.is_file() and sha256(cached) == record["sha256"]:
            LOGGER.info("Reusing checksum-matched local source %s", cached)
            source = cached
        else:
            fd, name = tempfile.mkstemp(prefix=target.name + ".", suffix=".download", dir=target.parent)
            os.close(fd)
            source = Path(name)
            downloaded = True
            try:
                LOGGER.info("Downloading %s", record["url"])
                with urllib.request.urlopen(record["url"], timeout=timeout) as response, source.open("wb") as output:
                    shutil.copyfileobj(response, output)
                if sha256(source) != record["sha256"]:
                    raise RuntimeError(f"checksum mismatch for {record['url']}")
            except Exception:
                source.unlink(missing_ok=True)
                raise
        fd, name = tempfile.mkstemp(prefix=target.name + ".", suffix=".tmp", dir=target.parent)
        os.close(fd)
        staging = Path(name)
        try:
            shutil.copyfile(source, staging)
            if sha256(staging) != record["sha256"]:
                raise RuntimeError(f"checksum mismatch while installing {target}")
            os.replace(staging, target)
        finally:
            staging.unlink(missing_ok=True)
            if downloaded:
                source.unlink(missing_ok=True)
        LOGGER.info("Installed %s (SHA-256 %s)", target, record["sha256"])
        outputs.append(target)
    return outputs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=REPOSITORY_ROOT / "data" / "netcdf-archive-demo")
    parser.add_argument("--cache", type=Path, default=REPOSITORY_ROOT / "data" / "meteouniparthenope" / "files")
    parser.add_argument("--timeout", type=float, default=120.0)
    args = parser.parse_args()
    acquire(args.root.expanduser().resolve(), args.cache.expanduser().resolve(), args.timeout)
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    raise SystemExit(main())
