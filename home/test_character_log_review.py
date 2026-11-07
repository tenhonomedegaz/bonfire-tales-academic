"""Focused evidence-review tests; synthetic sources and SQLite memory only."""
import os
import sys
import unittest

ISOLATED = __name__ == '__main__' and '--isolated' in sys.argv
if ISOLATED:
    os.environ['DJANGO_SECRET_KEY'] = 'isolated-history-review'
    os.environ['POSTGRES_URL'] = 'postgresql://unused:unused@127.0.0.1:1/unused'
    os.environ['DJANGO_SETTINGS_MODULE'] = 'bonfire.settings'
    from bonfire import settings as config
    config.DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':memory:'}}
    config.PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']
    config.ALLOWED_HOSTS = ['testserver']
    import django
    django.setup()

from django.apps import apps
from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connection
from django.test import TestCase
from django.utils import timezone

from .character_log_models import CharacterHistoryMission, CharacterLogEntry, CharacterLogReview
from .character_log_import import apply_log
from .character_log_review import (entry_version, review_entry, review_queue,
                                   search_missions, search_redemptions)
from .character_log_workbook import entry_category, read_workbook
from .models import (BotQuest, BotCharacterLog, TbPersonagemAventura,
                     TbTransacaoMestre, TbPersonagem)
from .test_character_log_import import CharacterLogImportTests, GUILD, workbook


