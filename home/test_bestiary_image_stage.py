"""Focused tests for reviewed, checksum-bound local image staging."""

import hashlib
from io import BytesIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase
from PIL import Image

from home.bestiary_image_stage import git_blob_sha


class ImageStageTests(SimpleTestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        image = Image.new('RGB', (400, 200), '#b13b21')
        buffer = BytesIO()
        image.save(buffer, format='PNG')
        self.data = buffer.getvalue()
        self.sha = git_blob_sha(self.data)
        self.blobs = self.root / 'blobs'
        self.blobs.mkdir()
        (self.blobs / self.sha).write_bytes(self.data)
        self.preview = self.root / 'preview.json'
        self.preview.write_text(json.dumps({'records': [{'pk': 7, 'slug': 'dragao-de-teste',
            'status': 'candidate_exact', 'candidates': [{'sha': self.sha,
                'path': 'bestiary/XMM/Dragon.png'}]}]}), encoding='utf-8')
        self.selection = self.root / 'selection.json'
        self.selection_data = {'preview_sha256': hashlib.sha256(self.preview.read_bytes()).hexdigest(),
            'items': [{'slug': 'dragao-de-teste', 'source_sha': self.sha,
                'usage_basis': 'Arte própria autorizada', 'reviewer': 'QA local',
                'attribution': 'Equipe de teste'}]}
        self.selection.write_text(json.dumps(self.selection_data), encoding='utf-8')
        self.output = self.root / 'staged'

    def run_stage(self, report):
        call_command('preparar_imagens_bestiario', preview=str(self.preview),
                     selection=str(self.selection), blobs=str(self.blobs),
                     output_dir=str(self.output), report=str(self.root / report))

    def test_stages_and_resumes_exact_reviewed_image(self):
        self.run_stage('first.json')
        staged = json.loads((self.root / 'first.json').read_text())['staged'][0]
        self.assertEqual(Path(staged['original']).read_bytes(), self.data)
        with Image.open(staged['thumbnail']) as thumb:
            self.assertEqual(thumb.format, 'WEBP')
            self.assertLessEqual(max(thumb.size), 320)
        (self.blobs / self.sha).unlink()
        self.run_stage('second.json')
        self.assertEqual(json.loads((self.root / 'second.json').read_text())['staged'], [staged])

    def test_rejects_changed_preview_and_unreviewed_source(self):
        self.selection_data['preview_sha256'] = '0' * 64
        self.selection.write_text(json.dumps(self.selection_data), encoding='utf-8')
        with self.assertRaises(CommandError):
            self.run_stage('bad-hash.json')
        self.assertFalse(self.output.exists())
        self.selection_data['preview_sha256'] = hashlib.sha256(self.preview.read_bytes()).hexdigest()
        self.selection_data['items'][0]['usage_basis'] = ''
        self.selection.write_text(json.dumps(self.selection_data), encoding='utf-8')
        with self.assertRaises(CommandError):
            self.run_stage('bad-rights.json')
        self.assertFalse(self.output.exists())
