"""Focused batch tests; --isolated uses SQLite memory, never the configured DB."""
import sys
from pathlib import Path

ISOLATED = __name__ == '__main__' and '--isolated' in sys.argv
if ISOLATED:
    import os
    os.environ['DJANGO_SECRET_KEY'] = 'isolated-maintenance-only'
    os.environ['DJANGO_DEBUG'] = 'true'
    os.environ['POSTGRES_URL'] = 'postgresql://isolated:unused@127.0.0.1:1/unused'
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bonfire.settings')
    from bonfire import settings as project_settings
    project_settings.DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':memory:'}}
    project_settings.SECRET_KEY = 'isolated-maintenance-only'
    project_settings.DEBUG = True
    project_settings.ALLOWED_HOSTS = ['testserver', 'localhost', '127.0.0.1']
    project_settings.ASAAS_API_KEY = ''
    project_settings.ASAAS_API_BASE = 'https://api.asaas.com/v3'
    project_settings.EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
    project_settings.PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']
    import django
    django.setup()

import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from django.apps import apps
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import connection, IntegrityError, transaction
from django.test import TestCase, override_settings
from django.urls import reverse

from home.email_cleanup_v1 import cleanup_and_index
from home.email_identity import available_email
from home.master_application import MasterApplicationForm
from home.master_application_testdata import application_data
from home.models import (UserProfile, UserAccountMergeReceipt, TbImportacaoMestre,
                         TbMestreLegado, TbPerfilMestre, TbAventuraMestre, TbRegistroMestreLegado,
                         TbRevisaoMissaoBot, BotQuest, BotMember, BotTransaction, BotDedicatedRank)
from home.master_roster import adventure_amount, mission_history, _history_matches
from home.views import _create_asaas_checkout, StaffSignupForm


