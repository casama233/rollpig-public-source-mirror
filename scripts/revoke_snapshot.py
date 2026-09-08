#!/usr/bin/env python3
"""Record a withdrawal and remove the public working-tree snapshot in one change."""
import argparse
import json
import shutil
from pathlib import Path

from snapshot_protocol import digest, parse_json


def revoke(repository: Path, manifest_hash: str) -> None:
    repository = Path(repository)
    policy_path = repository / 'publication-approvals.json'
    policy = parse_json(policy_path.read_bytes())
    review = policy['approved_snapshots'][manifest_hash]
    review['status'] = 'revoked'
    temporary = policy_path.with_suffix('.json.tmp')
    temporary.write_text(json.dumps(policy, ensure_ascii=False, indent=2) + '\n')
    temporary.replace(policy_path)
    snapshot = repository / 'public/v1'
    if snapshot.is_symlink():
        raise ValueError('public snapshot must not be a symlink')
    if snapshot.is_dir() and digest((snapshot / 'manifest.json').read_bytes()) == manifest_hash:
        shutil.rmtree(snapshot)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest_sha256')
    args = parser.parse_args()
    revoke(Path(__file__).resolve().parents[1], args.manifest_sha256)
