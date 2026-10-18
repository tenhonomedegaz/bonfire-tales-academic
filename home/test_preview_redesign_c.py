"""Read-only G01-C preview keeps unverifiable historical levels visible for review."""

from io import StringIO
import json

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TransactionTestCase
from django.utils import timezone

from .models import TbEventoConquista, TbPersonagem, TbUsuarioConquista


class PreviewRedesignCTests(TransactionTestCase):
    def test_deleted_character_and_missing_revision_are_reported_without_grant(self):
        owner = get_user_model().objects.create_user('c-preview-owner')
        character = TbPersonagem.objects.create(dono=owner, nome='Histórica', nivel=13)
        remaining = TbPersonagem.objects.create(dono=owner, nome='Atual', nivel=9)
        deleted = TbEventoConquista.objects.create(
            origem='site', chave_origem='deleted-character-level-13',
            tipo='character_level_up', conta=owner, personagem=character,
            agregado_id=100001, ocorrido_em=timezone.now(),
            payload_json={'level_after': 13},
        )
        missing_revision = TbEventoConquista.objects.create(
            origem='site', chave_origem='missing-revision-level-9',
            tipo='character_level_up', conta=owner, personagem=remaining,
            agregado_id=100002, ocorrido_em=timezone.now(),
            payload_json={'level_after': 9},
        )
        character.delete()
        deleted.refresh_from_db()
        self.assertIsNone(deleted.personagem_id)

        output = StringIO()
        call_command('preview_redesign_c', stdout=output)
        account = json.loads(output.getvalue())['accounts'][0]
        self.assertTrue(account['current_level_9_candidate'])
        self.assertFalse(account['current_level_13_candidate'])
        self.assertFalse(account['proven_level_13'])
        self.assertCountEqual(account['level_events_needing_review'], [
            {'event_id': str(deleted.pk), 'level': 13, 'reason': 'character_missing'},
            {'event_id': str(missing_revision.pk), 'level': 9,
             'reason': 'revision_missing'},
        ])
        self.assertEqual(TbEventoConquista.objects.count(), 2)
        self.assertFalse(TbUsuarioConquista.objects.exists())