class MaintenanceBatchTests(TestCase):
    def test_ads_txt_uses_seller_id_without_changing_ad_client(self):
        for publisher in ('ca-pub-1634793837919535', 'pub-1634793837919535'):
            with self.subTest(publisher=publisher), override_settings(ADSENSE_PUBLISHER_ID=publisher):
                response = self.client.get(reverse('ads_txt'))
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.content.decode(),
                    'google.com, pub-1634793837919535, DIRECT, f08c47fec0942fa0\n')
        with override_settings(ADSENSE_ENABLED=True, ADSENSE_PUBLISHER_ID='ca-pub-1634793837919535'):
            response = self.client.get(reverse('home'))
            self.assertContains(response, 'client=ca-pub-1634793837919535')
            self.assertContains(response, 'js/privacy-choices.js')
            self.assertContains(response, 'data-privacy-choices hidden')
            login = self.client.get(reverse('login'))
            self.assertNotContains(login, 'js/privacy-choices.js')
            self.assertNotContains(login, 'data-privacy-choices')
            self.assertNotContains(login, 'pagead/js/adsbygoogle.js')

    def test_invalid_ads_txt_configuration_does_not_publish_an_invalid_seller(self):
        for publisher in ('', 'ca-pub-123', 'pub-1234567890123456\ninjected', 'unrelated'):
            with self.subTest(publisher=publisher), override_settings(ADSENSE_PUBLISHER_ID=publisher):
                self.assertEqual(self.client.get(reverse('ads_txt')).status_code, 404)

    def test_history_matches_single_title_even_when_reporting_dates_differ(self):
        from datetime import date, datetime, timezone
        for offset in (1, 2, 14, 90):
            from datetime import timedelta
            day = date(2026, 1, 1)
            record = SimpleNamespace(pk=1, bot_quest_id='', titulo='A jornada!', data=day+timedelta(days=offset))
            quest = SimpleNamespace(pk='bot', name='A jornada.', type='normal',
                                    questDate=datetime(2026,1,1,12,tzinfo=timezone.utc))
            self.assertEqual(_history_matches([record], {'bot':quest}, {}), {1:quest})

    def test_repeated_titles_are_not_collapsed_by_nearest_date(self):
        from datetime import date, datetime, timezone
        record = SimpleNamespace(pk=1, bot_quest_id='', titulo='Repeated', data=date(2026,1,2))
        quests = {str(day): SimpleNamespace(pk=str(day), name='Repeated', type='normal',
                  questDate=datetime(2026,1,day,12,tzinfo=timezone.utc)) for day in (1,3)}
        self.assertEqual(_history_matches([record], quests, {}), {})
        record.data = date(2026,1,1)
        self.assertEqual(_history_matches([record], quests, {}), {1:quests['1']})
        duplicate = SimpleNamespace(pk=2, bot_quest_id='', titulo='Repeated', data=record.data)
        self.assertEqual(_history_matches([record, duplicate], quests, {}), {})
        self.assertEqual(_history_matches([record], quests, {'1':SimpleNamespace(decision='no_record'),
                                                          '3':SimpleNamespace(decision='duplicate')}), {})

    def test_no_partial_customer_and_all_item_names_fit_gateway(self):
        from home.views import _ASAAS_CHECKOUT_PRODUCTS
        for product in _ASAAS_CHECKOUT_PRODUCTS.values():
            order = SimpleNamespace(mode='single', email='local@example.test', product_code='test',
                                    external_reference='local-order', save=lambda **kw: None)
            with patch('home.views._asaas_api_request', return_value={'id':'checkout-only'}) as send:
                _create_asaas_checkout(order, product, 'A long customer name', 'https://example.test/result')
            payload = send.call_args.args[2]
            self.assertNotIn('customerData', payload)
            self.assertLessEqual(len(payload['items'][0]['name']), 30)

    def test_form_has_six_reference_questions_and_limits_three_themes(self):
        form = MasterApplicationForm(application_data())
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(len(form.snapshot()['questions']), 6)
        data = application_data()
        data['tematicas'] = form.schema['questions'][4]['choices'][:4]
        self.assertFalse(MasterApplicationForm(data).is_valid())
        self.assertFalse(MasterApplicationForm({}).is_valid())
        data['tematicas'] = ['Outro']
        self.assertFalse(MasterApplicationForm(data).is_valid())
        data['tematicas_outro'] = 'Investigação política'
        self.assertTrue(MasterApplicationForm(data).is_valid())

    def test_signup_requires_unique_normalized_email(self):
        get_user_model().objects.create_user('existing', email='One@Example.test')
        with self.assertRaises(ValidationError):
            available_email(' one@example.test ')
        self.assertTrue(StaffSignupForm.base_fields['email'].required)

    def test_unregistered_master_has_numbered_portfolio_without_fake_account(self):
        archive = TbImportacaoMestre.objects.create(fonte='roster-test', checksum='c'*64, dados={})
        identity = TbMestreLegado.objects.create(importacao=archive, numero=9, nome='Mestre Keter', rotulo_original='Fogueira 09')
        response = self.client.get(reverse('masters_directory'))
        self.assertContains(response, 'Fogueira 09')
        self.assertContains(response, reverse('master_roster_portfolio', args=[9]))
        self.assertEqual(get_user_model().objects.count(), 0)
        response = self.client.get(reverse('master_roster_portfolio', args=[9]))
        self.assertContains(response, 'Mestre Keter')
        self.assertNotContains(response, 'Perfil de None')
        self.assertEqual(response.context['master_user'], None)

    def test_private_application_answers_do_not_leak_into_roster(self):
        user = get_user_model().objects.create_user('hidden-master')
        archive = TbImportacaoMestre.objects.create(fonte='private-test', checksum='d'*64, dados={})
        TbMestreLegado.objects.create(importacao=archive, numero=8, nome='Mestre Teste', rotulo_original='F08', user=user)
        TbPerfilMestre.objects.create(user=user, status_mestre='aprovado', listado=False,
                                     apresentacao='PRIVATE-PORTFOLIO', candidatura_json={'answers': {'origem':'PRIVATE-ANSWER'}})
        for url in (reverse('masters_directory'), reverse('master_roster_portfolio', args=[8])):
            response = self.client.get(url)
            self.assertNotContains(response, 'PRIVATE-PORTFOLIO')
            self.assertNotContains(response, 'PRIVATE-ANSWER')

    def test_bot_progression_thresholds_and_unknown_legacy_are_not_guessed(self):
        from datetime import datetime, timedelta, timezone
        start = datetime(2026,1,1,tzinfo=timezone.utc)
        for minutes, expected in [(149,0),(150,1),(300,2),(750,4),(900,6),(1200,8),(1800,12)]:
            quest = SimpleNamespace(status='finished', type='normal', rewardAventurasOverride=None,
                timeEvents=[{'eventType':'run','date':start.isoformat()}, {'eventType':'finish','date':(start+timedelta(minutes=minutes)).isoformat()}])
            self.assertEqual(adventure_amount(quest), expected)
        quest.type = 'legacy'
        quest.rewardAventurasOverride = 0
        self.assertIsNone(adventure_amount(quest))
        self.assertEqual(adventure_amount(quest, SimpleNamespace(decision='settled', adventures=2)), 2)

    def test_mission_history_deduplicates_approved_republications(self):
        from datetime import datetime, timezone
        admin = get_user_model().objects.create_user('reviewer')
        archive = TbImportacaoMestre.objects.create(fonte='history-test', checksum='f'*64, dados={})
        identity = TbMestreLegado.objects.create(importacao=archive, numero=9, nome='Mestre Keter', rotulo_original='F09', discord_id='123456789012345678')
        for key, kind, amount in [('main','normal',2), ('republication','normal',0), ('old','legacy',0)]:
            quest = BotQuest.objects.create(id=key, guildId='community', name=key, description='',
                questDate=datetime(2026,1,1,tzinfo=timezone.utc), playersAmount=0, rules='',
                type=kind, tableUrl='', questMaster=identity.discord_id, createdBy=identity.discord_id,
                status='finished', rewardAventurasOverride=amount,
                createdAt=datetime.now(timezone.utc), updatedAt=datetime.now(timezone.utc))
            if key != 'republication':
                TbRegistroMestreLegado.objects.create(mestre=identity, chave=key, tipo='adventure', titulo=key,
                    valor_mm=100, original={}, bot_quest_id=key)
        TbRevisaoMissaoBot.objects.create(quest_id='republication', guild_id='community', decision='duplicate',
                                        canonical_id='main', reviewed_by=admin)
        rows, unavailable = mission_history(identity)
        self.assertFalse(unavailable)
        self.assertEqual(len(rows), 2)
        self.assertEqual(next(r for r in rows if r['title']=='main')['adventures'], 2)
        self.assertIsNone(next(r for r in rows if r['title']=='old')['adventures'])

    def test_numbered_portfolio_does_not_impersonate_its_owner_in_navigation(self):
        viewer = get_user_model().objects.create_user('viewer')
        owner = get_user_model().objects.create_user('master-owner')
        archive = TbImportacaoMestre.objects.create(fonte='viewer-test', checksum='e'*64, dados={})
        TbMestreLegado.objects.create(importacao=archive, numero=41, nome='Mestre Gaz', rotulo_original='F41', user=owner)
        self.client.force_login(viewer)
        response = self.client.get(reverse('master_roster_portfolio', args=[41]))
        self.assertEqual(response.context['user'].pk, viewer.pk)
        self.assertEqual(response.context['master_user'].pk, owner.pk)

    def test_directory_pagination_and_global_navigation_are_discoverable(self):
        archive = TbImportacaoMestre.objects.create(fonte='pages-test', checksum='b'*64, dados={})
        for number in range(1, 27):
            TbMestreLegado.objects.create(importacao=archive, numero=number,
                                         nome=f'Mestre {number}', rotulo_original=f'F{number}')
        response = self.client.get(reverse('masters_directory'))
        self.assertContains(response, 'Página 1 de 2')
        self.assertContains(response, 'rel="next"')
        self.assertContains(response, 'aria-disabled="true"')
        self.assertContains(response, 'pagina=2#master-results')
        self.assertContains(response, 'Vitrine de mestres', count=3)
        response = self.client.get(reverse('masters_directory'), {'pagina': 2})
        self.assertContains(response, 'rel="prev"')
        self.assertEqual(len(response.context['masters']), 2)

    def test_history_uses_unique_original_instead_of_imported_placeholder(self):
        from datetime import date, datetime, timezone
        archive = TbImportacaoMestre.objects.create(fonte='original-test', checksum='9'*64, dados={})
        identity = TbMestreLegado.objects.create(importacao=archive, numero=17,
            nome='Mestre Teste', rotulo_original='F17', discord_id='123456789012345678')
        for key, kind, amount, day in [('placeholder','legacy',0,1), ('original','normal',3,1),
                                       ('another-date','normal',1,2)]:
            BotQuest.objects.create(id=key, guildId='community', name='Same title', description='',
                questDate=datetime(2026,1,day,12,tzinfo=timezone.utc), playersAmount=0, rules='',
                type=kind, tableUrl='', questMaster=identity.discord_id, createdBy=identity.discord_id,
                status='finished', rewardAventurasOverride=amount,
                createdAt=datetime.now(timezone.utc), updatedAt=datetime.now(timezone.utc))
        TbRegistroMestreLegado.objects.create(mestre=identity, chave='old', tipo='adventure',
            titulo='Same title', data=date(2026,1,1), valor_mm=100, original={}, bot_quest_id='placeholder')
        TbRegistroMestreLegado.objects.create(mestre=identity, chave='original', tipo='adventure',
            titulo='Same title', data=date(2026,1,1), valor_mm=100, original={}, bot_quest_id='original')
        rows, unavailable = mission_history(identity)
        self.assertFalse(unavailable)
        self.assertEqual(len(rows), 2)
        self.assertEqual(sorted(r['adventures'] for r in rows), [1,3])
        self.assertTrue(all(r['status'] == 'Concluída' for r in rows))

    def test_different_reporting_date_merges_only_this_masters_original(self):
        from datetime import date, datetime, timezone
        archive = TbImportacaoMestre.objects.create(fonte='report-date-test', checksum='8'*64, dados={})
        identity = TbMestreLegado.objects.create(importacao=archive, numero=17,
            nome='Mestre Teste', rotulo_original='F17', discord_id='123456789012345678')
        for key, kind, owner in [('placeholder','legacy',identity.discord_id),
                                 ('original','normal',identity.discord_id),
                                 ('other-master','normal','223456789012345678')]:
            BotQuest.objects.create(id=key, guildId='community', name='Uma jornada', description='',
                questDate=datetime(2026,1,1,12,tzinfo=timezone.utc), playersAmount=0, rules='',
                type=kind, tableUrl='', questMaster=owner, createdBy=owner,
                status='finished', rewardAventurasOverride=2 if kind=='normal' else 0,
                createdAt=datetime.now(timezone.utc), updatedAt=datetime.now(timezone.utc))
        TbRegistroMestreLegado.objects.create(mestre=identity, chave='report', tipo='adventure',
            titulo='Uma jornada!', data=date(2026,1,3), valor_mm=100, original={}, bot_quest_id='placeholder')
        rows, unavailable = mission_history(identity)
        self.assertFalse(unavailable)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['adventures'], 2)
        self.assertEqual(rows[0]['date'], date(2026,1,1))
        self.assertEqual(rows[0]['status'], 'Concluída')


