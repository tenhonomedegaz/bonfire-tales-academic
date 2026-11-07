"""Legacy attribution and wallet regressions. Run with --isolated, SQLite memory only."""
import sys
from pathlib import Path

ISOLATED = __name__ == '__main__' and '--isolated' in sys.argv
if ISOLATED:
    from django.conf import settings
    settings.configure(SECRET_KEY='isolated-legacy-masters', USE_TZ=True,
        TIME_ZONE='America/Sao_Paulo', BASE_DIR=Path(__file__).resolve().parents[1],
        INSTALLED_APPS=['django.contrib.auth', 'django.contrib.contenttypes', 'home'],
        DATABASES={'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':memory:'}},
        DEFAULT_AUTO_FIELD='django.db.models.BigAutoField', ROOT_URLCONF=__name__, ALLOWED_HOSTS=['testserver'])
    import django
    django.setup()

import json
import unittest
from copy import deepcopy
from datetime import datetime
from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connection
from django.db.models import Sum
from django.test import TestCase, RequestFactory, override_settings
from django.http import HttpResponse
from django.utils import timezone
from django.urls import path

from home import db_access_api
from home.db_access_models import DbAccessAudit, DbAccessIdempotency, ManagedApiKey
from home.master_legacy import (bind_master, confirm_discord_masters, claim_discord_masters, discover_bot_links,
                                import_archive, market_identity_context, quest_local_date)
from home.master_legacy_api import legacy_import_preview, legacy_report_operation
from home.master_mission_archive import active_seconds, backfill_apply, backfill_plan, mission_audit
from home.master_mission_review import preview as review_preview, apply as review_apply, quote_reward
from home.models import (BotQuest, BotDedicatedRank, MestreOuroDireito, MestreOuroRevisao, TbAventuraMestre,
    TbImportacaoMestre, TbMestreLegado, TbPerfilMestre, TbRegistroMestreLegado,
    TbTransacaoMestre, TbRevisaoMissaoBot, UserProfile)

DID = '123456789012345678'
OTHER = '223456789012345678'
GUILD = '1167320030988468234'
urlpatterns = [path('operations/<slug:handler_name>/', db_access_api.db_operation),
               path('profile/', lambda request: HttpResponse(), name='profile'),
               path('masters/', lambda request: HttpResponse(), name='master_dashboard')]


def sample():
    return {'schema': 1, 'source_sha256': 'a' * 64, 'rewards': [], 'warnings': [],
        'masters': [{'number': 49, 'name': 'Mestra Hani', 'label': 'Fogueira 49 - Mestra Hani',
                     'balance_mm': 77, 'event_coins': 3, 'table_count': 1,
                     'calculations': {'income': 100}}],
        'entries': [{'key': 'history:3:adventure', 'master_number': 49, 'kind': 'adventure',
                     'title': 'Aventura da noite', 'date': '2026-01-02', 'amount_mm': 100},
                    {'key': 'history:3:purchase', 'master_number': 49, 'kind': 'purchase',
                     'title': 'Token de missao', 'date': '2026-01-03', 'amount_mm': -30}]}


class LegacyMasterTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create(username='admin', is_superuser=True, is_staff=True)
        self.user = User.objects.create(username='leehani17')
        UserProfile.objects.get_or_create(user=self.user)
        self.plan = sample()
        self.archive, _ = import_archive(self.plan, 'market', actor=self.admin)
        self.master = self.archive.mestres.get()

    def bind(self, **options):
        return bind_master(self.master.pk, self.user.pk, actor=self.admin, **options)

    @override_settings(MASTER_APPLICATIONS_OPEN=False)
    def test_closed_registration_rejects_direct_posts_without_creating_profiles(self):
        from home.master_participation import master_request
        from home.master_application_testdata import application_data
        request = RequestFactory().post('/mestre/solicitar/', application_data())
        request.user = self.user
        self.assertEqual(master_request(request).status_code, 403)
        self.assertFalse(TbPerfilMestre.objects.filter(user=self.user).exists())

    @override_settings(MASTER_APPLICATIONS_OPEN=True)
    def test_explicit_reopening_allows_one_pending_request(self):
        from home.master_participation import master_request
        from home.master_application_testdata import application_data
        request = RequestFactory().post('/mestre/solicitar/', application_data())
        request.user = self.user
        self.assertEqual(master_request(request).status_code, 302)
        self.assertEqual(master_request(request).status_code, 302)
        profile = TbPerfilMestre.objects.get(user=self.user)
        self.assertEqual((profile.status_mestre, profile.versao), ('pendente', 1))

    def test_master_authorization_requires_a_numbered_identity(self):
        from home.master_participation import master_authorize
        profile = TbPerfilMestre.objects.create(user=self.user, status_mestre='pendente')
        request = RequestFactory().post('/authorize/', {'acao':'autorizar', 'confirmar':'sim', 'versao':'0'})
        request.user = self.admin
        self.assertEqual(master_authorize(request, self.user.pk).status_code, 409)
        self.master.user = self.user
        self.master.save(update_fields=['user'])
        self.assertEqual(master_authorize(request, self.user.pk).status_code, 302)
        profile.refresh_from_db()
        self.assertEqual(profile.status_mestre, 'aprovado')
        self.assertFalse(TbTransacaoMestre.objects.exists())

    @override_settings(MASTER_ROSTER_MAX_NUMBER=76)
    def test_out_of_range_binding_changes_neither_permission_nor_wallet(self):
        self.master.numero = 77
        self.master.save(update_fields=['numero'])
        with self.assertRaises(ValidationError):
            self.bind()
        self.master.refresh_from_db()
        self.assertIsNone(self.master.user_id)
        self.assertFalse(TbPerfilMestre.objects.exists())
        self.assertFalse(TbTransacaoMestre.objects.exists())

    def test_registration_audit_is_bounded_superuser_only_and_does_not_match_names(self):
        from home.master_registration import registration_audit
        from home.db_access import ApiProblem
        from types import SimpleNamespace
        TbPerfilMestre.objects.create(user=self.user, status_mestre='pendente')
        with self.assertRaises(ApiProblem):
            registration_audit({}, SimpleNamespace(created_by=self.user))
        with self.assertRaises(ApiProblem):
            registration_audit({'limit':51}, SimpleNamespace(created_by=self.admin))
        result = registration_audit({'limit':1}, SimpleNamespace(created_by=self.admin))
        self.assertEqual(result['total'], 1)
        self.assertEqual(result['rows'][0]['identities'], [])
        self.assertFalse(TbTransacaoMestre.objects.exists())

    def quest(self, **changes):
        fields = dict(id='quest-1', guildId='guild-1', name='Aventura da noite', description='',
            questDate=timezone.make_aware(datetime(2026, 1, 2, 18)), playersAmount=5, rules='',
            type='one-shot', tableUrl='', questMaster=DID, createdBy=DID, isPublished=True,
            status='idle', createdAt=timezone.now(), updatedAt=timezone.now())
        fields.update(changes)
        return BotQuest.objects.create(**fields)

    def test_import_is_replay_safe_and_does_not_create_accounts_or_wallets(self):
        archive, created = import_archive(self.plan, 'market')
        self.assertFalse(created)
        self.assertEqual(archive.pk, self.archive.pk)
        self.assertFalse(import_archive(self.plan, 'another-source')[1])
        self.assertEqual(TbMestreLegado.objects.count(), 1)
        self.assertEqual(TbRegistroMestreLegado.objects.count(), 2)
        self.assertFalse(TbTransacaoMestre.objects.exists())
        changed = deepcopy(self.plan)
        changed['source_sha256'] = 'b' * 64
        with self.assertRaises(ValidationError):
            import_archive(changed, 'market')

    def test_manual_link_uses_account_id_not_similar_name_and_grants_once(self):
        self.bind()
        profile = UserProfile.objects.get(user=self.user)
        self.assertEqual((profile.moedas_mestragem, profile.moedas_evento, profile.mm_ganhas_total), (77, 3, 100))
        self.assertEqual(TbPerfilMestre.objects.get(user=self.user).status_mestre, 'aprovado')
        self.assertEqual(self.user.username, 'leehani17')
        self.assertEqual(TbAventuraMestre.objects.get().nome, 'Aventura da noite')
        self.assertEqual(TbTransacaoMestre.objects.aggregate(total=Sum('valor_mm'))['total'], 77)
        receipts = TbTransacaoMestre.objects.count()
        self.bind()
        self.assertEqual(TbTransacaoMestre.objects.count(), receipts)
        self.assertEqual(market_identity_context(self.user)['identidades_mestre'][0].numero, 49)

    def test_identity_only_binding_defers_wallet_without_losing_legacy_credit(self):
        before = UserProfile.objects.get(user=self.user)
        self.bind(wallet_mode='defer')
        self.master.refresh_from_db()
        after = UserProfile.objects.get(user=self.user)
        self.assertEqual(self.master.user_id, self.user.pk)
        self.assertIsNone(self.master.carteira_importada_em)
        self.assertEqual((after.moedas_mestragem, after.moedas_evento),
                         (before.moedas_mestragem, before.moedas_evento))
        self.assertFalse(TbTransacaoMestre.objects.exists())
        self.assertEqual(self.master.saldo_mm, 77)

    def test_non_superuser_cannot_attribute_funds(self):
        with self.assertRaises(PermissionDenied):
            bind_master(self.master.pk, self.user.pk, actor=self.user)
        self.assertFalse(TbTransacaoMestre.objects.exists())

    def test_existing_balance_requires_explicit_reconciliation(self):
        UserProfile.objects.filter(user=self.user).update(moedas_mestragem=20, moedas_evento=2)
        linked = self.bind()
        self.assertIsNone(linked.carteira_importada_em)
        self.assertTrue(linked.conciliacao)
        self.assertFalse(TbTransacaoMestre.objects.exists())
        with self.assertRaises(ValidationError):
            self.bind(wallet_mode='add', expected_balance=19, expected_events=2)
        self.bind(wallet_mode='add', expected_balance=20, expected_events=2)
        profile = UserProfile.objects.get(user=self.user)
        self.assertEqual((profile.moedas_mestragem, profile.moedas_evento), (97, 5))

    def test_replace_is_explicit_and_keeps_current_transactions(self):
        UserProfile.objects.filter(user=self.user).update(moedas_mestragem=50)
        old = TbTransacaoMestre.objects.create(mestre=self.user, valor_mm=50, saldo_mm=50)
        self.bind(wallet_mode='replace', expected_balance=50, expected_events=0)
        self.assertTrue(TbTransacaoMestre.objects.filter(pk=old.pk).exists())
        self.assertEqual(TbTransacaoMestre.objects.aggregate(total=Sum('valor_mm'))['total'], 77)

    def test_failing_receipt_rolls_back_identity_role_and_wallet(self):
        with patch.object(TbTransacaoMestre.objects, 'create', side_effect=ValueError('failed')):
            with self.assertRaises(ValueError):
                self.bind()
        self.master.refresh_from_db()
        self.assertIsNone(self.master.user_id)
        self.assertFalse(TbPerfilMestre.objects.exists())
        self.assertEqual(UserProfile.objects.get(user=self.user).moedas_mestragem, 0)

    def test_binding_cannot_move_claimed_identity_to_another_user(self):
        self.bind()
        with self.assertRaises(ValidationError):
            bind_master(self.master.pk, self.admin.pk, actor=self.admin)

    def test_suspended_master_is_not_reapproved(self):
        TbPerfilMestre.objects.create(user=self.user, status_mestre='suspenso')
        self.bind()
        self.assertEqual(TbPerfilMestre.objects.get(user=self.user).status_mestre, 'suspenso')

    def test_future_discord_account_claims_identity_once_not_by_name(self):
        self.master.discord_id = DID
        self.master.save(update_fields=['discord_id'])
        self.assertEqual(claim_discord_masters(self.user, DID), 0)
        UserProfile.objects.filter(user=self.user).update(discord_user_id=DID)
        with override_settings(MASTER_APPLICATIONS_OPEN=False):
            self.assertEqual(claim_discord_masters(self.user, DID), 1)
        participation = TbPerfilMestre.objects.get(user=self.user)
        self.assertEqual(participation.status_mestre, 'aprovado')
        self.assertEqual(participation.modo, 'ambos')
        self.master.refresh_from_db()
        self.assertEqual(self.master.user_id, self.user.pk)
        total = TbTransacaoMestre.objects.count()
        claim_discord_masters(self.user, DID)
        self.assertEqual(TbTransacaoMestre.objects.count(), total)

    def test_wallet_failure_does_not_undo_master_access(self):
        self.master.discord_id = DID
        self.master.save(update_fields=['discord_id'])
        UserProfile.objects.filter(user=self.user).update(discord_user_id=DID)
        from home.master_legacy import _wallet
        def fail_import(identity, user, **kwargs):
            if kwargs.get('mode') == 'defer':
                return _wallet(identity, user, **kwargs)
            raise ValidationError('Financial evidence unavailable')
        with patch('home.master_legacy._wallet', side_effect=fail_import):
            self.assertEqual(claim_discord_masters(self.user, DID), 1)
        self.master.refresh_from_db()
        self.assertEqual(self.master.user_id, self.user.pk)
        self.assertEqual(TbPerfilMestre.objects.get(user=self.user).status_mestre, 'aprovado')
        self.assertIsNone(self.master.carteira_importada_em)
        self.assertFalse(TbTransacaoMestre.objects.exists())

    def test_password_login_reconciles_existing_verified_discord(self):
        from home.signals import reconcile_registered_master_on_login
        with patch('home.master_legacy.claim_discord_masters') as reconcile:
            reconcile_registered_master_on_login(sender=type(self.user), user=self.user)
        reconcile.assert_called_once_with(self.user, '')

    def confirm(self, rows=None, checksum=None, actor=None):
        return confirm_discord_masters(self.archive.pk, checksum or self.archive.checksum,
            rows if rows is not None else [{'number': 49, 'discord_id': DID}],
            actor=actor or self.admin)

    def test_confirmation_reserves_departed_user_until_verified_oauth(self):
        report = self.confirm()
        self.assertEqual(report['masters'][0]['status'], 'reserved')
        self.assertFalse(TbTransacaoMestre.objects.exists())
        self.master.refresh_from_db()
        evidence = self.master.evidencia['manual_confirmation']
        self.assertEqual(evidence['actor_id'], self.admin.pk)
        self.confirm()
        self.master.refresh_from_db()
        self.assertEqual(self.master.evidencia['manual_confirmation'], evidence)
        UserProfile.objects.filter(user=self.user).update(discord_user_id=DID)
        claim_discord_masters(self.user, DID)
        self.assertEqual(UserProfile.objects.get(user=self.user).moedas_mestragem, 77)
        count = TbTransacaoMestre.objects.count()
        self.assertEqual(self.confirm()['masters'][0]['status'], 'linked')
        self.assertEqual(TbTransacaoMestre.objects.count(), count)

    def test_confirmation_never_cleared_by_missing_or_conflicting_bot_history(self):
        self.confirm()
        discover_bot_links(self.archive.pk)
        self.quest(createdBy=OTHER)
        discover_bot_links(self.archive.pk)
        self.master.refresh_from_db()
        self.assertEqual(self.master.discord_id, DID)
        self.assertEqual(self.master.evidencia['manual_confirmation']['discord_id'], DID)
        self.assertTrue(self.master.evidencia['master_author_conflict'])

    def test_confirmation_leaves_occupied_wallet_for_explicit_reconciliation(self):
        UserProfile.objects.filter(user=self.user).update(discord_user_id=DID, moedas_mestragem=20)
        result = self.confirm()['masters'][0]
        self.assertEqual(result['status'], 'linked')
        self.assertFalse(result['wallet_imported'])
        self.assertTrue(result['reconciliation'])
        self.assertEqual(UserProfile.objects.get(user=self.user).moedas_mestragem, 20)

    def test_confirmation_refuses_existing_account_or_discord_reassignment(self):
        UserProfile.objects.filter(user=self.user).update(discord_user_id=DID)
        UserProfile.objects.filter(user=self.admin).update(discord_user_id=OTHER)
        self.master.user = self.admin
        self.master.save(update_fields=['user'])
        with self.assertRaises(ValidationError):
            self.confirm()
        self.master.refresh_from_db()
        self.assertEqual(self.master.discord_id, '')
        self.master.user, self.master.discord_id = None, OTHER
        self.master.save(update_fields=['user', 'discord_id'])
        with self.assertRaises(ValidationError):
            self.confirm()

    def test_confirmation_validates_ids_source_and_rolls_back_entire_batch(self):
        for rows in ([{'number': 49, 'discord_id': int(DID)}],
                     [{'number': 49, 'discord_id': DID}] * 2,
                     [{'number': 49, 'discord_id': '<@' + DID + '>'}]):
            with self.assertRaises(ValidationError):
                self.confirm(rows)
        with self.assertRaises(ValidationError):
            self.confirm(checksum='b' * 64)
        with self.assertRaises(PermissionDenied):
            self.confirm(actor=self.user)
        UserProfile.objects.filter(user=self.user).update(discord_user_id=DID)
        with self.assertRaises(ValidationError):
            self.confirm([{'number': 49, 'discord_id': DID}, {'number': 999, 'discord_id': OTHER}])
        self.master.refresh_from_db()
        self.assertEqual(self.master.discord_id, '')
        self.assertIsNone(self.master.user_id)
        self.assertFalse(TbTransacaoMestre.objects.exists())

    def test_confirmation_cannot_reserve_same_discord_for_two_masters(self):
        TbMestreLegado.objects.create(importacao=self.archive, numero=50,
            nome='Outro mestre', rotulo_original='F50', saldo_mm=0, discord_id=DID)
        with self.assertRaises(ValidationError):
            self.confirm()

    def test_unique_bot_author_and_master_matches_title_date_then_claims(self):
        self.quest()
        UserProfile.objects.filter(user=self.user).update(discord_user_id=DID)
        result = discover_bot_links(self.archive.pk)
        self.assertEqual(result['unique_authors'], 1)
        self.master.refresh_from_db()
        self.assertEqual(self.master.user_id, self.user.pk)
        self.assertEqual(self.master.registros.get(tipo='adventure').bot_quest_id, 'quest-1')

    def test_prisma_utc_naive_dates_use_brazil_day_not_server_day(self):
        from datetime import date, timezone as tz
        from django.test import override_settings
        with override_settings(TIME_ZONE='UTC'):
            self.assertEqual(quest_local_date(datetime(2026, 1, 3, 1)), date(2026, 1, 2))
            self.assertEqual(quest_local_date(datetime(2026, 1, 3, 1, tzinfo=tz.utc)), date(2026, 1, 2))
            self.assertEqual(quest_local_date(datetime(2026, 1, 3, 4)), date(2026, 1, 3))
            self.assertIsNone(quest_local_date(None))

    def test_discovery_accepts_raw_prisma_datetime_without_rewriting_source(self):
        quest = self.quest()
        raw = datetime(2026, 1, 3, 1)
        original = BotQuest.from_db.__func__
        def prisma_row(cls, db, fields, values):
            row = original(cls, db, fields, values)
            if row.pk == quest.pk:
                row.questDate = raw
            return row
        with patch.object(BotQuest, 'from_db', classmethod(prisma_row)):
            self.assertEqual(discover_bot_links(self.archive.pk)['unique_authors'], 1)
        quest.refresh_from_db()
        self.assertEqual(timezone.localtime(quest.questDate).date().isoformat(), '2026-01-02')

    def test_mixed_authors_in_master_history_do_not_claim(self):
        self.quest()
        self.quest(id='quest-2', createdBy=OTHER)
        self.assertEqual(discover_bot_links(self.archive.pk)['unique_authors'], 0)
        self.assertFalse(TbTransacaoMestre.objects.exists())

    def test_master_and_creator_disagreement_is_a_conflict(self):
        self.quest(questMaster=OTHER)
        self.assertEqual(discover_bot_links(self.archive.pk)['unique_authors'], 0)
        self.master.refresh_from_db()
        self.assertTrue(self.master.evidencia['master_author_conflict'])

    def test_missing_adventure_or_unknown_author_does_not_claim(self):
        self.quest(name='Another adventure')
        self.assertEqual(discover_bot_links(self.archive.pk)['unique_authors'], 0)
        BotQuest.objects.update(name='Aventura da noite', createdBy='unknown')
        self.assertEqual(discover_bot_links(self.archive.pk)['unique_authors'], 0)

    def test_duplicate_quest_name_and_date_are_not_guessed(self):
        self.quest()
        self.quest(id='quest-2')
        self.assertEqual(discover_bot_links(self.archive.pk)['unique_authors'], 0)
        self.assertFalse(self.master.registros.exclude(bot_quest_id='').exists())

    def test_quarantined_adventure_prevents_claim_of_complete_history(self):
        self.quest()
        self.archive.dados['warnings'] = [{'quarantine': {'master_number': 49, 'kind': 'adventure'}}]
        self.archive.save(update_fields=['dados'])
        self.assertEqual(discover_bot_links(self.archive.pk)['unique_authors'], 0)

    def test_multiple_guilds_require_explicit_scope(self):
        self.quest()
        self.quest(id='quest-2', guildId='other-guild')
        with self.assertRaises(ValidationError):
            discover_bot_links(self.archive.pk)

    def test_proven_first_gold_purchase_is_permanent_without_monthly_charge(self):
        purchase = self.master.registros.get(tipo='purchase')
        purchase.titulo, purchase.valor_mm = 'Mestre Ouro', -5000
        purchase.save(update_fields=['titulo', 'valor_mm'])
        self.bind()
        self.assertTrue(MestreOuroDireito.objects.filter(user=self.user).exists())
        self.assertFalse(TbTransacaoMestre.objects.filter(tipo='mensalidade').exists())
        self.assertIsNone(UserProfile.objects.get(user=self.user).mestre_ouro_proximo_pgto)

    def test_package_preflight_and_bounded_report(self):
        from home.db_access import ApiProblem
        for payload in ({'package': '../bad', 'source_sha256': 'x'}, {'package': 'x', 'source_sha256': 'x', 'sql': 'x'}):
            with self.assertRaises(ApiProblem):
                legacy_import_preview(payload, None)
        report = legacy_report_operation({'import_id': self.archive.pk}, None)
        self.assertEqual(report['total'], 1)
        with self.assertRaises(ApiProblem):
            legacy_report_operation({'import_id': self.archive.pk, 'limit': 51}, None)

    def test_full_bundled_copy_imports_without_live_database(self):
        root = Path(__file__).resolve().parents[1]
        plan = json.loads((root / 'home/content_packages/master_legacy/mercado-mestres-20261104.json').read_text(encoding='utf-8'))
        archive, created = import_archive(plan, 'bundled')
        self.assertTrue(created)
        self.assertEqual(archive.mestres.count(), 74)
        self.assertEqual(TbRegistroMestreLegado.objects.filter(mestre__importacao=archive).count(), 778)
        self.assertFalse(TbTransacaoMestre.objects.exists())

    def api_key(self, scopes, actor=None):
        secret = ManagedApiKey.new_secret()
        ManagedApiKey.objects.create(name='legacy-test', prefix=secret[:16],
            secret_hash=ManagedApiKey.digest(secret), scopes=scopes, created_by=actor)
        return {'secure': True, 'HTTP_AUTHORIZATION': 'Bearer ' + secret,
                'HTTP_IDEMPOTENCY_KEY': str(uuid4())}

    def test_http_read_key_cannot_import_or_bind(self):
        headers = self.api_key(['read'], self.admin)
        response = self.client.post('/operations/master-legacy-bind/',
            data=json.dumps({'identity_id': self.master.pk, 'username': self.user.username}),
            content_type='application/json', **headers)
        self.assertEqual(response.status_code, 403)
        self.assertFalse(TbTransacaoMestre.objects.exists())
        report = self.client.post('/operations/master-legacy-report/',
            data=json.dumps({'import_id': self.archive.pk}), content_type='application/json', **headers)
        self.assertEqual(report.status_code, 200, report.content)

    def test_http_binding_requires_superuser_creator_and_is_replay_safe(self):
        payload = json.dumps({'identity_id': self.master.pk, 'username': 'LEEHANI17'})
        rejected = self.client.post('/operations/master-legacy-bind/', data=payload,
            content_type='application/json', **self.api_key(['publish'], self.user))
        self.assertEqual(rejected.status_code, 403)
        headers = self.api_key(['publish'], self.admin)
        with patch('home.master_legacy_api._backup'):
            response = self.client.post('/operations/master-legacy-bind/', data=payload,
                content_type='application/json', **headers)
            repeat = self.client.post('/operations/master-legacy-bind/', data=payload,
                content_type='application/json', **headers)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(repeat.json(), response.json())
        self.assertEqual(TbTransacaoMestre.objects.count(), 3)

    def test_http_backup_failure_does_not_bind_account(self):
        with patch('home.master_legacy_api._backup', side_effect=ValueError('backup unavailable')):
            response = self.client.post('/operations/master-legacy-bind/',
                data=json.dumps({'identity_id': self.master.pk, 'username': self.user.username}),
                content_type='application/json', **self.api_key(['publish'], self.admin))
        self.assertEqual(response.status_code, 409)
        self.master.refresh_from_db()
        self.assertIsNone(self.master.user_id)

    def test_http_confirmation_auth_backup_and_replay(self):
        payload = json.dumps({'import_id': self.archive.pk, 'source_sha256': self.archive.checksum,
                              'confirmations': [{'number': 49, 'discord_id': DID}]})
        route = '/operations/master-legacy-confirm/'
        for scopes, actor in [(['read'], self.admin), (['publish'], self.user)]:
            response = self.client.post(route, data=payload, content_type='application/json',
                                         **self.api_key(scopes, actor))
            self.assertEqual(response.status_code, 403, response.content)
        with patch('home.master_legacy_api._backup', side_effect=ValueError('backup unavailable')):
            response = self.client.post(route, data=payload, content_type='application/json',
                                         **self.api_key(['publish'], self.admin))
        self.assertEqual(response.status_code, 409)
        self.master.refresh_from_db()
        self.assertEqual(self.master.discord_id, '')
        headers = self.api_key(['publish'], self.admin)
        with patch('home.master_legacy_api._backup') as backup:
            response = self.client.post(route, data=payload, content_type='application/json', **headers)
            repeat = self.client.post(route, data=payload, content_type='application/json', **headers)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(repeat.json(), response.json())
        backup.assert_called_once()

    def test_bot_duration_excludes_pauses_and_rejects_bad_timeline(self):
        events = [{'eventType': action, 'date': stamp} for action, stamp in [
            ('run', '2026-01-02T12:00:00Z'), ('pause', '2026-01-02T12:30:00Z'),
            ('run', '2026-01-02T14:00:00Z'), ('finish', '2026-01-02T14:30:00Z')]]
        self.assertEqual(active_seconds(events), (3600, True))
        self.assertEqual(active_seconds([]), (0, True))
        self.assertEqual(active_seconds(events[::-1]), (0, False))
        self.assertEqual(active_seconds([{'eventType': 'run', 'date': 'bad'}]), (0, False))
        self.assertEqual(active_seconds('not-a-list'), (0, False))

    def test_private_bot_audit_includes_unknown_owners_cancelled_and_no_time(self):
        self.quest(guildId=GUILD, status='cancelled', isPublished=False)
        self.quest(id='quest-2', guildId=GUILD, status='finished', questMaster='', timeEvents=[])
        result = mission_audit(self.archive.pk, GUILD, limit=1)
        self.assertEqual(result['total'], 2)
        first = result['rows'][0]
        self.assertEqual(first['owner_state'], 'unmapped_discord')
        self.assertEqual(first['ineligible_reasons'], ['cancelled', 'no_recorded_duration'])
        self.assertFalse(first['viable_for_review'])
        following = mission_audit(self.archive.pk, GUILD, after_id=result['next_after_id'], limit=1)
        self.assertEqual(following['rows'][0]['owner_state'], 'missing_or_unrecognized')
        self.assertEqual(following['source_revision'], result['source_revision'])
        self.assertIsNone(following['next_after_id'])

    def bot_plan(self):
        return backfill_plan(self.archive.pk, self.archive.checksum, GUILD, ['history:3:adventure'])

    def apply_bot(self, version):
        return backfill_apply(self.archive.pk, self.archive.checksum, GUILD,
                              ['history:3:adventure'], version, actor=self.admin)

    def test_approved_private_legacy_has_no_fake_duration_or_second_credit(self):
        self.bind()
        receipts = TbTransacaoMestre.objects.count()
        plan = self.bot_plan()
        self.assertEqual(plan['rows'][0]['financial_state'], 'already_in_wallet')
        self.assertEqual(self.apply_bot(plan['base_version'])['created'], 1)
        quest = BotQuest.objects.get()
        self.assertFalse(quest.isPublished)
        self.assertIsNone(quest.channelId)
        self.assertEqual(quest.status, 'finished')
        self.assertEqual(quest.timeEvents, [])
        self.assertIsNone(quest.startDate)
        self.assertIsNone(quest.endDate)
        self.assertEqual(quest.rewardAventurasOverride, 0)
        self.assertEqual(quest.questMaster, self.master.rotulo_original)
        self.assertEqual(json.loads(quest.description)['date_precision'], 'day')
        self.assertEqual(TbTransacaoMestre.objects.count(), receipts)
        self.assertEqual(UserProfile.objects.get(user=self.user).moedas_mestragem, 77)
        repeat = self.apply_bot(self.bot_plan()['base_version'])
        self.assertEqual((repeat['created'], repeat['already_linked']), (0, 1))
        self.assertEqual(BotQuest.objects.count(), 1)

    def test_legacy_bot_record_keeps_unclaimed_credit_reserved(self):
        plan = self.bot_plan()
        self.assertEqual(plan['rows'][0]['financial_state'], 'reserved_in_legacy_balance')
        self.apply_bot(plan['base_version'])
        self.assertFalse(TbTransacaoMestre.objects.exists())
        self.master.refresh_from_db()
        self.assertEqual(self.master.saldo_mm, 77)
        result = mission_audit(self.archive.pk, GUILD)
        self.assertTrue(result['rows'][0]['legacy_baseline_record'])
        self.assertEqual(result['rows'][0]['owner_state'], 'identified')
        self.assertEqual(result['rows'][0]['ineligible_reasons'], ['no_recorded_duration'])

    def test_existing_mission_same_title_date_is_reviewed_not_duplicated(self):
        self.quest(guildId=GUILD, questMaster=OTHER, name='Aventura, da noite!')
        plan = self.bot_plan()
        self.assertEqual(plan['rows'][0]['action'], 'review_existing')
        result = self.apply_bot(plan['base_version'])
        self.assertEqual(result['created'], 0)
        self.assertEqual(len(result['review_existing']), 1)
        self.assertEqual(BotQuest.objects.count(), 1)

    def test_bot_backfill_rejects_stale_missing_date_and_cross_guild(self):
        plan = self.bot_plan()
        self.quest(guildId=GUILD)
        with self.assertRaises(ValidationError):
            self.apply_bot(plan['base_version'])
        record = self.master.registros.get(tipo='adventure')
        record.bot_quest_id = 'quest-1'
        record.save(update_fields=['bot_quest_id'])
        BotQuest.objects.update(guildId=OTHER)
        with self.assertRaises(ValidationError):
            self.bot_plan()
        record.bot_quest_id, record.data = '', None
        record.save(update_fields=['bot_quest_id', 'data'])
        with self.assertRaises(ValidationError):
            self.bot_plan()
        self.assertEqual(BotQuest.objects.count(), 1)

    def test_backfill_failure_rolls_back_bot_insert_and_keeps_wallet(self):
        self.bind()
        receipts = TbTransacaoMestre.objects.count()
        plan = self.bot_plan()
        with patch.object(TbRegistroMestreLegado, 'save', side_effect=ValueError('link failed')):
            with self.assertRaises(ValueError):
                self.apply_bot(plan['base_version'])
        self.assertFalse(BotQuest.objects.exists())
        self.assertEqual(self.master.registros.get(tipo='adventure').bot_quest_id, '')
        self.assertEqual(TbTransacaoMestre.objects.count(), receipts)
        self.assertEqual(UserProfile.objects.get(user=self.user).moedas_mestragem, 77)

    def test_http_bot_requests_refuse_extra_fields_and_read_only_mutation(self):
        route = '/operations/master-missions-audit/'
        for payload in ({'import_id': self.archive.pk, 'guild_id': GUILD, 'sql': 'x'},
                        {'import_id': self.archive.pk, 'guild_id': GUILD, 'limit': 51},
                        {'import_id': self.archive.pk, 'guild_id': int(GUILD)}):
            response = self.client.post(route, data=json.dumps(payload),
                content_type='application/json', **self.api_key(['read'], self.admin))
            self.assertEqual(response.status_code, 400, response.content)
        payload = {'import_id': self.archive.pk, 'source_sha256': self.archive.checksum,
                   'guild_id': GUILD, 'record_keys': ['history:3:adventure'], 'admin_validated': True,
                   'base_version': self.bot_plan()['base_version']}
        response = self.client.post('/operations/master-legacy-bot-apply/', data=json.dumps(payload),
            content_type='application/json', **self.api_key(['read'], self.admin))
        self.assertEqual(response.status_code, 403)
        self.assertFalse(BotQuest.objects.exists())

    def test_http_bot_operations_permissions_backup_replay_and_json_dates(self):
        payload = {'import_id': self.archive.pk, 'source_sha256': self.archive.checksum,
                   'guild_id': GUILD, 'record_keys': ['history:3:adventure'], 'admin_validated': True}
        rejected = self.client.post('/operations/master-legacy-bot-preview/', data=json.dumps(payload),
            content_type='application/json', **self.api_key(['read'], self.user))
        self.assertEqual(rejected.status_code, 403)
        preview = self.client.post('/operations/master-legacy-bot-preview/', data=json.dumps(payload),
            content_type='application/json', **self.api_key(['read'], self.admin))
        self.assertEqual(preview.status_code, 200, preview.content)
        payload['base_version'] = preview.json()['base_version']
        with patch('home.master_legacy_api._backup', side_effect=ValueError('backup unavailable')):
            failed = self.client.post('/operations/master-legacy-bot-apply/', data=json.dumps(payload),
                content_type='application/json', **self.api_key(['publish'], self.admin))
        self.assertEqual(failed.status_code, 409)
        self.assertFalse(BotQuest.objects.exists())
        headers = self.api_key(['publish'], self.admin)
        with patch('home.master_legacy_api._backup') as backup:
            first = self.client.post('/operations/master-legacy-bot-apply/', data=json.dumps(payload),
                content_type='application/json', **headers)
            repeat = self.client.post('/operations/master-legacy-bot-apply/', data=json.dumps(payload),
                content_type='application/json', **headers)
        self.assertEqual(first.status_code, 200, first.content)
        self.assertEqual(first.json(), repeat.json())
        backup.assert_called_once()
        audit = self.client.post('/operations/master-missions-audit/',
            data=json.dumps({'import_id': self.archive.pk, 'guild_id': GUILD}),
            content_type='application/json', **self.api_key(['read'], self.admin))
        self.assertEqual(audit.status_code, 200, audit.content)
        self.assertEqual(audit.json()['rows'][0]['date'], '2026-01-02')

    def review_payload(self, **changes):
        row = {'quest_id': 'quest-1', 'decision': 'confirmed', 'adventures': 1,
               'financial_mode': 'new', 'master_mm': 130, 'event_coins': 1,
               'note': 'Confirmacao explicita do PO.'}
        row.update(changes)
        return {'import_id': self.archive.pk, 'guild_id': GUILD, 'items': [row]}

    def review_apply(self, payload):
        plan = review_preview(payload)
        return review_apply({**payload, 'base_version': plan['base_version']}, actor=self.admin)

    def test_staff_review_new_reward_is_delivered_once_without_rewriting_telemetry(self):
        quest = self.quest(guildId=GUILD, tags='{"evento"}', allowedRanks='{"rank-role"}')
        UserProfile.objects.filter(user=self.user).update(discord_user_id=DID)
        payload = self.review_payload()
        self.review_apply(payload)
        quest.refresh_from_db()
        self.assertEqual(quest.timeEvents, [])
        self.assertEqual(quest.tags, '{"evento"}')
        self.assertEqual(quest.allowedRanks, '{"rank-role"}')
        self.assertEqual(quest.rewardAventurasOverride, 1)
        self.assertEqual(quest.status, 'finished')
        self.review_apply(payload)
        profile = UserProfile.objects.get(user=self.user)
        self.assertEqual((profile.moedas_mestragem, profile.moedas_evento), (130, 1))
        self.assertEqual(TbTransacaoMestre.objects.count(), 1)
        self.assertEqual(TbAventuraMestre.objects.count(), 1)

    def test_review_pending_reward_claims_only_verified_owner_once(self):
        self.quest(guildId=GUILD)
        self.review_apply(self.review_payload(master_name='Casper'))
        self.assertFalse(TbTransacaoMestre.objects.exists())
        self.assertEqual(claim_discord_masters(self.user, DID), 0)
        self.assertFalse(TbTransacaoMestre.objects.exists())
        UserProfile.objects.filter(user=self.user).update(discord_user_id=DID)
        claim_discord_masters(self.user, DID)
        claim_discord_masters(self.user, DID)
        self.assertEqual(TbTransacaoMestre.objects.count(), 1)
        self.assertEqual(UserProfile.objects.get(user=self.user).moedas_mestragem, 130)
        self.assertEqual(TbPerfilMestre.objects.get(user=self.user).status_mestre, 'aprovado')

    def test_baseline_review_links_native_record_without_repaying(self):
        self.bind()
        self.quest(guildId=GUILD)
        count = TbTransacaoMestre.objects.count()
        self.review_apply(self.review_payload(financial_mode='baseline', master_mm=100,
            event_coins=0, legacy_key='history:3:adventure'))
        self.assertEqual(TbTransacaoMestre.objects.count(), count)
        self.assertEqual(UserProfile.objects.get(user=self.user).moedas_mestragem, 77)
        self.assertEqual(self.master.registros.get(tipo='adventure').bot_quest_id, 'quest-1')
        with self.assertRaises(ValidationError):
            review_preview(self.review_payload())

    def test_settled_and_duplicate_decisions_never_pay_or_delete_records(self):
        self.quest(guildId=GUILD, status='paused')
        self.quest(id='quest-2', guildId=GUILD)
        self.review_apply(self.review_payload(decision='settled', financial_mode='settled', adventures=2))
        self.review_apply(self.review_payload(quest_id='quest-2', decision='duplicate', financial_mode='none',
            adventures=0, master_mm=None, event_coins=0, canonical_id='quest-1'))
        self.assertFalse(TbTransacaoMestre.objects.exists())
        self.assertEqual(BotQuest.objects.count(), 2)
        duplicate = BotQuest.objects.get(pk='quest-2')
        self.assertFalse(duplicate.isPublished)
        self.assertEqual(duplicate.rewardAventurasOverride, 0)
        rows = mission_audit(self.archive.pk, GUILD)['rows']
        self.assertIn('duplicate', next(r for r in rows if r['id'] == 'quest-2')['ineligible_reasons'])

    def test_standard_quote_uses_pinned_historic_dedicated_rank_and_event(self):
        quest = self.quest(guildId=GUILD, dedicatedRankId='old-rank', allowedRanks='{"role"}', tags='{"evento"}')
        now = timezone.now()
        BotDedicatedRank.objects.create(id='old-rank', guildId=GUILD,
            rankings=[{'rankName': 'Rank da epoca', 'rewardPerProgression': 30, 'maxTotalReward': 90}],
            validFrom=now, validUntil=now, isActive=False, createdAt=now, updatedAt=now)
        result = quote_reward(quest, 1, {'role': 'Rank da epoca'})
        self.assertEqual((result['mm'], result['event_coins'], result['dedicated_bonus']), (130, 1, 30))
        self.assertEqual(quote_reward(quest, 12, {'role': 'Rank da epoca'})['dedicated_bonus'], 90)
        with self.assertRaises(ValidationError):
            quote_reward(quest, 1, {})

    def test_staff_review_rejects_stale_preview_and_rolls_back_paid_changes(self):
        self.quest(guildId=GUILD)
        payload = self.review_payload()
        plan = review_preview(payload)
        BotQuest.objects.filter(pk='quest-1').update(name='changed')
        with self.assertRaises(ValidationError):
            review_apply({**payload, 'base_version': plan['base_version']}, actor=self.admin)
        self.assertFalse(TbRevisaoMissaoBot.objects.exists())
        UserProfile.objects.filter(user=self.user).update(discord_user_id=DID)
        self.review_apply(payload)
        with self.assertRaises(ValidationError):
            review_preview(self.review_payload(master_mm=140))
        self.assertEqual(UserProfile.objects.get(user=self.user).moedas_mestragem, 130)

    def test_http_staff_review_serialization_permissions_and_replay(self):
        self.quest(guildId=GUILD)
        payload = self.review_payload(financial_mode='settled', decision='settled', adventures=2)
        route = '/operations/master-mission-review-preview/'
        response = self.client.post(route, data=json.dumps(payload), content_type='application/json',
            **self.api_key(['read'], self.user))
        self.assertEqual(response.status_code, 403)
        response = self.client.post(route, data=json.dumps(payload), content_type='application/json',
            **self.api_key(['read'], self.admin))
        self.assertEqual(response.status_code, 200, response.content)
        payload['base_version'] = response.json()['base_version']
        route = '/operations/master-mission-review-apply/'
        response = self.client.post(route, data=json.dumps(payload), content_type='application/json',
            **self.api_key(['read'], self.admin))
        self.assertEqual(response.status_code, 403)
        headers = self.api_key(['publish'], self.admin)
        with patch('home.master_legacy_api._backup') as backup:
            first = self.client.post(route, data=json.dumps(payload), content_type='application/json', **headers)
            repeat = self.client.post(route, data=json.dumps(payload), content_type='application/json', **headers)
        self.assertEqual(first.status_code, 200, first.content)
        self.assertEqual(first.json(), repeat.json())
        backup.assert_called_once()
        self.assertFalse(TbTransacaoMestre.objects.exists())

    def test_event_confirmation_preserves_other_tags_and_uses_event_coin_rule(self):
        self.quest(guildId=GUILD, tags='{"tag-original"}')
        UserProfile.objects.filter(user=self.user).update(discord_user_id=DID)
        self.review_apply(self.review_payload(adventures=2, master_mm=300, event_coins=None, event=True))
        quest = BotQuest.objects.get(pk='quest-1')
        self.assertEqual(quest.tags, '{"tag-original","evento"}')
        self.assertEqual(UserProfile.objects.get(user=self.user).moedas_evento, 3)
        self.assertEqual(quest.timeEvents, [])

    def test_review_reward_context_preserves_boost_and_never_multiplies_rank_bonus(self):
        self.quest(guildId=GUILD)
        context = {'base_adventures': 2, 'multiplier': 2, 'reason': 'weekend_double',
                   'base_mm': 400, 'dedicated_bonus_mm': 60, 'final_mm': 460,
                   'source': 'staff_confirmation'}
        payload = self.review_payload(financial_mode='settled', decision='settled',
            adventures=4, master_mm=460, event_coins=0, reward_context=context,
            mission_details={'summary': 'Resumo preservado.', 'participants': ['A', 'B'],
                'source_url': f'https://discord.com/channels/{GUILD}/323456789012345678/423456789012345678'})
        self.review_apply(payload)
        review = TbRevisaoMissaoBot.objects.get(quest_id='quest-1')
        self.assertEqual(review.evidence['reward_context'], context)
        self.assertEqual(review.evidence['mission_details']['participants'], ['A', 'B'])
        self.assertFalse(TbTransacaoMestre.objects.exists())
        # An older client must not erase the structured evidence on a later review.
        payload['items'][0].pop('reward_context')
        payload['items'][0].pop('mission_details')
        self.review_apply(payload)
        review.refresh_from_db()
        self.assertEqual(review.evidence['reward_context'], context)
        self.assertEqual(review.evidence['mission_details']['summary'], 'Resumo preservado.')

    def test_review_rejects_inconsistent_boost_without_mutating_money(self):
        self.quest(guildId=GUILD)
        context = {'base_adventures': 2, 'multiplier': 2, 'reason': 'weekend_double',
                   'base_mm': 400, 'dedicated_bonus_mm': 120, 'final_mm': 460,
                   'source': 'staff_confirmation'}
        with self.assertRaises(ValidationError):
            review_preview(self.review_payload(adventures=4, master_mm=460, reward_context=context))
        context.update(dedicated_bonus_mm=60, base_adventures=3)
        with self.assertRaises(ValidationError):
            review_preview(self.review_payload(adventures=4, master_mm=460, reward_context=context))
        self.assertFalse(TbRevisaoMissaoBot.objects.exists())
        self.assertFalse(TbTransacaoMestre.objects.exists())

    def test_review_rejects_foreign_references_and_unbounded_participants(self):
        self.quest(guildId=GUILD)
        for details in ({'source_url': 'https://example.com/secret'},
                        {'source_url': 'https://discord.com/channels/999/123/456'},
                        {'participants': ['A'] * 31}, {'summary': 'A' * 12001}):
            with self.subTest(details=list(details)):
                with self.assertRaises(ValidationError):
                    review_preview(self.review_payload(mission_details=details))

    def test_no_record_is_unpublished_but_keeps_evidence_and_receipts(self):
        quest = self.quest(guildId=GUILD, status='finished', isPublished=True)
        self.review_apply(self.review_payload(decision='no_record', financial_mode='none',
            adventures=0, master_mm=None, event_coins=0))
        quest.refresh_from_db()
        self.assertFalse(quest.isPublished)
        self.assertEqual(quest.rewardAventurasOverride, 0)
        self.assertTrue(TbRevisaoMissaoBot.objects.filter(quest_id=quest.pk).exists())
        self.assertEqual(BotQuest.objects.count(), 1)
        self.assertFalse(TbTransacaoMestre.objects.exists())


if ISOLATED:
    if connection.settings_dict['NAME'] != ':memory:' or 'bonfire.settings' in sys.modules:
        raise RuntimeError('Only isolated memory SQLite allowed')
    with connection.schema_editor() as editor:
        from django.apps import apps
        for model in apps.get_models():
            if model._meta.managed and not model._meta.proxy:
                editor.create_model(model)
        for model in (BotQuest, BotDedicatedRank):
            editor.create_model(model)
    unittest.main(argv=[sys.argv[0]], verbosity=2)
