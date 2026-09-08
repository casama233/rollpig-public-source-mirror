#!/usr/bin/env python3
"""Build only the currently reviewed snapshot; an explicit revocation emits notice-only."""
from pathlib import Path
import json
import shutil

from publication_policy import validate_publication
from snapshot_protocol import digest, parse_json


def build(repository: Path, output: Path) -> dict:
    repository, output = Path(repository), Path(output)
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)
    policy_path = repository / 'publication-approvals.json'
    policy = parse_json(policy_path.read_bytes())
    snapshot = repository / 'public/v1'
    active = [key for key, value in policy['approved_snapshots'].items() if value.get('status') == 'approved']
    shutil.copyfile(repository / 'public/NOTICE.txt', output / 'NOTICE.txt')
    if active:
        result = validate_publication(snapshot, policy_path)
        if active != [result['manifest_sha256']]:
            raise ValueError('Only one reviewed current publication may be served')
        shutil.copytree(snapshot, output / 'v1')
    else:
        result = {'status': 'withdrawn', 'published_files': 0}
    shutil.copyfile(policy_path, output / 'publication-approvals.json')
    return result


if __name__ == '__main__':
    root = Path(__file__).resolve().parents[1]
    print(json.dumps(build(root, root / 'dist')))