@unittest.skipUnless(ISOLATED, 'Requires isolated SQLite memory schema')
class EmailCleanupMigrationTests(unittest.TestCase):
    def test_postgres_checks_deferred_constraints_before_creating_index(self):
        User = get_user_model()
        User.objects.create_user('pg-keeper', email='one@example.test')
        User.objects.create_user('pg-empty', email='ONE@example.test')
        statements = []
        with connection.schema_editor() as editor:
            def execute(sql):
                statements.append(sql)
                if sql != 'SET CONSTRAINTS ALL IMMEDIATE':
                    editor.execute(sql)
            proxy = SimpleNamespace(
                connection=SimpleNamespace(alias=connection.alias, vendor='postgresql',
                                           introspection=connection.introspection),
                quote_name=editor.quote_name, execute=execute)
            with patch('home.master_legacy_api._backup') as backup:
                cleanup_and_index(apps, proxy)
            backup.assert_called_once()
        self.assertEqual(statements[0], 'SET CONSTRAINTS ALL IMMEDIATE')
        self.assertTrue(statements[1].startswith('CREATE UNIQUE INDEX '))
        self.assertEqual(User.objects.count(), 1)
        self.assertEqual(UserAccountMergeReceipt.objects.count(), 1)

    def tearDown(self):
        if not ISOLATED:
            return
        with connection.cursor() as cursor:
            cursor.execute('DROP INDEX IF EXISTS auth_user_email_normalized_unique')
        from django.core.management import call_command
        call_command('flush', verbosity=0, interactive=False, inhibit_post_migrate=True)

    def test_empty_duplicate_is_removed_without_changing_owned_records(self):
        User = get_user_model()
        keeper = User.objects.create_user('keeper', email='One@Example.test')
        duplicate = User.objects.create_user('empty', email=' one@example.test ')
        owned = TbAventuraMestre.objects.create(mestre=keeper, nome='Existing record', recompensa_mm=0)
        UserProfile.objects.filter(user=duplicate).update(email_verified=True)
        with connection.schema_editor() as editor:
            cleanup_and_index(apps, editor)
        owned.refresh_from_db()
        self.assertEqual(owned.mestre_id, keeper.pk)
        self.assertFalse(User.objects.filter(pk=duplicate.pk).exists())
        self.assertTrue(UserProfile.objects.get(user=keeper).email_verified)
        self.assertEqual(UserAccountMergeReceipt.objects.get().removed_user_id, duplicate.pk)
        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.create_user('race', email=' ONE@example.test ')
        User.objects.create_user('legacy-empty-one', email='')
        User.objects.create_user('legacy-empty-two', email='')

    def test_two_populated_accounts_are_not_merged_or_deleted(self):
        User = get_user_model()
        first = User.objects.create_user('first', email='same@example.test')
        second = User.objects.create_user('second', email='SAME@example.test')
        TbAventuraMestre.objects.create(mestre=first, nome='First data', recompensa_mm=0)
        TbAventuraMestre.objects.create(mestre=second, nome='Second data', recompensa_mm=0)
        with self.assertRaises(RuntimeError), connection.schema_editor() as editor:
            cleanup_and_index(apps, editor)
        self.assertEqual(User.objects.count(), 2)
        self.assertFalse(UserAccountMergeReceipt.objects.exists())

    @unittest.skipUnless('--production-backup' in sys.argv, 'Opt-in read-only production fixture simulation')
    def test_production_snapshot_cleanup_is_only_empty_accounts(self):
        import os
        fixture = Path(os.environ['LOCALAPPDATA']) / 'BonfireQA/account-checkout-audit-20261105/pre-account-cleanup.json'
        rows = json.loads(fixture.read_text(encoding='utf-8'))
        User = get_user_model()
        users = {}
        for row in rows:
            if row['model'] == 'auth.user':
                fields = row['fields']
                user = User.objects.create(pk=row['pk'], username=fields['username'], email=fields['email'],
                    password='!', is_active=fields['is_active'], is_staff=fields['is_staff'],
                    is_superuser=fields['is_superuser'], last_login=fields['last_login'], date_joined=fields['date_joined'])
                users[user.username] = user
        for row in rows:
            if row['model'] == 'home.userprofile':
                fields = dict(row['fields'])
                owner = users[fields.pop('user')[0]]
                UserProfile.objects.update_or_create(user=owner, defaults=fields)
            elif row['model'] != 'auth.user':
                owners = {v[0] for v in row['fields'].values() if isinstance(v, list) and len(v) == 1 and isinstance(v[0], str) and v[0] in users}
                for owner in owners:
                    TbAventuraMestre.objects.create(mestre=users[owner], nome='Fixture ownership evidence', recompensa_mm=0)
        owned_before = list(TbAventuraMestre.objects.values_list('pk', 'mestre_id'))
        with connection.schema_editor() as editor:
            cleanup_and_index(apps, editor)
        self.assertEqual(User.objects.count(), 87)
        self.assertEqual(UserAccountMergeReceipt.objects.count(), 14)
        self.assertEqual(list(TbAventuraMestre.objects.values_list('pk', 'mestre_id')), owned_before)
        self.assertTrue(User.objects.filter(username='Bia_cookie').exists())
        self.assertTrue(User.objects.filter(username='MiguelBC').exists())
        self.assertTrue(User.objects.filter(username='oSaik').exists())
        self.assertTrue(User.objects.filter(username='Spadez').exists())
        manifest = list(UserAccountMergeReceipt.objects.values('keeper__username', 'removed_user_id', 'removed_username'))
        destination = fixture.parent / 'cleanup-simulation.json'
        destination.write_text(json.dumps({'remaining':87, 'removed':14, 'ownership_preserved':True, 'manifest':manifest}, ensure_ascii=False, indent=2), encoding='utf-8')


