#!/usr/bin/env python3
"""Validate a checked-in RollPig public-resource snapshot without network access."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from sync_primary import _sha256, _validate_manifest


def validate(root: Path) -> dict:
    manifest_path = root / "manifest.json"
    if not manifest_path.is_file():
        raise ValueError(f"missing snapshot manifest: {manifest_path}")
    manifest_raw = manifest_path.read_bytes()
    manifest, members = _validate_manifest(manifest_raw)
    root_resolved = root.resolve()
    total = 0
    for member in members:
        relative = str(member["path"])
        path = (root / relative).resolve()
        if root_resolved not in path.parents:
            raise ValueError(f"snapshot path escaped root: {relative}")
        if not path.is_file():
            raise ValueError(f"missing snapshot member: {relative}")
        data = path.read_bytes()
        expected_size = int(member["size"])
        if len(data) != expected_size:
            raise ValueError(f"size mismatch for {relative}")
        if _sha256(data) != str(member["sha256"]):
            raise ValueError(f"sha256 mismatch for {relative}")
        total += len(data)

    mirror_path = root / "mirror.json"
    if mirror_path.is_file():
        mirror = json.loads(mirror_path.read_text(encoding="utf-8"))
        if str(mirror.get("resource_version") or "") != str(
            manifest.get("resource_version") or ""
        ):
            raise ValueError("mirror metadata resource_version does not match manifest")
        source_hash = str(mirror.get("source_manifest_sha256") or "")
        if source_hash and source_hash != _sha256(manifest_raw):
            raise ValueError("mirror metadata manifest hash does not match manifest")

    if total != int(manifest["package_size"]):
        raise ValueError("snapshot package size does not match manifest")
    return {
        "resource_version": str(manifest["resource_version"]),
        "members": len(members),
        "package_size": total,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", type=Path, default=Path("public/v1"))
    args = parser.parse_args()
    print(json.dumps(validate(args.root), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
