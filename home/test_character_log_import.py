"""Focused import checks; --isolated never connects to the configured PostgreSQL."""
import io
import os
import sys
import unittest
from unittest.mock import patch

ISOLATED = __name__ == '__main__' and '--isolated' in sys.argv
if ISOLATED:
    os.environ['DJANGO_SECRET_KEY'] = 'isolated-character-import'
    os.environ['POSTGRES_URL'] = 'postgresql://unused:unused@127.0.0.1:1/unused'
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bonfire.settings')
    from bonfire import settings as project_settings
    project_settings.DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':memory:'}}
    project_settings.SECRET_KEY = 'isolated-character-import'
    project_settings.ALLOWED_HOSTS = ['testserver', '127.0.0.1', 'localhost']
    project_settings.PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']
    import django
    django.setup()

from django.apps import apps
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connection
from django.test import TestCase
from django.utils import timezone
from openpyxl import Workbook

from .character_log_import import apply_log, preview_log, registered_logs
from .character_log_models import CharacterLogImportBatch, CharacterLogMission, CharacterLogSource
from .character_log_workbook import read_workbook, spreadsheet_id, _GoogleRedirects
from .models import (BotCharacterLog, BotQuest, TbPersonagem, TbPersonagemAventura,
                     TbRevisaoMissaoBot, TbTransacaoMestre, UserProfile)

DISCORD = '123456789012345678'
GUILD = '223456789012345678'
SHEET = 'A' * 32


def workbook(titles=('The Silent Road II',), *, name='Andromeda', quantity=None, description=''):
    book = Workbook()
    book.properties.description = description
    log = book.active
    log.title = 'LOG'
    for cell, value in {'C6': name, 'R25': 'Diamante', 'T5': 'Cacador', 'AL6': 20, 'AE7': 160}.items():
        log[cell] = value
    adventures = book.create_sheet('Aventuras')
    for index, title in enumerate(titles):
        row = 3 + 15 * index
        adventures[f'J{row}'] = title
        adventures[f'W{row + 2}'] = 130  # Not an adventure quantity.
        if quantity is not None:
            adventures[f'A{row + 3}'], adventures[f'B{row + 3}'] = 'Aventuras', quantity
    output = io.BytesIO()
    book.save(output)
    return output.getvalue()


class CharacterLogImportTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_user('import-admin', is_superuser=True)
        self.owner = get_user_model().objects.create_user('import-owner')
        profile = UserProfile.objects.get(user=self.owner)
        profile.discord_user_id = DISCORD
        profile.save(update_fields=['discord_user_id'])
        self.log = BotCharacterLog.objects.create(id='log-1', discordUserId=DISCORD,
            discordUserTag='Owner', sheetUrl=f'https://docs.google.com/spreadsheets/d/{SHEET}/edit',
            spreadsheetId=SHEET, characterName='Andromeda', rankName='Diamante', className='Cacador',
            level=20, adventuresPlayed=160, registeredBy=DISCORD,
            createdAt=timezone.now(), updatedAt=timezone.now())
        self.quest()

    def quest(self, key='quest-1', **changes):
        values = dict(id=key, guildId=GUILD, name='Silent Road - II', description='',
            questDate=timezone.now(), endDate=timezone.now(), playersAmount=1, rules='', type='Aventura',
            tableUrl='', questMaster='323456789012345678', createdBy='323456789012345678',
            status='finished', rewardAventurasOverride=1,
            questPlayers=[{'userId': DISCORD, 'characterName': 'Andromeda',
                          'characterUrl': self.log.sheetUrl, 'rewardAmount': 1}],
            createdAt=timezone.now(), updatedAt=timezone.now())
        values.update(changes)
        return BotQuest.objects.create(**values)

    def preview(self, data=None):
        return preview_log(self.admin, self.log.pk, uploaded=data or workbook(), guild_id=GUILD)

    def test_parser_reads_metadata_and_titles_without_turning_money_into_adventures(self):
        result = read_workbook(workbook())
        self.assertEqual(result['metadata']['adventures_reported'], 160)
        self.assertEqual(result['rows'][0]['title'], 'The Silent Road II')
        self.assertIsNone(result['rows'][0]['adventures'])
        self.assertEqual(result['rows'][0]['starter_marker'], '130')
        self.assertEqual(read_workbook(workbook(quantity=2))['rows'][0]['adventures'], 2)

    def test_preview_is_read_only_and_import_is_idempotent_without_playable_character_or_rewards(self):
        preview = self.preview()
        self.assertEqual(preview['matched'], 1)
        self.assertIsNone(preview['character_id'])
        self.assertFalse(CharacterLogSource.objects.exists())
        first = apply_log(self.admin, preview['ticket'])
        second = apply_log(self.admin, preview['ticket'])
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(CharacterLogSource.objects.count(), 1)
        self.assertEqual(CharacterLogImportBatch.objects.count(), 1)
        self.assertEqual(CharacterLogMission.objects.count(), 1)
        self.assertFalse(TbPersonagem.objects.exists())
        self.assertFalse(TbPersonagemAventura.objects.exists())
        self.assertFalse(TbTransacaoMestre.objects.exists())

    def test_export_metadata_changes_do_not_duplicate_the_same_import(self):
        first = self.preview(workbook(description='First ZIP export'))
        second = self.preview(workbook(description='Second ZIP export'))
        self.assertEqual(first['fingerprint'], second['fingerprint'])
        self.assertEqual(apply_log(self.admin, first['ticket']).pk,
                         apply_log(self.admin, second['ticket']).pk)

    def test_http_preview_confirm_and_csrf(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        from django.test import Client
        from django.urls import reverse
        route = reverse('gestao:character_logs')
        self.assertEqual(self.client.get(route).status_code, 403)
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(route).status_code, 403)
        self.client.force_login(self.admin)
        self.assertContains(self.client.get(route, {'q': DISCORD}), 'Andromeda')
        response = self.client.post(route, {'action': 'preview', 'log_id': self.log.pk,
            'guild_id': GUILD, 'uploaded': SimpleUploadedFile('log.xlsx', workbook())})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(CharacterLogSource.objects.exists())
        ticket = response.context['preview']['ticket']
        self.assertEqual(self.client.post(route, {'action': 'apply', 'ticket': ticket}).status_code, 400)
        confirmed = self.client.post(route, {'action': 'apply', 'ticket': ticket, 'confirm': 'yes'})
        self.assertEqual(confirmed.status_code, 302)
        self.assertNotIn('ticket', confirmed['Location'])
        self.assertContains(self.client.get(confirmed['Location']), 'Andromeda')
        self.assertEqual(CharacterLogImportBatch.objects.count(), 1)
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.admin)
        self.assertEqual(csrf_client.post(route, {'action': 'apply', 'ticket': ticket,
                                                 'confirm': 'yes'}).status_code, 403)

    def test_api_uses_the_same_actor_and_base_version(self):
        from types import SimpleNamespace
        from .character_log_api import character_logs_read, character_log_preview, character_log_apply
        from .db_access import ApiProblem
        key = SimpleNamespace(created_by=self.admin)
        self.assertEqual(character_logs_read({'discord_id': DISCORD}, key)['total'], 1)
        with patch('home.character_log_import.download_workbook', return_value=workbook()):
            result = character_log_preview({'log_id': self.log.pk, 'guild_id': GUILD}, key)
        self.assertEqual(result['matched'], 1)
        with self.assertRaises(ApiProblem):
            character_log_apply({'ticket': result['ticket'], 'base_version': '0' * 64}, key)
        receipt = character_log_apply({'ticket': result['ticket'], 'base_version': result['base_version']}, key)
        self.assertFalse(receipt['rewards_credited'])
        self.assertEqual(receipt['matched'], 1)
        with self.assertRaises(ApiProblem):
            character_logs_read({'discord_id': DISCORD}, SimpleNamespace(created_by=self.owner))

    def test_registration_identity_and_sheet_name_are_required(self):
        self.assertEqual(len(registered_logs(self.admin, DISCORD)), 1)
        with self.assertRaises(ValidationError):
            self.preview(workbook(name='Different character'))
        self.log.sheetUrl = 'https://evil.test/a'
        self.log.save(update_fields=['sheetUrl'])
        with self.assertRaises(ValidationError):
            self.preview()
        self.assertFalse(CharacterLogSource.objects.exists())

    def test_same_discord_other_character_is_not_associated(self):
        BotQuest.objects.filter(pk='quest-1').update(questPlayers=[{
            'userId': DISCORD, 'characterName': 'Other character',
            'characterUrl': f'https://docs.google.com/spreadsheets/d/{"B" * 32}/edit'}])
        preview = self.preview()
        self.assertEqual(preview['matched'], 0)
        self.assertEqual(preview['rows'][0]['state'], 'unproven')
        apply_log(self.admin, preview['ticket'])
        self.assertFalse(CharacterLogMission.objects.exists())

    def test_multiple_characters_require_character_specific_participation_evidence(self):
        values = {field.attname: getattr(self.log, field.attname) for field in self.log._meta.concrete_fields}
        values.update(id='log-2', spreadsheetId='B' * 32, characterName='Other character',
                      sheetUrl=f'https://docs.google.com/spreadsheets/d/{"B" * 32}/edit')
        BotCharacterLog.objects.create(**values)
        BotQuest.objects.filter(pk='quest-1').update(questPlayers=[{'userId': DISCORD}])
        preview = self.preview()
        self.assertEqual(preview['matched'], 0)
        self.assertEqual(preview['rows'][0]['state'], 'unproven')

    def test_repeated_title_and_repeated_source_rows_are_ambiguous(self):
        self.quest('quest-2')
        self.assertEqual(self.preview()['rows'][0]['state'], 'ambiguous')
        BotQuest.objects.filter(pk='quest-2').delete()
        preview = self.preview(workbook(titles=('The Silent Road II', 'Silent Road II')))
        self.assertEqual(preview['matched'], 0)
        self.assertTrue(all(r['state'] == 'ambiguous' for r in preview['rows']))

    def test_reward_mismatch_is_reported_not_applied_and_boost_entries_are_not_missions(self):
        preview = self.preview(workbook(titles=('Silent Road II', 'Boost de evento'), quantity=4))
        self.assertEqual(preview['rows'][0]['state'], 'conflict')
        self.assertEqual(preview['rows'][1]['state'], 'adjustment')
        batch = apply_log(self.admin, preview['ticket'])
        self.assertEqual(len(batch.snapshot['rows']), 2)
        self.assertFalse(CharacterLogMission.objects.exists())

    def test_cancelled_or_excluded_bot_sessions_do_not_match(self):
        BotQuest.objects.filter(pk='quest-1').update(status='cancelled')
        self.assertEqual(self.preview()['matched'], 0)
        BotQuest.objects.filter(pk='quest-1').update(status='finished')
        TbRevisaoMissaoBot.objects.create(quest_id='quest-1', guild_id=GUILD,
            decision='no_record', reviewed_by=self.admin)
        self.assertEqual(self.preview()['matched'], 0)

    def test_changed_owner_or_quest_refuses_stale_preview(self):
        preview = self.preview()
        BotQuest.objects.filter(pk='quest-1').update(name='Changed title')
        with self.assertRaises(ValidationError):
            apply_log(self.admin, preview['ticket'])
        self.assertFalse(CharacterLogSource.objects.exists())
        self.log.discordUserId = '423456789012345678'
        self.log.save(update_fields=['discordUserId'])
        with self.assertRaises(ValidationError):
            apply_log(self.admin, preview['ticket'])

    def test_other_actor_or_forgery_cannot_apply(self):
        preview = self.preview()
        with self.assertRaises(PermissionDenied):
            apply_log(self.owner, preview['ticket'])
        other = get_user_model().objects.create_user('other-admin', is_superuser=True)
        with self.assertRaises(PermissionDenied):
            apply_log(other, preview['ticket'])
        with self.assertRaises(ValidationError):
            apply_log(self.admin, preview['ticket'] + 'bad')

    def test_failure_rolls_back_source_batch_and_links(self):
        preview = self.preview()
        with patch.object(CharacterLogMission.objects, 'update_or_create', side_effect=ValueError('failure')):
            with self.assertRaises(ValueError):
                apply_log(self.admin, preview['ticket'])
        self.assertFalse(CharacterLogSource.objects.exists())
        self.assertFalse(CharacterLogImportBatch.objects.exists())

    def test_only_owned_site_character_can_be_related_and_nothing_is_overwritten(self):
        character = TbPersonagem.objects.create(dono=self.owner, nome='Andromeda', nivel=3, aventuras=5)
        other = TbPersonagem.objects.create(dono=self.admin, nome='Andromeda')
        preview = self.preview()
        self.assertEqual(preview['character_id'], character.pk)
        batch = apply_log(self.admin, preview['ticket'])
        self.assertEqual(batch.source.character_id, character.pk)
        character.refresh_from_db()
        self.assertEqual((character.nivel, character.aventuras), (3, 5))
        self.assertNotEqual(batch.source.character_id, other.pk)

    def test_bad_file_and_untrusted_urls_are_refused(self):
        with self.assertRaises(ValidationError):
            read_workbook(b'not an xlsx')
        for url in ('http://docs.google.com/spreadsheets/d/' + SHEET,
                    'https://docs.google.com.evil.test/spreadsheets/d/' + SHEET,
                    'https://user@docs.google.com/spreadsheets/d/' + SHEET):
            self.assertEqual(spreadsheet_id(url), '')
        from urllib.request import Request
        with self.assertRaises(ValidationError):
            _GoogleRedirects().redirect_request(Request('https://docs.google.com'), None,
                                                302, '', {}, 'http://127.0.0.1/secret')


if ISOLATED:
    if connection.vendor != 'sqlite' or connection.settings_dict['NAME'] != ':memory:':
        raise RuntimeError('Only isolated SQLite memory is allowed')
    if '--make-migration' in sys.argv:
        from django.core.management import call_command
        call_command('makemigrations', 'home', name='character_log_history', verbosity=1)
        sys.exit(0)
    with connection.schema_editor() as editor:
        for model in apps.get_models():
            if model._meta.managed and not model._meta.proxy:
                editor.create_model(model)
        editor.create_model(BotCharacterLog)
        editor.create_model(BotQuest)
    from django.test.utils import setup_test_environment
    setup_test_environment()
    unittest.main(argv=[sys.argv[0]], verbosity=2)