if ISOLATED:
    if connection.settings_dict['NAME'] != ':memory:':
        raise RuntimeError('Only SQLite memory is allowed')
    from django.test.utils import setup_test_environment
    setup_test_environment()
    from home import views, db_access_api  # Register their managed models before schema creation.
    if '--migration-check' in sys.argv:
        from django.core.management import call_command
        call_command('makemigrations', 'home', check=True, dry_run=True, verbosity=1)
    models = [m for m in apps.get_models() if m._meta.managed and not m._meta.proxy]
    with connection.schema_editor() as editor:
        for model in models + [BotQuest, BotMember, BotTransaction, BotDedicatedRank]:
            editor.create_model(model)
    if '--preview' in sys.argv:
        from wsgiref.simple_server import make_server
        from django.core.wsgi import get_wsgi_application
        from django.contrib.staticfiles.handlers import StaticFilesHandler
        from django.conf import settings
        from home.master_legacy import import_archive, bind_master
        settings.MASTER_APPLICATIONS_OPEN = True  # Preview process only; production stays closed.
        user = get_user_model().objects.create_superuser('preview-admin', 'preview@example.test', 'preview-local-only')
        root = Path(__file__).resolve().parents[1]
        for name in ('mercado-mestres-20261104', 'mercado-mestres-20261105-roster-addendum'):
            plan = json.loads((root / 'home/content_packages/master_legacy' / (name + '.json')).read_text(encoding='utf-8'))
            import_archive(plan, name)
        bind_master(TbMestreLegado.objects.get(numero=41).pk, user.pk, actor=user, wallet_mode='defer')
        server = make_server('127.0.0.1', 8776, StaticFilesHandler(get_wsgi_application()))
        print('ISOLATED_PREVIEW http://127.0.0.1:8776', flush=True)
        server.serve_forever()
        sys.exit(0)
    suite = unittest.TestSuite()
    suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(MaintenanceBatchTests))
    from home.test_asaas import AsaasPaymentMappingTests, AsaasCheckoutTests, AsaasDiscordCheckoutTests, AsaasWebhookIdentityTests
    suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(AsaasPaymentMappingTests))
    suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(AsaasCheckoutTests))
    suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(AsaasDiscordCheckoutTests))
    suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(AsaasWebhookIdentityTests))
    suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(EmailCleanupMigrationTests))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
