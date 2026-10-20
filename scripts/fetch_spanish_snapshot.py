"""Rebuild the pinned OpenFootball inputs without relabeling cached data as new."""

import hashlib
import json
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]


def main():
    root = ROOT / "data/raw/research_20260925"
    root.mkdir(parents=True, exist_ok=True)
    for name in ("manifest.json", "espana_manifest.json"):
        source = ROOT / "configs/source_snapshots" / name
        manifest = json.loads(source.read_text(encoding="utf-8"))
        for item in manifest["files"]:
            relative = item["path"].replace("\\", "/")
            if item.get("status", 200) != 200 or not relative.startswith(
                ("openfootball/", "espana/")
            ):
                continue
            destination = root / relative
            if destination.exists():
                content = destination.read_bytes()
            else:
                response = requests.get(item["url"], timeout=45)
                response.raise_for_status()
                content = response.content
            if hashlib.sha256(content).hexdigest() != item["sha256"]:
                raise ValueError(f"Snapshot content differs from pinned hash: {destination}")
            if not destination.exists():
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(content)
            print(item["path"], flush=True)
        target = root / name
        if target.exists() and target.read_bytes() != source.read_bytes():
            raise ValueError(f"Different existing manifest: {target}")
        if not target.exists():
            target.write_bytes(source.read_bytes())


if __name__ == "__main__":
    main()
