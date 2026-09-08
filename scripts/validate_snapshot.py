#!/usr/bin/env python3
"""Validate a reviewed RollPig snapshot, including rights and protocol integrity."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from publication_policy import DEFAULT_APPROVALS, validate_publication
from sync_primary import _sha256, _validate_manifest


def validate(root: Path, approvals_path: Path = DEFAULT_APPROVALS) -> dict:
    # The approval file is repository-maintained policy, never a member supplied
    # by the downloaded snapshot. Empty policy rejects all historical snapshots.
    publication = validate_publication(root, approvals_path)
    manifest_raw = (root / "manifest.json").read_bytes()
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
        with path.open("rb") as source:
            data = source.read(int(member["size"]) + 1)
        expected_size = int(member["size"])
        if len(data) != expected_size:
            raise ValueError(f"size mismatch for {relative}")
        if _sha256(data) != str(member["sha256"]):
            raise ValueError(f"sha256 mismatch for {relative}")
        total += len(data)
    if total != int(manifest["package_size"]):
        raise ValueError("snapshot package size does not match manifest")
    return {
        "resource_version": str(manifest["resource_version"]),
        "members": len(members),
        "package_size": total,
        **publication,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", type=Path, default=Path("public/v1"))
    args = parser.parse_args()
    print(json.dumps(validate(args.root), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
