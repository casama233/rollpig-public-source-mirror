"""Synthetic fixtures only: these tests contain no upstream artwork or prose."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from publication_policy import PROFILE, PRIMARY, validate_publication


def digest(data):
    return hashlib.sha256(data).hexdigest()


def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


class PublicationPolicyTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.root = self.base / "candidate"
        (self.root / "images").mkdir(parents=True)
        (self.root / "LICENSES").mkdir()
        (self.root / "pig.json").write_bytes(b'[{"id":"synthetic"}]')
        (self.root / "images/test.png").write_bytes(b"synthetic-test-image-not-for-publication")
        (self.root / "NOTICE.md").write_text("Synthetic test attribution only.", encoding="utf-8")
        (self.root / "LICENSES/test.txt").write_text("Synthetic test license fixture only.", encoding="utf-8")
        def member(name):
            data = (self.root / name).read_bytes()
            return {"path": name, "size": len(data), "sha256": digest(data)}
        self.manifest = {"schema_version": 1, "client": "astrbot_plugin_rollpig_plus", "resource_version": "synthetic-test", "publication_profile": PROFILE, "pig_json": member("pig.json"), "images": [member("images/test.png")]}
        self.manifest["package_size"] = self.manifest["pig_json"]["size"] + self.manifest["images"][0]["size"]
        self.provenance = {"publication_profile": PROFILE, "files": {name: {"author": "Synthetic test author", "rights_basis": "original-work", "redistribution_verified": True, "license_file": "LICENSES/test.txt", "source_url": "https://example.invalid/test-source", "evidence_url": "https://example.invalid/test-permission", "review_note": "Synthetic unit test, not a real rights determination."} for name in ("pig.json", "images/test.png")}}
        self.policy_path = self.base / "approvals.json"
        self.seal()

    def seal(self):
        write_json(self.root / "manifest.json", self.manifest)
        write_json(self.root / "PROVENANCE.json", self.provenance)
        self.hash = digest((self.root / "manifest.json").read_bytes())
        self.review = {"status": "approved", "profile": PROFILE, "primary_manifest_url": PRIMARY, "review_url": "https://example.invalid/test-review", "files": {p.relative_to(self.root).as_posix(): digest(p.read_bytes()) for p in self.root.rglob("*") if p.is_file()}}
        self.policy = {"schema_version": 1, "approved_snapshots": {self.hash: self.review}}
        write_json(self.policy_path, self.policy)

    def check(self):
        return validate_publication(self.root, self.policy_path)

    def test_complete_reviewed_fixture(self):
        self.assertEqual(self.check()["approved_files"], 6)

    def test_empty_policy_rejects_all_snapshots(self):
        write_json(self.policy_path, {"schema_version": 1, "approved_snapshots": {}})
        with self.assertRaisesRegex(ValueError, "no separately reviewed"):
            self.check()

    def test_old_manifest_cannot_reuse_a_different_approval(self):
        self.manifest["resource_version"] = "unreviewed-new-version"
        write_json(self.root / "manifest.json", self.manifest)
        with self.assertRaisesRegex(ValueError, "no separately reviewed"):
            self.check()

    def test_pending_and_revoked_approvals_are_rejected(self):
        for state in ("pending", "revoked", "not_published"):
            with self.subTest(state=state):
                self.review["status"] = state
                write_json(self.policy_path, self.policy)
                with self.assertRaises(ValueError):
                    self.check()

    def test_changed_image_and_license_are_rejected(self):
        for name in ("images/test.png", "LICENSES/test.txt"):
            with self.subTest(name=name):
                original = (self.root / name).read_bytes()
                (self.root / name).write_bytes(b"changed")
                with self.assertRaisesRegex(ValueError, "reviewed bytes changed"):
                    self.check()
                (self.root / name).write_bytes(original)

    def test_unlisted_private_file_is_rejected(self):
        (self.root / "private.token").write_bytes(b"synthetic")
        with self.assertRaisesRegex(ValueError, "undeclared"):
            self.check()

    def test_manifest_extensions_rejected_even_when_resealed(self):
        self.manifest["ex_variants"] = {"path": "pig_ex_variants.json"}
        self.seal()
        with self.assertRaisesRegex(ValueError, "extension payloads"):
            self.check()

    def test_extra_files_rejected_even_when_approved(self):
        (self.root / "roast_copy.json").write_bytes(b"{}")
        self.seal()
        with self.assertRaisesRegex(ValueError, "forbidden/unexpected"):
            self.check()

    def test_all_assets_need_evidence_including_catalog_text(self):
        for name in ("pig.json", "images/test.png"):
            with self.subTest(name=name):
                self.provenance["files"][name]["evidence_url"] = ""
                self.seal()
                with self.assertRaisesRegex(ValueError, "permission evidence"):
                    self.check()
                self.provenance["files"][name]["evidence_url"] = "https://example.invalid/test-permission"

    def test_source_code_license_does_not_replace_asset_review(self):
        self.provenance["files"]["images/test.png"]["redistribution_verified"] = False
        self.seal()
        with self.assertRaisesRegex(ValueError, "unverified"):
            self.check()

    def test_non_primary_publication_cannot_be_approved(self):
        self.review["primary_manifest_url"] = "https://example.invalid/unrelated-source"
        write_json(self.policy_path, self.policy)
        with self.assertRaisesRegex(ValueError, "audited primary"):
            self.check()

    def test_symlink_is_rejected(self):
        (self.root / "images/link.png").symlink_to(self.root / "images/test.png")
        with self.assertRaisesRegex(ValueError, "symlinks"):
            self.check()

    def test_traversal_is_rejected(self):
        self.review["files"]["../secret"] = "0" * 64
        write_json(self.policy_path, self.policy)
        with self.assertRaisesRegex(ValueError, "non-canonical"):
            self.check()

    def test_missing_rights_document_is_rejected(self):
        (self.root / "NOTICE.md").unlink()
        with self.assertRaisesRegex(ValueError, "incomplete"):
            self.check()

    def test_duplicate_json_keys_are_rejected(self):
        self.policy_path.write_text('{"schema_version":1,"schema_version":1,"approved_snapshots":{}}', encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "duplicate JSON key"):
            self.check()

    def test_snapshot_validator_composes_rights_and_protocol_checks(self):
        from validate_snapshot import validate
        result = validate(self.root, self.policy_path)
        self.assertEqual(result["members"], 2)
        self.assertEqual(result["publication_profile"], PROFILE)

    def test_snapshot_validator_rejects_hash_only_legacy_snapshot(self):
        from validate_snapshot import validate
        write_json(self.policy_path, {"schema_version": 1, "approved_snapshots": {}})
        with self.assertRaisesRegex(ValueError, "no separately reviewed"):
            validate(self.root, self.policy_path)

    def test_approval_does_not_replace_protocol_integrity(self):
        from validate_snapshot import validate
        image = self.root / "images/test.png"
        image.write_bytes(b"x" * len(image.read_bytes()))
        self.seal()
        with self.assertRaisesRegex(ValueError, "sha256 mismatch"):
            validate(self.root, self.policy_path)


if __name__ == "__main__":
    unittest.main()
