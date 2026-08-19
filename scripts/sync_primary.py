#!/usr/bin/env python3
"""Mirror one fully validated RollPig Resource Protocol v1 snapshot."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import shutil
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path, PurePosixPath

CLIENT_ID = "astrbot_plugin_rollpig_plus"
SCHEMA_VERSION = 1
DEFAULT_MANIFEST_URL = "https://curryudon.top/astrbot-rollpig/v1/manifest.json"
MAX_MANIFEST_BYTES = 1024 * 1024
MAX_PACKAGE_BYTES = 128 * 1024 * 1024
MAX_MEMBER_BYTES = 50 * 1024 * 1024
MAX_MEMBERS = 1608
USER_AGENT = "AstrBot-RollPig/3.11.5 (+https://github.com/casama233/rollpig-public-source-mirror; mirror)"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _fetch(url: str, *, max_bytes: int, timeout: float, retries: int = 3) -> bytes:
    last_error: Exception | None = None
    for attempt in range(retries):
        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": USER_AGENT,
                "X-RollPig-Client": CLIENT_ID,
                "X-RollPig-Protocol": str(SCHEMA_VERSION),
                "Accept": "application/json, application/octet-stream;q=0.9, */*;q=0.1",
                "Cache-Control": "no-cache",
                "Pragma": "no-cache",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                length = response.headers.get("Content-Length")
                if length and int(length) > max_bytes:
                    raise ValueError(f"remote file exceeds limit: {url}")
                data = response.read(max_bytes + 1)
                if len(data) > max_bytes:
                    raise ValueError(f"remote file exceeds limit: {url}")
                return data
        except (OSError, urllib.error.URLError, urllib.error.HTTPError, ValueError) as exc:
            last_error = exc
            if attempt + 1 < retries:
                time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"failed to fetch {url}: {last_error}") from last_error


def _safe_member_path(value: object) -> str:
    raw = str(value or "").strip()
    if not raw or "\\" in raw or raw.startswith("/"):
        raise ValueError(f"unsafe resource path: {raw!r}")
    path = PurePosixPath(raw)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError(f"unsafe resource path: {raw!r}")
    if ":" in path.parts[0]:
        raise ValueError(f"unsafe resource path: {raw!r}")
    return path.as_posix()


def _member(raw: object, *, label: str) -> dict[str, object]:
    if not isinstance(raw, dict):
        raise ValueError(f"{label} must be an object")
    path = _safe_member_path(raw.get("path"))
    try:
        size = int(raw.get("size"))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} has invalid size") from exc
    digest = str(raw.get("sha256") or "").lower().strip()
    if size < 0 or size > MAX_MEMBER_BYTES:
        raise ValueError(f"{label} size is outside the safety limit")
    if len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest):
        raise ValueError(f"{label} has invalid sha256")
    return {"path": path, "size": size, "sha256": digest}


def _manifest_members(manifest: dict) -> list[dict[str, object]]:
    members: list[dict[str, object]] = []
    for key in ("pig_json", "roast_copy", "ex_variants"):
        if manifest.get(key) is not None:
            members.append(_member(manifest[key], label=key))
    for key in ("images", "variant_images"):
        raw_items = manifest.get(key, [])
        if not isinstance(raw_items, list):
            raise ValueError(f"{key} must be an array")
        for index, raw in enumerate(raw_items):
            members.append(_member(raw, label=f"{key}[{index}]"))
    if not members or len(members) > MAX_MEMBERS:
        raise ValueError("manifest member count is outside the safety limit")
    paths = [str(item["path"]) for item in members]
    if len(set(paths)) != len(paths):
        raise ValueError("manifest contains duplicate resource paths")
    return members


def _validate_manifest(raw: bytes) -> tuple[dict, list[dict[str, object]]]:
    try:
        manifest = json.loads(raw.decode("utf-8-sig"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("manifest is not valid UTF-8 JSON") from exc
    if not isinstance(manifest, dict):
        raise ValueError("manifest must be an object")
    if int(manifest.get("schema_version") or 0) != SCHEMA_VERSION:
        raise ValueError("unsupported manifest schema_version")
    if str(manifest.get("client") or "") != CLIENT_ID:
        raise ValueError("manifest client does not match RollPig Plus")
    version = str(manifest.get("resource_version") or "").strip()
    if not version or len(version) > 64:
        raise ValueError("manifest resource_version is invalid")
    members = _manifest_members(manifest)
    try:
        declared_package_size = int(manifest.get("package_size"))
    except (TypeError, ValueError) as exc:
        raise ValueError("manifest package_size is invalid") from exc
    actual_declared_size = sum(int(item["size"]) for item in members)
    if declared_package_size != actual_declared_size:
        raise ValueError(
            f"manifest package_size mismatch: {declared_package_size} != {actual_declared_size}"
        )
    if declared_package_size <= 0 or declared_package_size > MAX_PACKAGE_BYTES:
        raise ValueError("manifest package_size is outside the safety limit")
    return manifest, members


def _same_origin(base_url: str, candidate: str) -> bool:
    base = urllib.parse.urlsplit(base_url)
    target = urllib.parse.urlsplit(candidate)
    return (
        target.scheme == "https"
        and target.scheme == base.scheme
        and target.hostname == base.hostname
        and target.port == base.port
    )


def sync(manifest_url: str, target: Path, *, timeout: float = 30.0) -> dict:
    parsed = urllib.parse.urlsplit(manifest_url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise ValueError("manifest URL must be HTTPS")

    manifest_raw = _fetch(
        manifest_url,
        max_bytes=MAX_MANIFEST_BYTES,
        timeout=timeout,
    )
    manifest, members = _validate_manifest(manifest_raw)
    manifest_hash = _sha256(manifest_raw)
    version = str(manifest["resource_version"])

    mirror_meta = target / "mirror.json"
    try:
        existing_meta = json.loads(mirror_meta.read_text(encoding="utf-8"))
    except Exception:
        existing_meta = {}
    if (
        isinstance(existing_meta, dict)
        and str(existing_meta.get("resource_version") or "") == version
        and str(existing_meta.get("source_manifest_sha256") or "") == manifest_hash
        and (target / "manifest.json").is_file()
    ):
        return {"changed": False, "resource_version": version, "members": len(members)}

    target.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".v1-mirror-", dir=str(target.parent)))
    try:
        (staging / "manifest.json").write_bytes(manifest_raw)
        base_url = manifest_url.rsplit("/", 1)[0] + "/"
        downloaded = 0
        for member in members:
            relative = str(member["path"])
            url = urllib.parse.urljoin(base_url, relative)
            if not _same_origin(base_url, url):
                raise ValueError(f"resource path escaped primary origin: {relative}")
            expected_size = int(member["size"])
            data = _fetch(
                url,
                max_bytes=min(MAX_MEMBER_BYTES, expected_size + 1),
                timeout=max(timeout, 45.0),
            )
            if len(data) != expected_size:
                raise ValueError(
                    f"size mismatch for {relative}: {len(data)} != {expected_size}"
                )
            if _sha256(data) != str(member["sha256"]):
                raise ValueError(f"sha256 mismatch for {relative}")
            destination = staging / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(data)
            downloaded += len(data)

        if downloaded != int(manifest["package_size"]):
            raise ValueError("downloaded package size does not match manifest")

        # health.json is diagnostic rather than part of the signed member set. Keep
        # it when the primary serves it, but never let an unavailable health file
        # invalidate an otherwise complete protocol snapshot.
        health_url = urllib.parse.urljoin(base_url, "health.json")
        try:
            health_raw = _fetch(health_url, max_bytes=256 * 1024, timeout=timeout, retries=2)
            health = json.loads(health_raw.decode("utf-8-sig"))
            if (
                isinstance(health, dict)
                and str(health.get("resource_version") or "") == version
                and str(health.get("client") or CLIENT_ID) == CLIENT_ID
            ):
                (staging / "health.json").write_bytes(health_raw)
        except Exception:
            pass

        metadata = {
            "schema_version": 1,
            "authoritative": False,
            "source": "primary",
            "primary_manifest_url": manifest_url,
            "resource_version": version,
            "source_manifest_sha256": manifest_hash,
            "package_size": int(manifest["package_size"]),
            "member_count": len(members),
            "mirrored_at": dt.datetime.now(dt.timezone.utc)
            .replace(microsecond=0)
            .isoformat(),
        }
        (staging / "mirror.json").write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        if target.exists():
            shutil.rmtree(target)
        staging.rename(target)
        return {
            "changed": True,
            "resource_version": version,
            "members": len(members),
            "package_size": downloaded,
        }
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest-url",
        default=os.environ.get("ROLLPIG_PRIMARY_MANIFEST_URL", DEFAULT_MANIFEST_URL),
    )
    parser.add_argument("--target", type=Path, default=Path("public/v1"))
    parser.add_argument("--timeout", type=float, default=30.0)
    args = parser.parse_args()
    result = sync(args.manifest_url, args.target, timeout=max(2.0, min(120.0, args.timeout)))
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
