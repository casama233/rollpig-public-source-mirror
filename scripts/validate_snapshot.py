#!/usr/bin/env python3
"""Validate a separately reviewed source-service snapshot without network I/O."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from publication_policy import DEFAULT_APPROVALS, validate_publication


def validate(root: Path, approvals_path: Path = DEFAULT_APPROVALS) -> dict:
    return validate_publication(root, approvals_path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", type=Path, default=Path("public/v1"))
    args = parser.parse_args()
    print(json.dumps(validate(args.root), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
