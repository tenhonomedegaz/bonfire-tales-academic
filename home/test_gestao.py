"""Management checks in SQLite memory. Never use the configured PostgreSQL."""
import sys
from datetime import datetime, timezone as datetime_timezone
from pathlib import Path

ISOLATED = __name__ == '__main__' and '--isolated' in sys.argv
if ISOLATED:
    import os
    os.environ['DJANGO_SECRET_KEY'] = 'isolated-management-only'
    os.environ['POSTGRES_URL'] = 'postgresql://unused:unused@127.0.0.1:1/unused'
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bonfire.settings')
    from bonfire import settings as project_settings
    project_settings.DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':memory:'}}
    project_settings.SECRET_KEY = 'isolated-management-only'
    project_settings.DEBUG = True
    project_settings.ALLOWED_HOSTS = ['testserver', 'localhost', '127.0.0.1']
    project_settings.PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']
    project_settings.EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
    import django
    django.setup()

import unittest
from unittest.mock import patch

from django.apps import apps
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.core import signing
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connection
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from .gestao.policy import can
from .gestao.services import apply_manual_grant, preview_manual_grant
from .gestao_models import ManualCosmeticGrantReceipt
from .models import TbCosmetico, TbUsuarioCosmetico, UserProfile


class ManagementFlowTests(TestCase):
    def setUp(self):
        users = get_user_model()
        self.admin = users.objects.create_user('admin', is_superuser=True, is_staff=False)
        self.person = users.objects.create_user('aventura')
        self.staff = users.objects.create_user('equipe', is_staff=True)
        self.cosmetic = TbCosmetico.objects.create(slug='moldura-bosque-qa', tipo='moldura',
            nome='Moldura do Bosque', origem='evento_manual', ativo=True,
            asset_url='/static/cosmetics/avatar-black-moon-v5.webp')

    def preview(self, **changes):
        arguments = dict(actor=self.admin, user_id=self.person.pk,
                         cosmetic_id=self.cosmetic.pk, reason='Concessao aprovada em evento.')
        arguments.update(changes)
        return preview_manual_grant(**arguments)

    def confirm(self, preview=None, **changes):
        arguments = dict(actor=self.admin, ticket=(preview or self.preview())['ticket'])
        arguments.update(changes)
        return apply_manual_grant(**arguments)

    def test_superuser_does_not_require_staff_boolean(self):
        self.assertTrue(can(self.admin, 'people.view'))
        self.assertTrue(can(self.admin, 'cosmetics.grant_manual'))
        self.assertFalse(can(self.staff, 'people.view'))
        self.assertFalse(can(self.admin, 'unknown'))
        self.admin.is_active = False
        self.assertFalse(can(self.admin, 'people.view'))

    def test_explicit_permissions_work_without_staff_or_group_promotion(self):
        self.staff.is_staff = False
        self.staff.save(update_fields=['is_staff'])
        content_type = ContentType.objects.get_for_model(ManualCosmeticGrantReceipt)
        for code in ('view_management_people', 'view_management_cosmetics', 'grant_management_cosmetic'):
            permission, _ = Permission.objects.get_or_create(content_type=content_type,
                codename=code, defaults={'name': code})
            self.staff.user_permissions.add(permission)
        actor = get_user_model().objects.get(pk=self.staff.pk)
        preview = self.preview(actor=actor)
        receipt = self.confirm(preview, actor=actor)
        self.assertEqual(receipt.outcome, 'granted')
        actor.refresh_from_db()
        self.assertFalse(actor.is_staff)
        self.assertFalse(actor.is_superuser)

    def test_preview_is_read_only_and_double_submit_returns_same_receipt(self):
        preview = self.preview()
        self.assertTrue(preview['can_apply'])
        self.assertFalse(TbUsuarioCosmetico.objects.exists())
        self.assertFalse(ManualCosmeticGrantReceipt.objects.exists())
        first, second = self.confirm(preview), self.confirm(preview)
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(TbUsuarioCosmetico.objects.count(), 1)
        self.assertEqual(ManualCosmeticGrantReceipt.objects.count(), 1)
        self.assertEqual(first.actor, self.admin)
        self.assertEqual(first.motivo, 'Concessao aprovada em evento.')

    def test_existing_inventory_is_preserved_instead_of_overwriting_purchase_origin(self):
        inventory = TbUsuarioCosmetico.objects.create(user=self.person, cosmetico=self.cosmetic,
                                                    origem='compra_asaas')
        preview = self.preview()
        self.assertTrue(preview['already_owned'])
        receipt = self.confirm(preview)
        inventory.refresh_from_db()
        self.assertEqual(receipt.outcome, 'already_owned')
        self.assertEqual(inventory.origem, 'compra_asaas')

    def test_permanent_right_does_not_create_duplicate_manual_inventory(self):
        with patch('home.gestao.services.has_permanent_cosmetic', return_value=True):
            receipt = self.confirm()
        self.assertEqual(receipt.outcome, 'already_owned')
        self.assertFalse(TbUsuarioCosmetico.objects.exists())

    def test_suspension_is_not_implicitly_reactivated(self):
        inventory = TbUsuarioCosmetico.objects.create(user=self.person, cosmetico=self.cosmetic,
            origem='staff', suspenso_em=timezone.now())
        preview = self.preview()
        self.assertFalse(preview['can_apply'])
        self.assertEqual(preview['ticket'], '')
        inventory.refresh_from_db()
        self.assertIsNotNone(inventory.suspenso_em)

    def test_stale_catalog_target_and_permission_are_rechecked(self):
        preview = self.preview()
        TbCosmetico.objects.filter(pk=self.cosmetic.pk).update(ativo=False)
        with self.assertRaises(ValidationError):
            self.confirm(preview)
        TbCosmetico.objects.filter(pk=self.cosmetic.pk).update(ativo=True)
        self.person.is_active = False
        self.person.save(update_fields=['is_active'])
        with self.assertRaises(ValidationError):
            self.confirm(preview)
        self.person.is_active = True
        self.person.save(update_fields=['is_active'])
        self.admin.is_superuser = False
        self.admin.save(update_fields=['is_superuser'])
        with self.assertRaises(PermissionDenied):
            self.confirm(preview)
        self.assertFalse(TbUsuarioCosmetico.objects.exists())

    def test_forged_expired_and_other_actor_tickets_are_refused(self):
        preview = self.preview()
        with self.assertRaises(ValidationError):
            self.confirm(preview, ticket=preview['ticket'] + 'bad')
        with patch('home.gestao.services.signing.loads', side_effect=signing.SignatureExpired):
            with self.assertRaises(ValidationError):
                self.confirm(preview)
        other = get_user_model().objects.create_user('other_admin', is_superuser=True)
        with self.assertRaises(PermissionDenied):
            self.confirm(preview, actor=other)
        self.assertFalse(TbUsuarioCosmetico.objects.exists())

    def test_audit_failure_rolls_back_inventory_and_missing_reason_is_rejected(self):
        with self.assertRaises(ValidationError):
            self.preview(reason='')
        preview = self.preview()
        with patch.object(ManualCosmeticGrantReceipt.objects, 'create', side_effect=ValueError('audit failed')):
            with self.assertRaises(ValueError):
                self.confirm(preview)
        self.assertFalse(TbUsuarioCosmetico.objects.exists())

    def test_ticket_cannot_be_confirmed_for_another_target(self):
        preview = self.preview()
        with self.assertRaises(ValidationError):
            self.confirm(preview, expected_user_id=self.staff.pk)
        self.assertFalse(TbUsuarioCosmetico.objects.exists())

    def test_http_preview_confirm_and_replay_with_receipt(self):
        self.client.force_login(self.admin)
        route = reverse('gestao:grant', args=[self.person.pk])
        response = self.client.post(route, {'action': 'preview', 'cosmetic_id': self.cosmetic.pk,
                                            'reason': 'Presente autorizado pela equipe.'})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(TbUsuarioCosmetico.objects.exists())
        ticket = response.context['preview']['ticket']
        payload = {'action': 'confirm', 'ticket': ticket}
        first, second = self.client.post(route, payload), self.client.post(route, payload)
        self.assertEqual(first.status_code, 302)
        self.assertEqual(second.status_code, 302)
        self.assertEqual(ManualCosmeticGrantReceipt.objects.count(), 1)
        self.assertEqual(TbUsuarioCosmetico.objects.count(), 1)
        history = self.client.get(first['Location'])
        self.assertEqual(history.status_code, 200)
        self.assertContains(history, 'Presente autorizado pela equipe.')

    def test_write_without_csrf_is_refused(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.admin)
        response = client.post(reverse('gestao:grant', args=[self.person.pk]), {
            'action': 'preview', 'cosmetic_id': self.cosmetic.pk, 'reason': 'Presente aprovado.'})
        self.assertEqual(response.status_code, 403)
        self.assertFalse(ManualCosmeticGrantReceipt.objects.exists())

    def test_management_get_does_not_create_missing_profiles(self):
        self.client.force_login(self.admin)
        UserProfile.objects.filter(user__in=[self.admin, self.person]).delete()
        before = UserProfile.objects.count()
        response = self.client.get(reverse('gestao:person', args=[self.person.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(UserProfile.objects.count(), before)

    def test_dates_are_shown_in_brasilia_without_leaking_timezone(self):
        self.person.date_joined = datetime(2026, 1, 2, 1, 30, tzinfo=datetime_timezone.utc)
        self.person.save(update_fields=['date_joined'])
        self.client.force_login(self.admin)
        with timezone.override('UTC'):
            response = self.client.get(reverse('gestao:person', args=[self.person.pk]))
            self.assertContains(response, '01/01/2026 22:30')
            self.assertEqual(timezone.get_current_timezone_name(), 'UTC')

    def test_http_routes_are_guarded_and_share_site_header_without_new_tab(self):
        for name in ('gestao:index', 'gestao:people'):
            self.assertEqual(self.client.get(reverse(name)).status_code, 302)
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(reverse('gestao:people')).status_code, 403)
        self.assertEqual(self.client.get(reverse('gestao:person', args=[self.person.pk])).status_code, 403)
        self.client.force_login(self.admin)
        response = self.client.get(reverse('gestao:people'), {'q': self.person.username})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.person.username)
        self.assertContains(response, reverse('gestao:person', args=[self.person.pk]))
        self.assertNotContains(response, 'target="_blank" href="/gestao/')
        self.assertNotContains(response, 'Available user permissions')
        self.assertContains(response, 'noindex')


if ISOLATED:
    if connection.vendor != 'sqlite' or connection.settings_dict['NAME'] != ':memory:':
        raise RuntimeError('Only isolated SQLite memory is allowed')
    models = [model for model in apps.get_models() if model._meta.managed and not model._meta.proxy]
    with connection.schema_editor() as editor:
        for model in models:
            editor.create_model(model)
    from django.test.utils import setup_test_environment
    setup_test_environment()
    if '--migration-check' in sys.argv:
        from django.core.management import call_command
        call_command('makemigrations', 'home', check=True, dry_run=True, verbosity=1)
    if '--preview' in sys.argv:
        from django.contrib.staticfiles.handlers import StaticFilesHandler
        from django.core.wsgi import get_wsgi_application
        from wsgiref.simple_server import make_server
        users = get_user_model()
        preview_admin = users.objects.create_superuser('preview-admin', 'preview@example.invalid', 'preview-local-only')
        visitor = users.objects.create_user('AventureiroDeCineria', first_name='Aventureiro')
        users.objects.create_user('StaffDeExemplo', is_staff=True)
        TbCosmetico.objects.create(slug='moldura-lua-negra-preview', tipo='moldura',
            nome='Moldura da Lua Negra', origem='evento_manual', ativo=True,
            asset_url='/static/cosmetics/avatar-black-moon-v5.webp')
        TbCosmetico.objects.create(slug='moldura-lua-de-sangue-preview', tipo='moldura',
            nome='Moldura da Lua de Sangue', origem='evento_manual', ativo=True,
            asset_url='/static/cosmetics/avatar-blood-moon-v5.webp')
        TbCosmetico.objects.create(slug='tema-evento-preview', tipo='tema',
            nome='Tema da Vigilia', origem='evento_manual', ativo=False)
        from .models import (BotCharacterLog, BotQuest, TbImportacaoMestre, TbMestreLegado,
                             TbRegistroMestreLegado, TbRevisaoMissaoBot)
        with connection.schema_editor() as editor:
            editor.create_model(BotQuest)
            editor.create_model(BotCharacterLog)
        archive = TbImportacaoMestre.objects.create(fonte='local-preview', checksum='f' * 64, dados={})
        identity = TbMestreLegado.objects.create(importacao=archive, numero=9, nome='Mestre de Exemplo',
            rotulo_original='F09', discord_id='123456789012345678', user=visitor)
        TbRegistroMestreLegado.objects.create(mestre=identity, chave='local-manual', tipo='adventure',
            titulo='Memoria da planilha', data=timezone.localdate(), valor_mm=200, original={})
        for index in range(26):
            quest = BotQuest.objects.create(id=f'preview-mission-{index}', guildId='223456789012345678',
                channelId='323456789012345678', name=f'Aventura de exemplo {index + 1}', description='',
                questDate=timezone.now(), endDate=timezone.now(), playersAmount=4, rules='', type='Aventura',
                tableUrl='', questMaster=identity.discord_id, createdBy=identity.discord_id, isPublished=True,
                status='finished', rewardAventurasOverride=4 if index == 0 else 1,
                createdAt=timezone.now(), updatedAt=timezone.now())
            if index == 0:
                TbRevisaoMissaoBot.objects.create(quest_id=quest.pk, guild_id=quest.guildId,
                    master_discord_id=identity.discord_id, legacy_master=identity, decision='confirmed',
                    adventures=4, master_mm=460, reviewed_by=preview_admin, evidence={
                        'reward_context': {'base_adventures': 2, 'multiplier': 2, 'base_mm': 400,
                            'dedicated_bonus_mm': 60, 'final_mm': 460, 'reason': 'weekend_double'},
                        'mission_details': {'summary': 'Relato ficticio para conferir a apresentacao.',
                                            'participants': ['Aventureiro de Exemplo']}})
        UserProfile.objects.filter(user=visitor).update(discord_user_id=identity.discord_id)
        for index, name in enumerate(('Andromeda de Exemplo', 'Outro Personagem de Exemplo')):
            sheet_id = ('A' if index == 0 else 'B') * 32
            BotCharacterLog.objects.create(id=f'preview-log-{index}', discordUserId=identity.discord_id,
                discordUserTag=visitor.username, sheetUrl=f'https://docs.google.com/spreadsheets/d/{sheet_id}/edit',
                spreadsheetId=sheet_id, characterName=name, rankName='Diamante', className='Classe de Exemplo',
                level=20, adventuresPlayed=160, registeredBy=identity.discord_id,
                createdAt=timezone.now(), updatedAt=timezone.now())
        BotQuest.objects.filter(pk='preview-mission-0').update(questPlayers=[{
            'userId': identity.discord_id, 'characterName': 'Andromeda de Exemplo',
            'characterUrl': f'https://docs.google.com/spreadsheets/d/{"A" * 32}/edit', 'rewardAmount': 4}])
        from .test_character_log_import import workbook
        demo_sheets = {'A' * 32: workbook(titles=('Aventura de exemplo 1', 'Registro sem correspondencia',
                                                'FGTS', 'Moedas de Mestre'),
                                         name='Andromeda de Exemplo', quantity=4),
                       'B' * 32: workbook(name='Outro Personagem de Exemplo')}
        def demo_download(source_id):
            if source_id not in demo_sheets:
                raise ValidationError('Esta previa aceita somente fontes ficticias locais.')
            return demo_sheets[source_id]
        print('ISOLATED_PREVIEW http://127.0.0.1:8777/gestao/', flush=True)
        with patch('home.character_log_import.download_workbook', side_effect=demo_download):
            from .character_log_import import preview_log, apply_log
            from .models import TbTransacaoMestre
            apply_log(preview_admin, preview_log(preview_admin, 'preview-log-0',
                guild_id='223456789012345678')['ticket'])
            TbTransacaoMestre.objects.create(mestre=visitor, tipo='resgate',
                descricao='Recibo ficticio de Aventura e Recompensa', valor_mm=-400,
                saldo_mm=0, quantidade=4)
            make_server('127.0.0.1', 8777, StaticFilesHandler(get_wsgi_application())).serve_forever()
    else:
        result = unittest.TextTestRunner(verbosity=2).run(
            unittest.defaultTestLoader.loadTestsFromTestCase(ManagementFlowTests))
        sys.exit(0 if result.wasSuccessful() else 1)
