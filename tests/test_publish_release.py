import hashlib
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.publish_release import publish


class PublishTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / 'frontend').mkdir()
        (self.root / 'frontend/package.json').write_text('{"version":"0.1.0"}', encoding='utf-8')
        (self.root / 'CHANGELOG.md').write_text('# 更新记录\n\n## 0.1.0\n\n新增便携版\n\n## 0.0.1\n\n旧记录', encoding='utf-8')
        self.output = self.root / 'release/output'
        self.output.mkdir(parents=True)
        archive = self.output / 'infNote-v0.1.0-windows-x64.zip'
        archive.write_bytes(b'test archive')
        archive.with_suffix('.sha256').write_text(hashlib.sha256(archive.read_bytes()).hexdigest() + '  ' + archive.name, encoding='utf-8')

    def tearDown(self):
        self.temp.cleanup()

    @patch('scripts.publish_release.subprocess.run')
    def test_create_then_publish_with_assets(self, run):
        run.side_effect = [subprocess.CompletedProcess([], 1), subprocess.CompletedProcess([], 0), subprocess.CompletedProcess([], 0)]
        publish(self.root, 'v0.1.0')
        create = run.call_args_list[1].args[0]
        self.assertEqual(create[:3], ['gh', 'release', 'create'])
        self.assertIn('--draft', create)
        self.assertIn('--verify-tag', create)
        self.assertTrue(any(arg.endswith('.zip') for arg in create))
        self.assertTrue(any(arg.endswith('.sha256') for arg in create))
        self.assertIn('--draft=false', run.call_args_list[2].args[0])
        notes = (self.output / 'release-notes.md').read_text('utf-8')
        self.assertIn('新增便携版', notes)
        self.assertNotIn('旧记录', notes)

    @patch('scripts.publish_release.subprocess.run')
    def test_failed_asset_upload_never_publishes(self, run):
        run.side_effect = [subprocess.CompletedProcess([], 0, stdout=json.dumps({'isDraft': True})), subprocess.CalledProcessError(1, 'gh')]
        with self.assertRaises(subprocess.CalledProcessError):
            publish(self.root, 'v0.1.0')
        self.assertEqual(run.call_count, 2)

    @patch('scripts.publish_release.subprocess.run')
    def test_already_published_is_not_overwritten(self, run):
        run.return_value = subprocess.CompletedProcess([], 0, stdout=json.dumps({'isDraft': False}))
        publish(self.root, 'v0.1.0')
        self.assertEqual(run.call_count, 1)

    @patch('scripts.publish_release.subprocess.run')
    def test_wrong_tag_or_checksum_rejected_before_network(self, run):
        with self.assertRaises(ValueError):
            publish(self.root, 'v0.2.0')
        (self.output / 'infNote-v0.1.0-windows-x64.zip').write_bytes(b'corrupt')
        with self.assertRaises(ValueError):
            publish(self.root, 'v0.1.0')
        run.assert_not_called()
