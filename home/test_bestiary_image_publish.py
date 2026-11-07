"""Isolated database and storage coverage for reviewed image binding."""

import hashlib
from io import BytesIO
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from django.core.management import call_command
from django.test import TestCase, override_settings
from PIL import Image

from home.bestiary_image_publish import ImagePublicationError, publication_plan, publish_images
from home.bestiary_image_stage import git_blob_sha, stage_images
from home.models import TbBestiario


class ImagePublicationTests(TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.media = Path(self.temp.name) / 'media'
        self.stage = Path(self.temp.name) / 'stage'
        self.stage.mkdir()
        self.settings_override = override_settings(MEDIA_ROOT=self.media)
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)
        self.creature = TbBestiario.objects.create(nome='Dragão de teste', slug='dragao-de-teste')
        image = Image.new('RGB', (32, 32), '#b13b21')
        output = BytesIO()
        image.save(output, format='WEBP')
        self.data = output.getvalue()
        self.original = self.stage / 'prepared-original.webp'
        self.original.write_bytes(self.data)
        self.thumb = self.stage / 'prepared-thumb.webp'
        self.thumb.write_bytes(self.data)
        self.sha = git_blob_sha(self.data)
        self.report = {'staged': [{
            'pk': self.creature.pk, 'slug': self.creature.slug,
            'source_blob_sha': self.sha, 'original': str(self.original),
            'original_sha256': hashlib.sha256(self.data).hexdigest(),
            'thumbnail': str(self.thumb),
            'thumbnail_sha256': hashlib.sha256(self.data).hexdigest(),
            'usage_basis': 'Arte original de teste', 'reviewer': 'QA local',
            'attribution': 'Equipe de teste',
        }]}

    def test_preview_apply_and_repeat_without_overwriting_art(self):
        plan = publication_plan(self.report, self.stage)
        self.assertFalse(self.media.exists())
        self.creature.refresh_from_db()
        self.assertFalse(self.creature.imagem_url)
        applied = publish_images(self.report, self.stage)
        self.creature.refresh_from_db()
        self.assertEqual(self.creature.imagem_url, applied[0]['url'])
        self.assertEqual((self.media / plan[0]['storage_name']).read_bytes(), self.data)
        self.assertTrue(publish_images(self.report, self.stage)[0]['already_linked'])
        self.creature.imagem_url = '/media/bestiario/arte-propria.webp'
        self.creature.save(update_fields=['imagem_url'])
        with self.assertRaises(ImagePublicationError):
            publish_images(self.report, self.stage)
        self.creature.refresh_from_db()
        self.assertEqual(self.creature.imagem_url, '/media/bestiario/arte-propria.webp')

    def test_rejects_community_and_modified_thumbnail(self):
        self.creature.comunidade = True
        self.creature.save(update_fields=['comunidade'])
        with self.assertRaises(ImagePublicationError):
            publication_plan(self.report, self.stage)
        self.creature.comunidade = False
        self.creature.save(update_fields=['comunidade'])
        self.thumb.write_bytes(b'changed')
        with self.assertRaises(ImagePublicationError):
            publication_plan(self.report, self.stage)

    def test_rejects_modified_source_blob(self):
        self.original.write_bytes(b'changed')
        with self.assertRaises(ImagePublicationError):
            publication_plan(self.report, self.stage)

    def test_reviewed_source_to_local_media_and_catalog(self):
        source = BytesIO()
        Image.new('RGB', (400, 240), '#317ca4').save(source, format='PNG')
        source_bytes = source.getvalue()
        sha = git_blob_sha(source_bytes)
        preview = {'records': [{'pk': self.creature.pk, 'slug': self.creature.slug,
                    'status': 'candidate_exact', 'candidates': [
                        {'sha': sha, 'path': 'bestiary/XMM/Test.png'}]}]}
        selection = {'items': [{'slug': self.creature.slug, 'source_sha': sha,
                     'usage_basis': 'Arte original de teste', 'reviewer': 'QA local',
                     'attribution': 'Equipe de teste'}]}
        staged = stage_images(preview, selection, self.stage, lambda _: source_bytes)
        linked = publish_images({'staged': staged}, self.stage)
        self.creature.refresh_from_db()
        self.assertEqual(self.creature.imagem_url, linked[0]['url'])
        self.assertTrue((self.media / f'bestiario/{sha}-thumb.webp').is_file())

    def test_command_defaults_to_preview(self):
        report_path = self.stage / 'report.json'
        report_path.write_text(json.dumps(self.report), encoding='utf-8')
        output = StringIO()
        call_command('publicar_imagens_bestiario', report=str(report_path),
                     stage_dir=str(self.stage), stdout=output)
        self.assertEqual(json.loads(output.getvalue())['mode'], 'preview')
        self.creature.refresh_from_db()
        self.assertFalse(self.creature.imagem_url)
        self.assertFalse(self.media.exists())
