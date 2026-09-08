"""Source-service-shaped synthetic fixtures, never real publication approvals."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from publication_policy import DEFAULT_APPROVALS, PRIMARY, PROFILE, validate_publication
from snapshot_protocol import CLIENT, digest, validate_manifest
from validate_snapshot import validate


def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


class PublicationPolicyTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.root = self.base / "candidate"
        (self.root / "images").mkdir(parents=True)
        (self.root / "LICENSES").mkdir()
        # Fixture content is synthetic; byte integrity is tested, not image decoding.
        self.catalog = [{"id": "test-pig", "name": "Synthetic pig", "description": "Fixture", "analysis": "Unit test only."}]
        self.provenance = {"resource_count": 1, "items": [{"id": "test-pig", "source": "synthetic fixture", "classification": "test-only"}]}
        (self.root / "images/test-pig.png").write_bytes(b"synthetic-test-image")
        (self.root / "NOTICE.md").write_text("Synthetic test attribution.", encoding="utf-8")
        (self.root / "LICENSES/test.txt").write_text("Synthetic unit-test license, not real evidence.", encoding="utf-8")
        self.policy_path = self.base / "approvals.json"
        self.refresh()

    def refresh(self):
        write_json(self.root / "pig.json", self.catalog)
        write_json(self.root / "PROVENANCE.json", self.provenance)

        def member(name):
            data = (self.root / name).read_bytes()
            return {"path": name, "size": len(data), "sha256": digest(data)}

        self.manifest = {"schema_version": 1, "client": CLIENT, "resource_version": "synthetic-test",
                         "generated_at": "2026-09-08T00:00:00+00:00", "profile": PROFILE,
                         "pig_count": 1, "pig_json": member("pig.json"),
                         "images": [member("images/test-pig.png")], "notice": member("NOTICE.md"),
                         "provenance": member("PROVENANCE.json"), "licenses": [member("LICENSES/test.txt")]}
        self.manifest["package_size"] = sum(self.manifest[key]["size"] for key in ("pig_json", "notice", "provenance")) + sum(item["size"] for key in ("images", "licenses") for item in self.manifest[key])
        self.seal()

    def seal(self):
        write_json(self.root / "manifest.json", self.manifest)
        self.hash = digest((self.root / "manifest.json").read_bytes())
        self.review = {"status": "approved", "profile": PROFILE, "primary_manifest_url": PRIMARY,
                       "review_url": "https://example.invalid/synthetic-review",
                       "files": {p.relative_to(self.root).as_posix(): digest(p.read_bytes()) for p in self.root.rglob("*") if p.is_file()},
                       "rights": {name: {"redistribution_verified": True, "rights_basis": "original-work",
                                          "author": "Synthetic fixture author", "source_url": "https://example.invalid/source",
                                          "evidence_url": "https://example.invalid/permission", "license_file": "LICENSES/test.txt",
                                          "review_note": "Synthetic test only, not publication permission."}
                                  for name in ("pig.json", "images/test-pig.png")}}
        self.policy = {"schema_version": 2, "approved_snapshots": {self.hash: self.review}}
        self.save_policy()

    def save_policy(self):
        write_json(self.policy_path, self.policy)

    def check(self):
        return validate(self.root, self.policy_path)

    def test_service_shape_includes_all_attribution_in_package_size(self):
        result = self.check()
        self.assertEqual(result["members"], 5)
        self.assertEqual(result["approved_files"], 6)
        self.assertEqual(result["publication_profile"], PROFILE)
        raw = (self.root / "manifest.json").read_bytes()
        self.assertEqual(validate_manifest(raw)[0]["package_size"], result["package_size"])

    def test_candidate_bytes_are_never_rewritten(self):
        before = {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        self.check()
        self.assertEqual(before, {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob("*") if p.is_file()})

    def test_repository_approval_list_remains_empty(self):
        policy = json.loads(DEFAULT_APPROVALS.read_text(encoding="utf-8"))
        self.assertEqual(policy, {"schema_version": 2, "approved_snapshots": {}})
        with self.assertRaisesRegex(ValueError, "no separately reviewed"):
            validate_publication(self.root)

    def test_empty_policy_rejects_every_snapshot(self):
        self.policy["approved_snapshots"] = {}
        self.save_policy()
        with self.assertRaisesRegex(ValueError, "no separately reviewed"):
            self.check()

    def test_old_manifest_cannot_reuse_an_approval(self):
        self.manifest["resource_version"] = "not-reviewed"
        write_json(self.root / "manifest.json", self.manifest)
        with self.assertRaisesRegex(ValueError, "no separately reviewed"):
            self.check()

    def test_pending_and_revoked_reviews_are_rejected(self):
        for state in ("pending", "revoked", "not_published"):
            with self.subTest(state=state):
                self.review["status"] = state
                self.save_policy()
                with self.assertRaises(ValueError):
                    self.check()

    def test_changed_image_license_and_notice_are_rejected(self):
        for name in ("images/test-pig.png", "LICENSES/test.txt", "NOTICE.md"):
            with self.subTest(name=name):
                original = (self.root / name).read_bytes()
                (self.root / name).write_bytes(b"changed")
                with self.assertRaisesRegex(ValueError, "reviewed bytes changed"):
                    self.check()
                (self.root / name).write_bytes(original)

    def test_each_validation_rechecks_unchanged_manifest_members(self):
        self.check()
        (self.root / "images/test-pig.png").write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "reviewed bytes changed"):
            self.check()

    def test_approval_does_not_replace_protocol_hashes(self):
        path = self.root / "images/test-pig.png"
        path.write_bytes(b"x" * len(path.read_bytes()))
        self.seal()
        with self.assertRaisesRegex(ValueError, "protocol size/sha256 mismatch"):
            self.check()

    def test_package_size_must_include_attribution(self):
        self.manifest["package_size"] = self.manifest["pig_json"]["size"] + self.manifest["images"][0]["size"]
        self.seal()
        with self.assertRaisesRegex(ValueError, "package_size must include"):
            self.check()

    def test_profile_alias_is_not_accepted(self):
        self.manifest["publication_profile"] = self.manifest.pop("profile")
        self.seal()
        with self.assertRaises(ValueError):
            self.check()

    def test_extended_and_unknown_manifest_fields_rejected(self):
        original = copy.deepcopy(self.manifest)
        for key in ("ex_variants", "variant_images", "roast_copy", "compatibility_floor", "unknown"):
            with self.subTest(key=key):
                self.manifest = {**original, key: {}}
                self.seal()
                with self.assertRaisesRegex(ValueError, "unexpected fields"):
                    self.check()

    def test_unlisted_private_file_is_rejected(self):
        (self.root / "private.token").write_bytes(b"synthetic")
        with self.assertRaisesRegex(ValueError, "undeclared"):
            self.check()

    def test_extra_files_rejected_even_if_reviewed(self):
        (self.root / "roast_copy.json").write_bytes(b"{}")
        self.seal()
        with self.assertRaisesRegex(ValueError, "forbidden/unexpected"):
            self.check()

    def test_every_asset_needs_independent_permission_evidence(self):
        for name in ("pig.json", "images/test-pig.png"):
            with self.subTest(name=name):
                self.review["rights"][name]["evidence_url"] = ""
                self.save_policy()
                with self.assertRaisesRegex(ValueError, "permission evidence"):
                    self.check()
                self.review["rights"][name]["evidence_url"] = "https://example.invalid/evidence"

    def test_provenance_labels_are_not_independent_rights_approval(self):
        del self.review["rights"]["pig.json"]
        self.save_policy()
        with self.assertRaisesRegex(ValueError, "independent rights review"):
            self.check()

    def test_unverified_redistribution_is_rejected(self):
        self.review["rights"]["images/test-pig.png"]["redistribution_verified"] = False
        self.save_policy()
        with self.assertRaisesRegex(ValueError, "unverified"):
            self.check()

    def test_non_primary_publication_is_rejected(self):
        self.review["primary_manifest_url"] = "https://example.invalid/other"
        self.save_policy()
        with self.assertRaisesRegex(ValueError, "audited primary"):
            self.check()

    def test_symlink_is_rejected(self):
        (self.root / "images/link.png").symlink_to(self.root / "images/test-pig.png")
        with self.assertRaisesRegex(ValueError, "symlinks"):
            self.check()

    def test_traversal_is_rejected(self):
        self.review["files"]["../secret"] = "0" * 64
        self.save_policy()
        with self.assertRaisesRegex(ValueError, "non-canonical"):
            self.check()

    def test_missing_rights_document_is_rejected(self):
        (self.root / "NOTICE.md").unlink()
        with self.assertRaisesRegex(ValueError, "incomplete"):
            self.check()

    def test_duplicate_json_keys_are_rejected(self):
        self.policy_path.write_text('{"schema_version":2,"schema_version":2,"approved_snapshots":{}}', encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "duplicate JSON key"):
            self.check()

    def test_provenance_covers_catalog_ids_not_a_synthetic_files_schema(self):
        self.provenance = {"files": {}, "publication_profile": PROFILE}
        self.refresh()
        with self.assertRaisesRegex(ValueError, "resource_count and items"):
            self.check()

    def test_missing_duplicate_and_foreign_provenance_ids_rejected(self):
        item = copy.deepcopy(self.provenance["items"][0])
        for rows in ([], [item, item], [{**item, "id": "another-pig"}]):
            with self.subTest(rows=rows):
                self.provenance["items"] = rows
                self.refresh()
                with self.assertRaises(ValueError):
                    self.check()

    def test_catalog_and_image_id_mismatch_rejected(self):
        self.catalog[0]["id"] = "another-pig"
        self.refresh()
        with self.assertRaisesRegex(ValueError, "image IDs"):
            self.check()

    def test_wrong_type_counts_rejected(self):
        for key in ("schema_version", "pig_count", "package_size"):
            with self.subTest(key=key):
                self.refresh()
                self.manifest[key] = True
                self.seal()
                with self.assertRaises(ValueError):
                    self.check()

    def test_unsafe_and_duplicate_member_paths_rejected(self):
        for path in ("images//test-pig.png", "images/../test-pig.png", "images/test-pig.png?secret", "images/%2e%2e.png"):
            with self.subTest(path=path):
                self.refresh()
                self.manifest["images"][0]["path"] = path
                self.seal()
                with self.assertRaises(ValueError):
                    self.check()

    def test_duplicate_license_descriptor_rejected(self):
        self.manifest["licenses"] *= 2
        self.seal()
        with self.assertRaisesRegex(ValueError, "duplicate"):
            self.check()

    def health(self):
        return {"status": "ok", "client": CLIENT, "protocol_version": 1,
                "resource_version": self.manifest["resource_version"], "profile": PROFILE,
                "pig_count": 1, "package_size": self.manifest["package_size"],
                "generated_at": self.manifest["generated_at"],
                "attribution_bundle": True, "extended_resources": False}

    def test_optional_service_health_is_pinned_outside_package_size(self):
        health = self.health()
        write_json(self.root / "health.json", health)
        self.seal()
        result = self.check()
        self.assertEqual(result["approved_files"], 7)
        self.assertEqual(result["members"], 5)
        self.assertEqual(result["package_size"], health["package_size"])

    def test_health_cannot_claim_different_version_or_extensions(self):
        health = self.health()
        for change in ({"resource_version": "stale"}, {"extended_resources": True}, {"pig_count": True}):
            with self.subTest(change=change):
                write_json(self.root / "health.json", {**health, **change})
                self.seal()
                with self.assertRaisesRegex(ValueError, "health metadata"):
                    self.check()

    def test_read_errors_fail_closed(self):
        with patch("publication_policy._read", side_effect=PermissionError("synthetic")):
            with self.assertRaises(PermissionError):
                self.check()

    def test_no_validation_network_dependency(self):
        import urllib.request
        with patch.object(urllib.request, "urlopen", side_effect=AssertionError("network must not be used")):
            self.check()


if __name__ == "__main__":
    unittest.main()
