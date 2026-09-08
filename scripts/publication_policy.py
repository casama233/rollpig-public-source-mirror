"""Offline publication authorization; protocol integrity alone grants no rights.

Approvals are a separately reviewed repository file, never remote input. An
empty approval map intentionally rejects every resource snapshot. Passing this
check means bytes match a recorded review, not that software can prove copyright.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit

PROFILE = "provenance-safe-base-only"
PRIMARY = "https://curryudon.top/astrbot-rollpig/v1/manifest.json"
DEFAULT_APPROVALS = Path(__file__).resolve().parents[1] / "publication-approvals.json"
MAX_META_BYTES = 1024 * 1024
MAX_FILE_BYTES = 50 * 1024 * 1024
MAX_TOTAL_BYTES = 132 * 1024 * 1024
MAX_FILES = 1650
BASE_RIGHTS = {"original-work", "explicit-permission", "public-domain", "permissive-asset-license"}


def _read(path: Path, limit: int) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"not a regular publication file: {path}")
    with path.open("rb") as handle:
        data = handle.read(limit + 1)
    if len(data) > limit:
        raise ValueError(f"publication file exceeds limit: {path.name}")
    return data


def _json(data: bytes) -> dict:
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON key: {key}")
            result[key] = value
        return result
    value = json.loads(data.decode("utf-8-sig"), object_pairs_hook=unique)
    if not isinstance(value, dict):
        raise ValueError("publication metadata must be an object")
    return value


def _path(value: object) -> str:
    if not isinstance(value, str) or not value or "\\" in value or ":" in value or "\x00" in value:
        raise ValueError("invalid publication path")
    parts = value.split("/")
    if any(part in {"", ".", ".."} or part != part.strip() for part in parts):
        raise ValueError("non-canonical publication path")
    if PurePosixPath(value).is_absolute():
        raise ValueError("absolute publication path")
    return value


def _https(value: object) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    try:
        parsed = urlsplit(value)
        return parsed.scheme == "https" and bool(parsed.hostname) and not parsed.username and not parsed.password
    except ValueError:
        return False


def validate_publication(root: Path, approvals_path: Path = DEFAULT_APPROVALS) -> dict:
    root = Path(root)
    if root.is_symlink() or not root.is_dir():
        raise ValueError("snapshot root must be a real directory")
    policy = _json(_read(Path(approvals_path), MAX_META_BYTES))
    approved = policy.get("approved_snapshots")
    if policy.get("schema_version") != 1 or not isinstance(approved, dict):
        raise ValueError("invalid publication approval policy")
    raw = _read(root / "manifest.json", MAX_META_BYTES)
    manifest_hash = hashlib.sha256(raw).hexdigest()
    review = approved.get(manifest_hash)
    if not isinstance(review, dict) or review.get("status") != "approved":
        raise ValueError("snapshot has no separately reviewed publication approval")
    if review.get("profile") != PROFILE or review.get("primary_manifest_url") != PRIMARY:
        raise ValueError("approval does not identify the audited primary base-only publication")
    if not _https(review.get("review_url")):
        raise ValueError("approval is missing a review reference")
    manifest = _json(raw)
    if manifest.get("publication_profile") != PROFILE:
        raise ValueError("manifest is not provenance-safe base-only")
    if any(manifest.get(key) is not None for key in ("roast_copy", "ex_variants", "compatibility_floor")):
        raise ValueError("extension payloads are not permitted in a base-only mirror")
    if manifest.get("variant_images", []) != []:
        raise ValueError("EX images are not permitted in a base-only mirror")
    catalog = manifest.get("pig_json")
    images = manifest.get("images")
    if not isinstance(catalog, dict) or not isinstance(images, list) or not images:
        raise ValueError("base-only publication requires a catalog and images")
    members = [catalog, *images]
    if any(not isinstance(member, dict) for member in members):
        raise ValueError("invalid base member")
    member_paths = [_path(member.get("path")) for member in members]
    if len(set(member_paths)) != len(member_paths):
        raise ValueError("duplicate publication member")
    if member_paths[0] != "pig.json":
        raise ValueError("base catalog must be pig.json")
    for name in member_paths[1:]:
        path = PurePosixPath(name)
        if len(path.parts) != 2 or path.parts[0] not in {"image", "images"} or path.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp", ".gif"}:
            raise ValueError("unexpected base image path")
    files = review.get("files")
    if not isinstance(files, dict) or not files or len(files) > MAX_FILES:
        raise ValueError("approval requires an exact bounded file inventory")
    expected = {_path(name) for name in files}
    if len({name.casefold() for name in expected}) != len(expected):
        raise ValueError("case-colliding publication paths")
    required = {"manifest.json", "NOTICE.md", "PROVENANCE.json", *member_paths}
    licenses = {name for name in expected if name.startswith("LICENSES/") and PurePosixPath(name).suffix.lower() in {".md", ".txt"}}
    if not licenses or not required <= expected or expected != required | licenses:
        raise ValueError("missing rights documents or forbidden/unexpected publication files")
    actual = set()
    allowed_dirs = {str(parent) for name in expected for parent in PurePosixPath(name).parents if str(parent) != "."}
    for path in root.rglob("*"):
        name = path.relative_to(root).as_posix()
        if path.is_symlink():
            raise ValueError("publication symlinks are forbidden")
        if path.is_dir() and name in allowed_dirs:
            continue
        if not path.is_file() or name not in expected:
            raise ValueError("undeclared publication path")
        actual.add(name)
        if len(actual) > MAX_FILES:
            raise ValueError("too many publication files")
    if actual != expected:
        raise ValueError("publication inventory is incomplete")
    total = 0
    for name, digest in files.items():
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ValueError("invalid approved file digest")
        limit = MAX_FILE_BYTES if name in member_paths[1:] else MAX_META_BYTES
        data = _read(root / name, limit)
        total += len(data)
        if total > MAX_TOTAL_BYTES:
            raise ValueError("publication exceeds total size limit")
        if hashlib.sha256(data).hexdigest() != digest:
            raise ValueError(f"reviewed bytes changed: {name}")
        if name in {"NOTICE.md", *licenses} and not data.strip():
            raise ValueError("empty attribution or license document")
    provenance = _json(_read(root / "PROVENANCE.json", MAX_META_BYTES))
    records = provenance.get("files")
    if provenance.get("publication_profile") != PROFILE or not isinstance(records, dict) or set(records) != set(member_paths):
        raise ValueError("provenance must cover the catalog text and every base image exactly")
    for name, record in records.items():
        if not isinstance(record, dict) or record.get("redistribution_verified") is not True:
            raise ValueError(f"redistribution is unverified: {name}")
        if record.get("rights_basis") not in BASE_RIGHTS or record.get("license_file") not in licenses:
            raise ValueError(f"missing asset-specific rights basis: {name}")
        if not _https(record.get("source_url")) or not _https(record.get("evidence_url")):
            raise ValueError(f"missing source or permission evidence: {name}")
        if not all(isinstance(record.get(key), str) and record[key].strip() for key in ("author", "review_note")):
            raise ValueError(f"missing attribution or review note: {name}")
    return {"publication_profile": PROFILE, "manifest_sha256": manifest_hash, "review_url": review["review_url"], "approved_files": len(files)}
