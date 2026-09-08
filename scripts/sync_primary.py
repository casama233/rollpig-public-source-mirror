#!/usr/bin/env python3
"""Refresh an exact approved snapshot, including every attribution/authoring file."""
from __future__ import annotations

import argparse
import json
import shutil
import tempfile
import urllib.request
from pathlib import Path

from publication_policy import DEFAULT_APPROVALS, PRIMARY, validate_publication
from snapshot_protocol import MAX_MANIFEST, digest, parse_json, safe_path, validate_manifest


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise ValueError('Publication downloads must stay on the exact primary origin')


def fetch(url: str, limit: int, timeout: float) -> bytes:
    request = urllib.request.Request(url, headers={
        'User-Agent': 'AstrBot-RollPig/3.12.3 (reviewed mirror)',
        'X-RollPig-Client': 'astrbot_plugin_rollpig_plus', 'X-RollPig-Protocol': '1',
        'Cache-Control': 'no-cache',
    })
    with urllib.request.build_opener(NoRedirect()).open(request, timeout=timeout) as response:
        raw = response.read(limit + 1)
    if len(raw) > limit:
        raise ValueError('Publication file exceeds size limit')
    return raw


def sync(manifest_url: str, target: Path, *, timeout=30.0, approvals_path=DEFAULT_APPROVALS) -> dict:
    if manifest_url != PRIMARY:
        raise ValueError('Only the authoritative primary source is supported')
    target = Path(target)
    if target.name != 'v1' or target.is_symlink():
        raise ValueError('Target must be a real v1 snapshot directory')
    policy = parse_json(Path(approvals_path).read_bytes())
    raw = fetch(PRIMARY, MAX_MANIFEST, timeout)
    review = policy['approved_snapshots'].get(digest(raw))
    if not isinstance(review, dict) or review.get('status') != 'approved':
        raise ValueError('Current primary snapshot is not approved; no automatic publication')
    _, members = validate_manifest(raw)
    sizes = {item['path']: item['size'] for item in members}
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.reviewed-', dir=target.parent) as temporary:
        stage = Path(temporary) / 'snapshot'
        stage.mkdir()
        (stage / 'manifest.json').write_bytes(raw)
        for name, sha in review['files'].items():
            safe_path(name)
            if name == 'manifest.json':
                continue
            data = fetch(PRIMARY.rsplit('/', 1)[0] + '/' + name, sizes.get(name, MAX_MANIFEST), timeout)
            if digest(data) != sha:
                raise ValueError('Downloaded bytes differ from approved snapshot: ' + name)
            path = stage / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        # Reload policy after downloading: an intervening withdrawal must stop activation.
        result = validate_publication(stage, approvals_path)
        previous = Path(temporary) / 'previous'
        if target.exists():
            target.rename(previous)
        try:
            stage.rename(target)
        except BaseException:
            if previous.exists() and not target.exists():
                previous.rename(target)
            raise
        return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target', type=Path, default=Path('public/v1'))
    args = parser.parse_args()
    print(json.dumps(sync(PRIMARY, args.target)))
