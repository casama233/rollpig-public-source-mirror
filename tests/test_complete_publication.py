import copy
import json
from pathlib import Path
from unittest.mock import patch

import unittest
import test_publication_policy as fixture

write_json = fixture.write_json
from snapshot_protocol import BINDING_FIELDS, COMPLETE_PROFILE, digest
from build_publication import build
from revoke_snapshot import revoke
from sync_primary import sync
from publication_policy import PRIMARY


class CompletePublicationTests(unittest.TestCase):
    setUp = fixture.PublicationPolicyTests.setUp
    refresh = fixture.PublicationPolicyTests.refresh
    seal = fixture.PublicationPolicyTests.seal
    save_policy = fixture.PublicationPolicyTests.save_policy
    check = fixture.PublicationPolicyTests.check
    def make_complete(self):
        self.manifest.update({
            'profile': COMPLETE_PROFILE, 'extended_resources': True,
            'handwritten_ex_pig_count': 1, 'handwritten_ex_level_count': 5,
            'ex_variant_pig_count': 1, 'variant_images': [],
            'roast_copy_dish_count': 1, 'roast_copy_line_count': 1,
            **{key: 'a' * 64 for key in BINDING_FIELDS},
        })
        authoring = {key: self.manifest[key] for key in BINDING_FIELDS | {'profile', 'pig_count', 'handwritten_ex_pig_count', 'handwritten_ex_level_count'}}
        authoring.update(publication_state='published', publication_reviewer='fixture')
        write_json(self.root / 'EX-AUTHORING.json', authoring)
        write_json(self.root / 'pig_ex_variants.json', {'schema_version': 1, 'pigs': {'test-pig': {str(i): {'description': f'fixture {i}', 'analysis': f'analysis {i}'} for i in range(1, 6)}}})
        write_json(self.root / 'roast_copy.json', {'schema_version': 1, 'dish_names': ['dish'], 'lines': ['line']})
        for key, name in [('ex_authoring', 'EX-AUTHORING.json'), ('ex_variants', 'pig_ex_variants.json'), ('roast_copy', 'roast_copy.json')]:
            raw = (self.root / name).read_bytes()
            self.manifest[key] = {'path': name, 'size': len(raw), 'sha256': digest(raw)}
        self.manifest['package_size'] = sum(item['size'] for key, item in self.manifest.items() if isinstance(item, dict) and 'size' in item) + sum(item['size'] for key in ['images', 'licenses'] for item in self.manifest[key])
        self.seal()
        self.review['profile'] = COMPLETE_PROFILE
        for name in ['pig_ex_variants.json', 'roast_copy.json']:
            self.review['rights'][name] = copy.deepcopy(self.review['rights']['pig.json'])
        self.save_policy()

    def test_complete_profile_retains_every_reviewed_member(self):
        self.make_complete()
        self.assertEqual(self.check()['publication_profile'], COMPLETE_PROFILE)
        self.assertEqual(self.check()['approved_files'], 9)

    def test_complete_text_rights_are_required(self):
        self.make_complete()
        del self.review['rights']['pig_ex_variants.json']
        self.save_policy()
        with self.assertRaisesRegex(ValueError, 'independent rights review'):
            self.check()

    def test_source_authoring_approval_alone_is_not_published(self):
        self.make_complete()
        path = self.root / 'EX-AUTHORING.json'
        data = json.loads(path.read_text())
        data['publication_state'] = 'not_approved'
        write_json(path, data)
        with self.assertRaises(ValueError):
            self.check()

    def test_extra_ex_image_is_not_approved(self):
        self.make_complete()
        (self.root / 'ex_variants').mkdir()
        (self.root / 'ex_variants/extra.png').write_bytes(b'extra')
        with self.assertRaisesRegex(ValueError, 'undeclared'):
            self.check()

    def test_offline_build_and_revocation_remove_all_served_assets(self):
        self.make_complete()
        repo = self.base / 'repository'
        (repo / 'public').mkdir(parents=True)
        (repo / 'public/NOTICE.txt').write_text('notice')
        self.root.rename(repo / 'public/v1')
        self.policy_path.rename(repo / 'publication-approvals.json')
        self.assertEqual(build(repo, self.base / 'dist')['approved_files'], 9)
        self.assertTrue((self.base / 'dist/v1/images/test-pig.png').is_file())
        revoke(repo, self.hash)
        self.assertFalse((repo / 'public/v1').exists())
        self.assertEqual(build(repo, self.base / 'dist')['status'], 'withdrawn')
        self.assertFalse((self.base / 'dist/v1').exists())

    def test_refresh_downloads_all_attribution_and_has_no_version_shortcut(self):
        self.make_complete()
        target = self.base / 'download/v1'
        def fetch(url, limit, timeout):
            return (self.root / url.rsplit('/v1/', 1)[-1]).read_bytes()
        with patch('sync_primary.fetch', fetch):
            sync(PRIMARY, target, approvals_path=self.policy_path)
            (target / 'NOTICE.md').write_text('corrupt')
            sync(PRIMARY, target, approvals_path=self.policy_path)
        self.assertEqual((target / 'NOTICE.md').read_bytes(), (self.root / 'NOTICE.md').read_bytes())
        self.assertEqual((target / 'EX-AUTHORING.json').read_bytes(), (self.root / 'EX-AUTHORING.json').read_bytes())

    def test_revocation_during_download_never_activates(self):
        self.make_complete()
        target = self.base / 'download/v1'
        def fetch(url, limit, timeout):
            if not url.endswith('manifest.json'):
                self.review['status'] = 'revoked'
                self.save_policy()
            return (self.root / url.rsplit('/v1/', 1)[-1]).read_bytes()
        with patch('sync_primary.fetch', fetch), self.assertRaisesRegex(ValueError, 'no separately reviewed'):
            sync(PRIMARY, target, approvals_path=self.policy_path)
        self.assertFalse(target.exists())
