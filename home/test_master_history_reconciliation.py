"""Bounded public mission history regressions; --isolated uses only memory SQLite."""
import sys
from pathlib import Path

ISOLATED = __name__ == '__main__' and '--isolated' in sys.argv
if ISOLATED:
    from django.conf import settings
    settings.configure(SECRET_KEY='isolated-master-history', USE_TZ=True,
        TIME_ZONE='America/Sao_Paulo', BASE_DIR=Path(__file__).resolve().parents[1],
        INSTALLED_APPS=['django.contrib.auth', 'django.contrib.contenttypes', 'home'],
        DATABASES={'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':memory:'}},
        DEFAULT_AUTO_FIELD='django.db.models.BigAutoField', ROOT_URLCONF=__name__,
        STATIC_URL='/static/', ALLOWED_HOSTS=['testserver'])
    import django
    django.setup()

import unittest
from datetime import date, datetime, timezone
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.core.paginator import Paginator
from django.db import connection, DatabaseError
from django.http import HttpResponse
from django.template import Context, Engine
from django.test import TestCase, RequestFactory
from django.test.utils import CaptureQueriesContext
from django.urls import path

from home.master_mission_archive import backfill_apply, backfill_plan, title_key
from home.master_roster import _discord_source, _history_matches, mission_history, portfolio
from home.models import (BotDedicatedRank, BotQuest, MestreOuroDireito, MestreOuroRevisao, TbAutorizacaoVitrine,
    TbAventuraMestre, TbImportacaoMestre, TbMestreLegado, TbPerfilMestre,
    TbRegistroMestreLegado, TbRevisaoMissaoBot, TbTransacaoMestre, UserProfile)

DID = '123456789012345678'
OTHER = '223456789012345678'
GUILD = '1167320030988468234'
SOURCE = f'https://discord.com/channels/{GUILD}/323456789012345678/423456789012345678'
urlpatterns = [path('masters/', lambda request: HttpResponse(), name='masters_directory')]


class MasterHistoryReconciliationTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create(username='history-reviewer', is_superuser=True)
        self.archive = TbImportacaoMestre.objects.create(fonte='history-test', checksum='a' * 64, dados={})
        self.master = TbMestreLegado.objects.create(importacao=self.archive, numero=9,
            nome='Mestre Teste', rotulo_original='F09', discord_id=DID)

    def quest(self, key, **changes):
        fields = dict(id=key, guildId=GUILD, name='The Silent Road: II', description='ADVERTISEMENT ONLY',
            questDate=datetime(2026, 1, 2, 18, tzinfo=timezone.utc), playersAmount=0, rules='',
            type='normal', tableUrl='', questMaster=DID, createdBy=DID, status='finished',
            rewardAventurasOverride=2, createdAt=datetime.now(timezone.utc), updatedAt=datetime.now(timezone.utc))
        fields.update(changes)
        return BotQuest.objects.create(**fields)

    def record(self, key, **changes):
        fields = dict(mestre=self.master, chave=key, tipo='adventure', titulo='Silent Road - II!',
            data=date(2026, 1, 20), valor_mm=100, original={})
        fields.update(changes)
        return TbRegistroMestreLegado.objects.create(**fields)

    def review(self, key, **changes):
        fields = dict(quest_id=key, guild_id=GUILD, master_discord_id=DID,
            legacy_master=self.master, decision='confirmed', adventures=2, reviewed_by=self.admin)
        fields.update(changes)
        return TbRevisaoMissaoBot.objects.create(**fields)

    def validated(self, key, amount):
        record = self.record(key, valor_mm=amount)
        plan = backfill_plan(self.archive.pk, self.archive.checksum, GUILD, [record.chave])
        backfill_apply(self.archive.pk, self.archive.checksum, GUILD, [record.chave],
                       plan['base_version'], actor=self.admin)
        record.refresh_from_db()
        return record, BotQuest.objects.get(pk=record.bot_quest_id)

    def history(self):
        rows, unavailable = mission_history(self.master)
        self.assertFalse(unavailable)
        return rows

    def render_history(self, rows, page_number=1, origin=''):
        page = Paginator(rows, 25).get_page(page_number)
        engine = Engine(dirs=[str(Path(__file__).resolve().parent / 'templates')],
            libraries={'static': 'django.templatetags.static'}, loaders=[
                ('django.template.loaders.locmem.Loader', {'home/pages/master_shell.html':
                    '{% block extra_head %}{% endblock %}{% block master_content %}{% endblock %}'}),
                'django.template.loaders.filesystem.Loader'])
        return engine.get_template('home/pages/master_roster_portfolio.html').render(Context({
            'identity': self.master, 'missions_page': page, 'mission_count': len(rows), 'history_origin': origin,
            'mission_page_numbers': page.paginator.get_elided_page_range(page.number, on_each_side=1, on_ends=1),
            'known_adventures': sum(r['adventures'] for r in rows if r['adventures'] is not None),
            'unknown_adventures': sum(r['adventures'] is None for r in rows)}))

    def test_no_record_and_duplicate_disappear_from_legacy_native_and_missing_sources(self):
        for decision in ('no_record', 'duplicate'):
            for source in ('native', 'legacy', 'missing'):
                with self.subTest(decision=decision, source=source):
                    key = f'{decision}-{source}'
                    if source != 'missing':
                        self.quest(key, type='legacy' if source == 'legacy' else 'normal')
                    self.record(key, bot_quest_id=key)
                    self.review(key, decision=decision, adventures=0)
        self.assertEqual(self.history(), [])

    def test_record_review_suppresses_unresolved_link_without_master_association(self):
        record = self.record('unresolved')
        self.review('deleted-bot-source', decision='no_record', adventures=None,
                    legacy_master=None, master_discord_id='', legacy_record=record)
        self.assertEqual(self.history(), [])

    def test_no_record_native_without_any_spreadsheet_row_is_hidden(self):
        self.quest('native-only')
        self.review('native-only', decision='no_record', adventures=None)
        self.assertEqual(self.history(), [])

    def test_record_review_does_not_resurface_linked_placeholder(self):
        quest = self.quest('old', type='legacy')
        record = self.record('source', bot_quest_id=quest.pk)
        self.review('missing', decision='no_record', adventures=0, legacy_record=record)
        self.assertEqual(self.history(), [])

    def test_any_exclusion_on_a_record_takes_precedence_over_conflicting_reviews(self):
        record = self.record('conflict')
        self.review('removed', decision='no_record', adventures=None, legacy_record=record)
        self.review('confirmed', adventures=2, legacy_record=record)
        self.assertEqual(self.history(), [])

    def test_reviewed_no_record_does_not_resurface_during_bot_outage(self):
        self.record('missing', bot_quest_id='missing')
        self.review('missing', decision='no_record', adventures=0)
        with patch.object(BotQuest.objects, 'filter', side_effect=DatabaseError('unavailable')):
            rows, unavailable = mission_history(self.master)
        self.assertTrue(unavailable)
        self.assertEqual(rows, [])

    def test_canonical_link_uses_explicit_session_not_title_alias(self):
        self.quest('original', name='Approved canonical session')
        self.quest('repost', name='Unrelated repost title')
        self.record('old', bot_quest_id='repost')
        self.review('repost', decision='duplicate', adventures=0, canonical_id='original')
        rows = self.history()
        self.assertEqual([r['title'] for r in rows], ['Approved canonical session'])

    def test_canonical_link_cannot_import_another_master_or_guild(self):
        for owner, guild in ((OTHER, GUILD), (DID, 'another-guild')):
            with self.subTest(owner=owner, guild=guild):
                target = self.quest(f'target-{guild}', questMaster=owner, guildId=guild)
                review = self.review(f'missing-{guild}', decision='duplicate', adventures=0, canonical_id=target.pk)
                self.assertEqual(self.history(), [])
                review.delete()
                target.delete()

    def test_the_alias_reconciles_punctuation_and_reporting_date_without_global_key_change(self):
        record, placeholder = self.validated('old', 100)
        native = self.quest('native', name='The Silent Road: II')
        self.assertNotEqual(title_key(record.titulo), title_key(native.name))
        rows = self.history()
        self.assertEqual(len(rows), 1)
        self.assertEqual((rows[0]['title'], rows[0]['adventures'], rows[0]['date']),
                         (native.name, 2, date(2026, 1, 2)))
        self.assertTrue(BotQuest.objects.filter(pk=placeholder.pk).exists())

    def test_chapter_roman_numbers_and_nonstandalone_the_stay_distinct(self):
        record = self.record('chapter', titulo='Silent Road II')
        chapter = self.quest('chapter-iv', name='The Silent Road IV')
        theatre = self.quest('theatre', name='Theatre II')
        self.assertEqual(_history_matches([record], {q.pk: q for q in (chapter, theatre)}, {}), {})
        record.titulo = 'Atre II'
        self.assertEqual(_history_matches([record], {theatre.pk: theatre}, {}), {})

    def test_two_native_sessions_remain_distinct_and_ambiguous_legacy_stays(self):
        self.record('old')
        self.quest('one')
        self.quest('two', questDate=datetime(2026, 1, 3, 18, tzinfo=timezone.utc))
        self.review('one', decision='identity', adventures=None)
        self.assertEqual(len(self.history()), 3)

    def test_reciprocal_same_day_matches_only_one_of_repeated_native_sessions(self):
        self.record('old', data=date(2026, 1, 2))
        self.quest('one')
        self.quest('two', questDate=datetime(2026, 1, 3, 18, tzinfo=timezone.utc))
        self.review('one', decision='identity', adventures=None)
        self.assertEqual(len(self.history()), 2)

    def test_two_legacy_sources_are_not_collapsed_into_one_native(self):
        self.record('first')
        self.record('second')
        self.quest('native')
        self.review('native', decision='identity', adventures=None)
        self.assertEqual(len(self.history()), 3)

    def test_title_matching_never_crosses_master_or_guild(self):
        record, placeholder = self.validated('old', 100)
        others = [self.quest('other-master', questMaster=OTHER), self.quest('other-guild', guildId='other')]
        matches = _history_matches([record], {q.pk: q for q in [placeholder, *others]}, {},
                                   names={DID}, guild_id=GUILD)
        self.assertEqual(matches, {})
        self.assertEqual(len(self.history()), 1)

    def test_positive_exact_hundreds_infer_only_validated_private_legacy(self):
        record, quest = self.validated('plain', 300)
        row = self.history()[0]
        self.assertEqual((row['adventures'], row['master_mm']), (3, 300))
        self.assertIn('Planilha validada', row['adventures_source'])
        quest.description = '{}'
        quest.save(update_fields=['description'])
        self.assertIsNone(self.history()[0]['adventures'])

    def test_matched_native_without_adventure_evidence_does_not_inherit_hundreds(self):
        self.validated('legacy', 300)
        self.quest('native', rewardAventurasOverride=None)
        rows = self.history()
        self.assertEqual(len(rows), 1)
        self.assertIsNone(rows[0]['adventures'])

    def test_zero_and_rank_bonus_amounts_remain_unknown(self):
        for amount in (0, 130, 550):
            with self.subTest(amount=amount):
                record, quest = self.validated(f'amount-{amount}', amount)
                self.assertIsNone(self.history()[0]['adventures'])
                quest.delete()
                record.delete()

    def test_whole_hundred_with_rank_or_boost_evidence_stays_unknown(self):
        record, quest = self.validated('rank', 400)
        quest.allowedRanks = '{"rank-role"}'
        quest.save(update_fields=['allowedRanks'])
        self.assertIsNone(self.history()[0]['adventures'])
        quest.allowedRanks = '{}'
        quest.save(update_fields=['allowedRanks'])
        self.review(quest.pk, decision='identity', adventures=None,
                    evidence={'reward_context': {'dedicated_bonus_mm': 100}})
        self.assertIsNone(self.history()[0]['adventures'])

    def test_unlinked_spreadsheet_and_arbitrary_legacy_never_infer(self):
        self.record('unlinked', valor_mm=300)
        self.assertIsNone(self.history()[0]['adventures'])
        quest = self.quest('arbitrary', type='legacy', rewardAventurasOverride=0)
        record = self.master.registros.get()
        record.bot_quest_id = quest.pk
        record.save(update_fields=['bot_quest_id'])
        self.assertIsNone(self.history()[0]['adventures'])

    def test_explicit_zero_and_quest_override_trump_inference(self):
        record, quest = self.validated('override', 300)
        quest.rewardAventurasOverride = 4
        quest.save(update_fields=['rewardAventurasOverride'])
        self.assertEqual(self.history()[0]['adventures'], 4)
        self.review(quest.pk, adventures=0, master_mm=0)
        row = self.history()[0]
        self.assertEqual((row['adventures'], row['master_mm']), (0, 0))
        rendered = self.render_history([row])
        self.assertIn('0 MM', rendered)
        self.assertNotIn('Não registrada', rendered)

    def test_explicit_four_adventures_and_550_mm_show_reward_provenance(self):
        self.quest('boost')
        self.review('boost', adventures=4, master_mm=550, evidence={'reward_context': {
            'base_adventures': 2, 'multiplier': 2, 'reason': 'Boost aprovado',
            'base_mm': 400, 'dedicated_bonus_mm': 150, 'final_mm': 550, 'source': 'Recibo revisado'}})
        row = self.history()[0]
        self.assertEqual((row['adventures'], row['master_mm']), (4, 550))
        rendered = self.render_history([row])
        for text in ('550 MM', '400 MM', '150 MM', 'Multiplicador: 2x', 'Base: 2',
                     'Boost aprovado', 'Recibo revisado', 'Revisão administrativa'):
            self.assertIn(text, rendered)

    def test_native_mm_are_never_used_to_infer_adventures(self):
        self.quest('native-one', name='First native session')
        self.quest('native-two', name='Second native session')
        self.quest('native-unknown', rewardAventurasOverride=None)
        self.review('native-one', adventures=1, master_mm=200)
        self.review('native-two', adventures=2, master_mm=300)
        self.review('native-unknown', decision='identity', adventures=None, master_mm=400)
        rows = {r['title']: r for r in self.history()}
        self.assertEqual(rows['First native session']['adventures'], 1)
        self.assertEqual(rows['Second native session']['adventures'], 2)
        self.assertIsNone(rows['The Silent Road: II']['adventures'])

    def test_history_pagination_first_last_numbered_pages_and_anchor(self):
        self.quest('session')
        self.review('session', decision='identity', adventures=None)
        row = self.history()[0]
        rows = [dict(row, title=f'Session {index}') for index in range(51)]
        first = self.render_history(rows)
        self.assertIn('Mostrando 1-25 de 51 missões', first)
        self.assertIn('aria-disabled="true"', first)
        self.assertNotIn('rel="prev"', first)
        self.assertIn('rel="next" href="?pagina=2#historico-missoes"', first)
        self.assertIn('aria-current="page" aria-label="Página 1"', first)
        self.assertIn('href="?pagina=3#historico-missoes" aria-label="Página 3"', first)
        self.assertIn('id="historico-missoes"', first)
        self.assertGreater(first.index('class="mr-pagination"'), first.index('</table>'))
        last = self.render_history(rows, 3)
        self.assertIn('Mostrando 51-51 de 51 missões', last)
        self.assertNotIn('rel="next"', last)
        self.assertIn('rel="prev" href="?pagina=2#historico-missoes"', last)
        self.assertIn('aria-current="page" aria-label="Página 3"', last)

    def test_many_pages_elide_and_portfolio_uses_current_page(self):
        self.quest('session')
        self.review('session', decision='identity', adventures=None)
        row = self.history()[0]
        rows = [dict(row, title=f'Session {index}') for index in range(780)]
        with patch('home.master_roster.mission_history', return_value=(rows, False)), \
                patch('home.master_roster.render', side_effect=lambda request, template, data: data):
            context = portfolio(RequestFactory().get('/masters/9/', {'pagina': 16}), 9)
        numbers = list(context['mission_page_numbers'])
        self.assertEqual([n for n in numbers if isinstance(n, int)], [1, 15, 16, 17, 32])
        self.assertEqual(context['missions_page'].number, 16)
        rendered = self.render_history(rows, 16)
        self.assertIn('Mostrando 376-400 de 780 missões', rendered)
        self.assertIn('class="mr-page-ellipsis"', rendered)
        self.assertIn('aria-current="page" aria-label="Página 16"', rendered)
        self.assertNotIn('aria-label="Página 2"', rendered)

    def test_approved_summary_is_escaped_and_participants_never_use_private_bot_data(self):
        self.quest('summary', questPlayers=[{'discordID': DID, 'characterID': 'private-character-key'}])
        self.review('summary', evidence={'mission_details': {
            'summary': '<script>alert("summary")</script>\nSession actually played.',
            'participants': ['Ana <img src=x onerror=alert(1)>', DID, f'<@{OTHER}>',
                             {'name': 'Object', 'characterID': 'private-character-key'},
                             'clabcdefghijk0123456789012', '123e4567-e89b-12d3-a456-426614174000', 'Bia'],
            'source_url': SOURCE}, 'reward_context': {'reason': '<b>approved</b>', 'source': '<img src=x>'}})
        with CaptureQueriesContext(connection) as queries:
            rows = self.history()
        self.assertFalse(any('questPlayers' in q['sql'] for q in queries))
        rendered = self.render_history(rows)
        self.assertIn('&lt;script&gt;', rendered)
        self.assertIn('&lt;img src=x onerror=alert(1)&gt;', rendered)
        self.assertIn('&lt;b&gt;approved&lt;/b&gt;', rendered)
        self.assertIn(f'href="{SOURCE}"', rendered)
        for text in ('<script>', '<img ', 'private-character-key', 'ADVERTISEMENT ONLY', f'>{DID}<', OTHER,
                     'clabcdefghijk0123456789012', '123e4567-e89b-12d3-a456-426614174000'):
            self.assertNotIn(text, rendered)
        self.assertEqual(len(rows[0]['details']['participants']), 2)

    def test_advertisement_is_not_a_summary_and_invalid_details_are_ignored(self):
        self.quest('advertisement')
        review = self.review('advertisement', evidence={'mission_details': 'not a dictionary',
            'reward_context': {'multiplier': True, 'final_mm': '550', 'source': {'secret': 'private'}}})
        row = self.history()[0]
        self.assertFalse(row['has_details'])
        self.assertIsNone(row['master_mm'])
        self.assertNotIn('multiplier', row['reward_context'])
        review.evidence = []
        review.save(update_fields=['evidence'])
        self.assertFalse(self.history()[0]['has_details'])

    def test_only_https_discord_message_sources_are_linked(self):
        self.assertEqual(_discord_source(SOURCE), SOURCE)
        for url in ('javascript:alert(1)', SOURCE.replace('https:', 'http:'),
                    SOURCE.replace('discord.com', 'discord.com.evil.test'),
                    SOURCE.replace('discord.com', 'user@discord.com'), SOURCE + '" onclick="alert(1)',
                    SOURCE.replace('/channels/', '/not-channels/'), SOURCE.replace('discord.com', 'discord.com:bad')):
            with self.subTest(url=url):
                self.assertEqual(_discord_source(url), '')

    def test_spreadsheet_placeholder_remains_manual_and_native_match_is_systemic(self):
        self.validated('manual', 200)
        self.quest('native', name='Session in both sources')
        self.record('matched', titulo='Session in both sources')
        self.review('native')
        rows = {row['title']: row for row in self.history()}
        manual = rows['Silent Road - II!']
        self.assertEqual(manual['entry_origin'], 'manual')
        self.assertTrue(manual['has_spreadsheet_source'])
        native = rows['Session in both sources']
        self.assertEqual(native['entry_origin'], 'system')
        self.assertTrue(native['has_spreadsheet_source'])
        self.assertEqual(len(rows), 2)
        rendered = self.render_history(list(rows.values()))
        self.assertIn('Manual · planilha', rendered)
        self.assertIn('Sistêmica · bot', rendered)
        self.assertIn('Também consta na planilha', rendered)

    def test_origin_filter_is_kept_in_pagination_and_does_not_reclassify_records(self):
        self.quest('native')
        self.review('native')
        row = self.history()[0]
        rows = [dict(row, title=f'Native {i}') for i in range(26)]
        rows.append(dict(row, entry_origin='manual', title='Spreadsheet'))
        with patch('home.master_roster.mission_history', return_value=(rows, False)), \
                patch('home.master_roster.render', side_effect=lambda request, template, data: data):
            context = portfolio(RequestFactory().get('/masters/9/', {'origem': 'system'}), 9)
        self.assertEqual(context['mission_count'], 26)
        rendered = self.render_history(rows[:26], origin=context['history_origin'])
        self.assertIn('href="?origem=system&amp;pagina=2#historico-missoes"', rendered)

    def test_activity_reads_bot_without_individual_verification_and_counts_sessions_not_rewards(self):
        from home.master_commercial import commercial_eligibility
        self.master.user = self.admin
        self.master.save(update_fields=['user'])
        TbPerfilMestre.objects.create(user=self.admin, status_mestre='aprovado')
        record, _ = self.validated('manual', 200)
        self.quest('open', name='Open session', isPublished=True, channelId='323456789012345678',
                   questDate=datetime(2025, 5, 1, tzinfo=timezone.utc),
                   endDate=datetime(2026, 1, 20, 18, tzinfo=timezone.utc), rewardAventurasOverride=4)
        self.quest('private', name='Private session', type='Privada', isPublished=True,
                   channelId='323456789012345679')
        self.record('same-open-session', titulo='Open session')
        self.quest('cancelled', name='Cancelled', status='cancelled')
        self.quest('test', name='Excluded')
        self.review('test', decision='no_record', adventures=0)
        today = date(2026, 1, 20)
        result = commercial_eligibility(self.admin, today=today)
        self.assertEqual((result['completed_tables'], result['open_tables']), (3, 1))
        self.assertEqual((result['system_tables'], result['manual_tables']), (2, 1))
        self.assertFalse(result['eligible'])  # Activity never replaces commercial authorization.
        TbAutorizacaoVitrine.objects.create(user=self.admin, autorizada=True, avaliado_por=self.admin)
        self.assertTrue(commercial_eligibility(self.admin, today=today)['eligible'])
        self.assertEqual(TbTransacaoMestre.objects.count(), 0)

    def test_bot_outage_does_not_unlock_commercial_listing(self):
        from home.master_commercial import commercial_eligibility
        self.master.user = self.admin
        self.master.save(update_fields=['user'])
        TbPerfilMestre.objects.create(user=self.admin, status_mestre='aprovado')
        TbAutorizacaoVitrine.objects.create(user=self.admin, autorizada=True, avaliado_por=self.admin)
        with patch('home.master_roster.mission_history', return_value=([], True)):
            result = commercial_eligibility(self.admin, today=date(2026, 1, 20))
        self.assertTrue(result['activity_unavailable'])
        self.assertFalse(result['eligible'])

    def test_old_verification_endpoint_is_retired_without_writes(self):
        from home.master_commercial import verify_table
        request = RequestFactory().post('/old-verification/1/', {'acao': 'validar', 'confirmar': 'sim'})
        request.user = self.admin
        with CaptureQueriesContext(connection) as queries:
            response = verify_table(request, 1)
        self.assertEqual(response.status_code, 410)
        self.assertFalse(any(q['sql'].lstrip().upper().startswith(('INSERT', 'UPDATE', 'DELETE')) for q in queries))


if ISOLATED:
    if connection.vendor != 'sqlite' or connection.settings_dict['NAME'] != ':memory:' or 'bonfire.settings' in sys.modules:
        raise RuntimeError('Only isolated memory SQLite allowed')
    with connection.schema_editor() as editor:
        for model in (ContentType, Permission, Group, get_user_model(), UserProfile,
                      TbPerfilMestre, TbAventuraMestre, TbTransacaoMestre, MestreOuroDireito,
                      MestreOuroRevisao, TbImportacaoMestre, TbMestreLegado,
                      TbRegistroMestreLegado, BotQuest, BotDedicatedRank, TbRevisaoMissaoBot, TbAutorizacaoVitrine):
            editor.create_model(model)
    unittest.main(argv=[sys.argv[0], *[arg for arg in sys.argv[1:] if arg != '--isolated']], verbosity=2)