class CharacterLogReviewTests(TestCase):
    quest = CharacterLogImportTests.quest
    preview = CharacterLogImportTests.preview
    setUp = CharacterLogImportTests.setUp

    def test_historical_delivery_creates_shared_mission_and_progress_without_levelup(self):
        from types import SimpleNamespace
        from unittest.mock import patch
        from .master_legacy import import_archive
        from .test_master_legacy import sample
        from .character_history_delivery_api import history_delivery_preview, history_delivery_apply
        from .models import TbMestreLegado
        entry = self.imported('A forgotten road')
        source = entry.source
        source.metadata['history_authority'] = 'registered_staff_log'
        source.save()
        entry.observed.update(date='2026-08-30', master='Mestra Hani', adventures=12)
        entry.save()
        archive, _ = import_archive(sample(), 'delivery-fixture')
        master = archive.mestres.get(numero=49)
        master.discord_id = '323456789012345678'
        master.save()
        payload = {'source_id':source.pk, 'entry_key':entry.source_key,
            'title':'A forgotten road', 'date':'2026-08-30', 'master_number':49,
            'master_mm':600, 'mission_adventures':12, 'evidence':'Explicit approved historical evidence'}
        key = SimpleNamespace(created_by=self.admin)
        preview = history_delivery_preview(payload, key)
        from .db_access import ApiProblem
        with patch('home.master_legacy_api._backup', side_effect=OSError('backup unavailable')):
            with self.assertRaises(ApiProblem):
                history_delivery_apply({**payload,'base_version':preview['base_version']}, key)
        self.assertFalse(TbPersonagem.objects.filter(nome=source.character_name).exists())
        self.assertFalse(BotQuest.objects.filter(name=payload['title']).exists())
        self.assertEqual(TbMestreLegado.objects.get(pk=master.pk).saldo_mm,77)
        with patch('home.master_legacy_api._backup'):
            result = history_delivery_apply({**payload,'base_version':preview['base_version']}, key)
        character = TbPersonagem.objects.get(pk=result['character_id'])
        self.assertEqual((character.dono_id, character.aventuras, character.nivel), (self.owner.pk,12,1))
        self.assertEqual((character.carteira_pc, character.braseiros), (0,0))
        self.assertEqual(TbMestreLegado.objects.get(pk=master.pk).saldo_mm, 677)
        self.assertEqual(BotQuest.objects.get(pk=result['bot_quest_id']).questMaster, master.discord_id)
        self.assertEqual(source.entries.get(pk=entry.pk).reference, 'bot:'+result['bot_quest_id'])
        self.assertEqual(TbPersonagemAventura.objects.filter(id_personagem=character).count(),1)
        with self.assertRaises(ApiProblem):
            history_delivery_apply({**payload,'base_version':preview['base_version']},key)
        self.assertEqual(TbPersonagem.objects.get(pk=character.pk).aventuras,12)

    def imported(self, *titles):
        data = self.preview(workbook(titles=titles or ('Unregistered road',)))
        batch = apply_log(self.admin, data['ticket'])
        return batch.source.entries.order_by('pk').first()

    def review(self, entry, action='verify_bonus', **kwargs):
        return review_entry(self.admin, entry.pk, entry_version(entry), action,
            note='Conferido no registro original', evidence='discord-message:123456789012345678', **kwargs)

    def test_classification_never_validates_salary_fgts_or_redemption_alone(self):
        expected = {'FGTS': 'staff_bonus', 'Salario Staff': 'staff_bonus',
            'Salario Server Booster': 'server_boost', 'Nitro Boost': 'server_boost',
            'Moedas de Mestre (4 ametista)': 'mm_redemption',
            'Moeda de Evento': 'event_exchange', 'Bonus 300 tickets': 'adjustment',
            'Dragonforce': 'mission'}
        for title, category in expected.items():
            self.assertEqual(entry_category(title, 'Bonfire'), category)
        preview = self.preview(workbook(titles=tuple(expected)))
        self.assertEqual(preview['matched'], 0)
        self.assertEqual(preview['pending'], len(expected))
        batch = apply_log(self.admin, preview['ticket'])
        self.assertEqual(batch.source.entries.filter(state='pending').count(), len(expected))
        self.assertFalse(batch.source.missions.exists())

    def test_dimensionless_google_export_and_explicit_quantity_are_read(self):
        import io
        import re
        import zipfile
        original = workbook(quantity=4)
        output = io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(original)) as source, zipfile.ZipFile(output, 'w') as target:
            for item in source.infolist():
                body = source.read(item.filename)
                if item.filename.startswith('xl/worksheets/'):
                    body = re.sub(rb'<dimension[^>]*/>', b'', body)
                    body = body.replace(b'>Aventuras<', b'>Numero de Aventuras<')
                target.writestr(item, body)
        parsed = read_workbook(output.getvalue())
        self.assertEqual(len(parsed['rows']), 1)
        self.assertEqual(parsed['rows'][0]['adventures'], 4)

    def test_player_cannot_review_and_boolean_staff_does_not_grant_review(self):
        entry = self.imported('FGTS')
        self.owner.is_staff = True
        self.owner.save(update_fields=['is_staff'])
        with self.assertRaises(PermissionDenied):
            review_queue(self.owner)
        with self.assertRaises(PermissionDenied):
            review_entry(self.owner, entry.pk, entry_version(entry), 'verify_bonus')
        from django.contrib.contenttypes.models import ContentType
        content_type = ContentType.objects.get_for_model(CharacterLogEntry)
        permission, _ = Permission.objects.get_or_create(content_type=content_type,
            codename='review_character_history', defaults={'name': 'Review history'})
        self.owner.user_permissions.add(permission)
        self.owner = type(self.owner).objects.get(pk=self.owner.pk)
        self.assertEqual(review_queue(self.owner).count(), 1)

    def test_bonus_requires_evidence_and_reimport_preserves_only_unchanged_decision(self):
        entry = self.imported('FGTS')
        with self.assertRaises(ValidationError):
            review_entry(self.admin, entry.pk, entry_version(entry), 'verify_bonus',
                category='staff_bonus', note='Reviewed', evidence='')
        entry = self.review(entry, category='staff_bonus', adventures=4)
        self.assertEqual((entry.state, entry.category), ('reviewed', 'staff_bonus'))
        self.assertEqual(CharacterLogReview.objects.count(), 1)
        self.assertFalse(TbPersonagemAventura.objects.exists())
        self.assertFalse(TbTransacaoMestre.objects.exists())
        preview = self.preview(workbook(titles=('FGTS',), quantity=5))
        apply_log(self.admin, preview['ticket'])
        entry.refresh_from_db()
        self.assertEqual(entry.state, 'stale')
        self.assertEqual(entry.reviews.count(), 1)

    def test_existing_mission_search_link_and_stale_version(self):
        entry = self.imported('Different spelling')
        results = search_missions(self.admin, 'Silent', GUILD)
        self.assertEqual(results[0]['reference'], 'bot:quest-1')
        previous = entry_version(entry)
        reviewed = self.review(entry, 'link_mission', reference='bot:quest-1', adventures=1)
        self.assertEqual(reviewed.source.missions.get().bot_quest_id, 'quest-1')
        with self.assertRaises(ValidationError):
            review_entry(self.admin, entry.pk, previous, 'reopen', note='Old form')
        BotQuest.objects.filter(pk='quest-1').update(status='cancelled')
        self.assertEqual(search_missions(self.admin, 'Silent', GUILD), [])
        with self.assertRaises(ValidationError):
            self.review(reviewed, 'link_mission', reference='bot:quest-1')

    def test_missing_bot_quantity_does_not_validate_a_forged_sheet_quantity(self):
        from .test_character_log_import import DISCORD
        BotQuest.objects.filter(pk='quest-1').update(rewardAventurasOverride=None,
            questPlayers=[{'userId': DISCORD, 'characterName': self.log.characterName}])
        preview = self.preview(workbook(quantity=999))
        self.assertEqual(preview['rows'][0]['state'], 'quantity_unproven')
        self.assertEqual(preview['matched'], 0)
        entry = apply_log(self.admin, preview['ticket']).source.entries.get()
        self.assertEqual(entry.state, 'pending')
        self.assertIsNone(entry.adventures_confirmed)

    def test_staff_registered_history_proves_legacy_participation_but_upload_does_not(self):
        from unittest.mock import patch
        from .character_log_import import preview_log
        BotQuest.objects.filter(pk='quest-1').update(questPlayers=[], rewardAventurasOverride=4)
        data = workbook(titles=('The Silent Road II', 'FGTS', 'Moedas de Mestre'), quantity=4)
        with patch('home.character_log_import.download_workbook', return_value=data):
            trusted = preview_log(self.admin, self.log.pk, guild_id=GUILD)
        self.assertEqual(trusted['matched'], 1)
        self.assertEqual(trusted['pending'], 0)
        self.assertFalse(trusted['rows'][0]['proof']['owner_in_bot'])
        self.assertTrue(trusted['rows'][0]['proof']['owner_from_staff_log'])
        batch = apply_log(self.admin, trusted['ticket'])
        self.assertEqual(batch.source.missions.get().bot_quest_id, 'quest-1')
        self.assertEqual(batch.source.entries.filter(state='staff_record').count(), 2)
        self.assertFalse(TbPersonagemAventura.objects.exists())
        self.assertFalse(TbTransacaoMestre.objects.exists())
        untrusted = self.preview(data)
        self.assertEqual(untrusted['matched'], 0)
        self.assertEqual(untrusted['pending'], 3)

    def test_missing_mission_attestation_creates_audited_history_not_a_bot_mission_or_credit(self):
        entry = self.imported('Absent historical road')
        count = BotQuest.objects.count()
        reviewed = self.review(entry, 'register_missing_mission', title='Absent historical road',
            date='2026-08-30', master='Historical master', adventures=12)
        self.assertEqual(reviewed.reference, f'history:{CharacterHistoryMission.objects.get().pk}')
        self.assertEqual(BotQuest.objects.count(), count)
        self.assertEqual(search_missions(self.admin, 'Absent', GUILD)[0]['origin'], 'Historico atestado pela staff')
        self.assertFalse(TbPersonagemAventura.objects.exists())
        self.assertFalse(TbTransacaoMestre.objects.exists())
        other = self.imported('Another label')
        self.review(other, 'register_missing_mission', title='Absent historical road',
                    date='2026-08-30', master='Historical master', adventures=12)
        self.assertEqual(CharacterHistoryMission.objects.count(), 1)

    def test_explicit_master_mm_reserves_once_without_guessing_an_account(self):
        from unittest.mock import patch
        from .models import TbImportacaoMestre, TbMestreLegado
        archive = TbImportacaoMestre.objects.create(fonte='test-history-reservation',
            checksum='e' * 64, dados={})
        master = TbMestreLegado.objects.create(importacao=archive, numero=17,
            nome='Mestre Historiador', rotulo_original='F17', saldo_mm=30)
        preview = self.preview(workbook(titles=('Missing mission', 'Another report')))
        first, second = list(apply_log(self.admin, preview['ticket']).source.entries.order_by('pk'))
        with patch('home.master_legacy_api._backup') as backup:
            self.review(first, 'register_missing_mission', title='Historical expedition',
                date='2026-08-30', master='Historiador', adventures=12,
                master_number=17, master_mm=600)
            self.review(second, 'register_missing_mission', title='Historical expedition',
                date='2026-08-30', master='Historiador', adventures=12,
                master_number=17, master_mm=600)
            backup.assert_called_once()
        master.refresh_from_db()
        self.assertEqual(master.saldo_mm, 630)
        self.assertIsNone(master.user_id)
        self.assertEqual(master.registros.get().valor_mm, 600)
        self.assertEqual(CharacterHistoryMission.objects.get().adventures, 12)
        self.assertFalse(TbTransacaoMestre.objects.exists())

    def test_financial_backup_failure_rolls_back_historical_record_and_reservation(self):
        from unittest.mock import patch
        from .models import TbImportacaoMestre, TbMestreLegado
        archive = TbImportacaoMestre.objects.create(fonte='test-history-refused', checksum='d' * 64)
        master = TbMestreLegado.objects.create(importacao=archive, numero=18,
            nome='Mestre Historiador', rotulo_original='F18', saldo_mm=30)
        entry = self.imported('Missing mission')
        with patch('home.master_legacy_api._backup', side_effect=OSError('backup unavailable')):
            with self.assertRaises(ValidationError):
                self.review(entry, 'register_missing_mission', title='Historical expedition',
                    date='2026-08-30', master='Historiador', adventures=12,
                    master_number=18, master_mm=600)
        self.assertFalse(CharacterHistoryMission.objects.exists())
        self.assertFalse(master.registros.exists())
        master.refresh_from_db()
        self.assertEqual(master.saldo_mm, 30)

    def test_mm_receipt_must_belong_to_owner_and_cannot_back_two_entries(self):
        preview = self.preview(workbook(titles=('Moedas de Mestre', 'Moedas de Mestre (outro)')))
        batch = apply_log(self.admin, preview['ticket'])
        first, second = list(batch.source.entries.order_by('pk'))
        own = TbTransacaoMestre.objects.create(mestre=self.owner, tipo='resgate',
            descricao='Aventura e Recompensa', valor_mm=-100, saldo_mm=0)
        foreign = TbTransacaoMestre.objects.create(mestre=self.admin, tipo='resgate', valor_mm=-100)
        self.assertEqual(len(search_redemptions(self.admin, first)), 1)
        with self.assertRaises(ValidationError):
            self.review(first, 'link_redemption', reference=f'mm:{foreign.pk}')
        self.review(first, 'link_redemption', reference=f'mm:{own.pk}')
        with self.assertRaises(ValidationError):
            self.review(second, 'link_redemption', reference=f'mm:{own.pk}')

    def test_http_queue_search_confirmation_csrf_and_stale_form(self):
        from django.urls import reverse
        from django.test import Client
        entry = self.imported('Unregistered road')
        queue_url = reverse('gestao:character_log_reviews')
        url = reverse('gestao:character_log_review_detail', args=[entry.pk])
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(queue_url).status_code, 403)
        self.client.force_login(self.admin)
        self.assertContains(self.client.get(queue_url), 'Unregistered road')
        self.assertContains(self.client.get(url, {'catalog': 'missions', 'query': 'Silent'}), 'Silent Road')
        self.assertFalse(CharacterLogReview.objects.exists())
        data = {'action': 'link_mission', 'expected_version': entry_version(entry),
                'reference': 'bot:quest-1', 'adventures': '1',
                'note': 'Titulo antigo conferido no registro', 'evidence': 'discord-message:123456789012345678'}
        csrf = Client(enforce_csrf_checks=True)
        csrf.force_login(self.admin)
        self.assertEqual(csrf.post(url, data).status_code, 403)
        self.assertEqual(self.client.post(url, data).status_code, 302)
        self.assertEqual(self.client.post(url, data).status_code, 409)
        self.assertEqual(CharacterLogReview.objects.count(), 1)


if ISOLATED:
    if connection.vendor != 'sqlite' or connection.settings_dict['NAME'] != ':memory:':
        raise RuntimeError('Only isolated SQLite memory is allowed')
    with connection.schema_editor() as editor:
        for model in apps.get_models():
            if model._meta.managed and not model._meta.proxy:
                editor.create_model(model)
        editor.create_model(BotCharacterLog)
        editor.create_model(BotQuest)
    from django.test.utils import setup_test_environment
    setup_test_environment()
    unittest.main(argv=[sys.argv[0]], verbosity=2,
                  defaultTest='CharacterLogReviewTests')
