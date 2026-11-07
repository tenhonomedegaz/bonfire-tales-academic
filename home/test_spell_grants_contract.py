"""Contract and closed-list regressions; --isolated only uses in-memory SQLite."""
import sys
from pathlib import Path

ISOLATED = __name__ == '__main__' and '--isolated' in sys.argv
if ISOLATED:
    from django.conf import settings
    settings.configure(
        SECRET_KEY='isolated-spell-grants-contract', USE_TZ=True,
        INSTALLED_APPS=['django.contrib.auth', 'django.contrib.contenttypes', 'home'],
        DATABASES={'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':memory:'}},
        MIGRATION_MODULES={'home': None}, ROOT_URLCONF=__name__, MIDDLEWARE=[],
        BASE_DIR=Path(__file__).resolve().parents[1], STATIC_URL='/static/',
        DEFAULT_AUTO_FIELD='django.db.models.AutoField', SITE_POSTGRES_TABLES={},
        PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'],
        CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}},
    )
    import django
    django.setup()

from collections import defaultdict
from copy import deepcopy
from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import SimpleTestCase, TestCase
from django.test.utils import CaptureQueriesContext

from home.character_engine import _grants_de_tag, magias_concedidas
from home.content_versions import create_revision, seal_ruleset
from home.hunter_rework import catalog
from home.hunter_spells import granted_spells, uses_tag_spell_grants
from home.hunter_traveler import (
    FINAL_SPELLS, command, final_grants, final_options, grant_long_rest, panel,
)
from home.models import (
    TbClasse, TbClassehabilidade, TbMagia, TbOperacaoRecurso, TbPersonagem,
    TbPersonagemCacador, TbPersonagemClasse, TbPersonagemEscolha, TbSubclasse,
)
from home.subclass_spell_catalog import spell_grant_tag
from home.versioned_classes import EVALUATOR, VOCABULARY, VersionedClassCatalog, inventory_class

urlpatterns = []


class ExplicitSpellListTests(SimpleTestCase):
    spells = {'first-spell': 6, 'second-spell': 7, 'third-spell': 0, 'unrelated': 9}

    def read(self, body, *, total=20, level=18, casts=False):
        return _grants_de_tag('spell_selection:any{' + body + '}', {}, self.spells,
                              total, casts, class_scopes={}, class_level=level)

    def test_varied_levels_are_options_not_fixed_grants(self):
        fixed, choice, reserved = self.read(
            'list:[first_spell,second_spell,third_spell],qtd:2,always_prepared,extra,requires:lvl{18}')
        self.assertEqual((fixed, reserved), ([], []))
        self.assertEqual(choice['opcoes'], ['first-spell', 'second-spell', 'third-spell'])
        self.assertEqual(choice['qtd'], 2)
        self.assertNotIn('pool', choice)

    def test_duplicates_and_aliases_are_deduplicated_and_count_is_bounded(self):
        fixed, choice, _ = self.read('list:[first_spell,first-spell,second_spell],qtd:99')
        self.assertEqual(fixed, [])
        self.assertEqual(choice['opcoes'], ['first-spell', 'second-spell'])
        self.assertEqual(choice['qtd'], 2)
        self.assertEqual(self.read('list:[first_spell],qtd:1')[0], [])
        self.assertEqual(self.read('list:[first_spell],qtd:0'), ([], None, []))

    def test_invalid_or_missing_reference_never_opens_a_pool_even_for_casts(self):
        for declaration in (
            'list:[]', 'list:[missing]', 'list:[first_spell,missing]',
            'list:[first_spell,,second_spell]', 'list:[first_spell,]',
            'list:[first_spell|second_spell]', 'list:first_spell',
            'list:{first_spell}', 'list:[first_spell', 'list[first_spell]',
            'list:[first_spell],list:[second_spell]',
            'list:[first_spell],list:bad',
        ):
            with self.subTest(declaration=declaration):
                self.assertEqual(self.read(declaration + ',qtd:2', casts=True), ([], None, []))

    def test_unlock_and_progressive_count_use_source_class_level(self):
        body = 'list:[first_spell,second_spell,third_spell],qtd:2,requires:lvl{18}'
        self.assertEqual(self.read(body, level=17), ([], None, []))
        self.assertEqual(self.read(body, level=18)[1]['qtd'], 2)
        self.assertEqual(self.read(body, total=17, level=None), ([], None, []))
        self.assertEqual(self.read(body, total=18, level=None)[1]['qtd'], 2)
        counts = 'list:[first_spell,second_spell,third_spell],qtd:{classlvl=3:1,classlvl=18:1}'
        self.assertEqual(self.read(counts, level=2), ([], None, []))
        self.assertEqual(self.read(counts, level=3)[1]['qtd'], 1)
        self.assertEqual(self.read(counts, level=18)[1]['qtd'], 2)
        self.assertEqual(self.read('qtd:{classlvl=3:1,classlvl=18:1}', level=3)[1]['qtd'], 1)


class SpellGrantContractTests(TestCase):
    def setUp(self):
        self.data = catalog()
        self.cl = TbClasse.objects.create(nome='Pinned class', slug='cacador',
                                          tags_json=['subclass-choices:[3]'])
        self.other_class = TbClasse.objects.create(nome='Other class', slug='other-class')
        self.orders = {row['id']: TbSubclasse.objects.create(
            id_classe=self.cl, nome=row['name'], slug=row['id']) for row in self.data['orders']}
        self.owner = get_user_model().objects.create_user('contract-owner')
        self.person = TbPersonagem.objects.bulk_create([
            TbPersonagem(dono=self.owner, nome='Isolated fixture', nivel=20)])[0]
        self.pc = TbPersonagemClasse.objects.create(id_personagem=self.person, id_classe=self.cl,
            id_subclasse=self.orders['ordem-dos-viajantes-primordiais'], nivel=18, principal=True)
        self.other_pc = TbPersonagemClasse.objects.create(
            id_personagem=self.person, id_classe=self.other_class, nivel=2)
        identities = {g['english']: g['catalog_identity'] for g in self.data['spell_grants']
                      if g.get('catalog_identity')}
        self.spells = {}
        for index, english in enumerate(sorted({g['english'] for g in self.data['spell_grants']})):
            identity = identities.get(english, {})
            self.spells[english] = TbMagia.objects.create(nome='Frozen %s' % english,
                nome_ingles=english, slug=identity.get('slug', 'grant-%s' % index),
                nivel=identity.get('level', 1))
        for index, english in enumerate(FINAL_SPELLS):
            self.spells[english] = TbMagia.objects.create(nome='Final %s' % index,
                nome_ingles=english, slug='final-%s' % index, nivel=6 + index % 2)
        TbMagia.objects.create(nome='Unrelated', slug='unrelated', nivel=9)
        grouped = defaultdict(list)
        for grant in self.data['spell_grants']:
            grouped[(grant['order'], grant['source'])].append(grant)
        for (order, source), grants in grouped.items():
            TbClassehabilidade.objects.create(id_classe=self.cl,
                id_subclasse=self.orders[order] if order else None,
                nome=source, niveladquirido=min(g['level'] for g in grants),
                tags_json=[spell_grant_tag(self.spells[g['english']].slug, g['level']) for g in grants])
        self.final_slugs = [self.spells[name].slug for name in FINAL_SPELLS]
        self.final_feature = TbClassehabilidade.objects.create(id_classe=self.cl,
            id_subclasse=self.orders['ordem-dos-viajantes-primordiais'], nome='Shared varied choice',
            niveladquirido=18, tags_json=[
                'spell_selection:any{list:[' + ','.join(self.final_slugs) +
                '],qtd:2,always_prepared,extra,requires:lvl{18}}'])
        self.legacy = self.seal()
        self.tagged = self.seal(tagged=True)
        self.profile = TbPersonagemCacador.objects.create(personagem_classe=self.pc,
            ruleset=self.legacy, ability='int', traveler={
                'final_choices': self.final_slugs[:2], 'final_used': self.final_slugs[:1],
                'final_selection_open': True, 'runes': [{'id': 'saved', 'label': 'Saved rune'}]})

    def seal(self, *, tagged=False, data=None):
        from home.versioned_spells import snapshot_spells
        from home.versioned_options import snapshot_options
        from home.versioned_origins import snapshot_origins
        from home.versioned_items import snapshot_magic_items, snapshot_mundane_items
        from home.versioned_conditions import snapshot_conditions
        from home.versioned_library import snapshot_library
        from home.tag_engine.library import Library

        payload = inventory_class(self.cl.pk)
        if tagged:
            payload['contracts'] = {'spell_grants': 'tags-v1'}
        return seal_ruleset([
            create_revision('class-catalog:%s' % self.cl.pk, payload),
            create_revision('class-catalog:%s' % self.other_class.pk, inventory_class(self.other_class.pk)),
            create_revision('hunter-rework', self.data if data is None else data),
            snapshot_spells(), snapshot_options(), snapshot_origins(), snapshot_magic_items(),
            snapshot_mundane_items(), snapshot_conditions(), snapshot_library(raw=Library(prefer_db=False).raw),
        ], evaluator_version=EVALUATOR, vocabulary_version=VOCABULARY)

    def bind(self, ruleset):
        self.profile.ruleset = ruleset
        self.profile.save(update_fields=['ruleset'])
        self.pc.ruleset = ruleset
        self.pc.save(update_fields=['ruleset'])
        self.profile.refresh_from_db()

    def test_actual_83_grants_are_read_from_tags_without_legacy_or_final_fallback(self):
        self.assertEqual(len(self.data['spell_grants']), 83)
        self.bind(self.tagged)
        self.assertEqual(VersionedClassCatalog(self.tagged, self.cl.pk).contracts,
                         {'spell_grants': 'tags-v1'})
        # Mutable source edits must not change identities or levels in the pin.
        TbMagia.objects.update(nome='Edited live', nivel=9)
        TbClassehabilidade.objects.update(tags_json=[])
        from home.versioned_spells import spell_catalog
        frozen = spell_catalog(self.tagged)
        for spell in self.spells.values():
            self.assertEqual((frozen[spell.pk].slug, frozen[spell.pk].nivel), (spell.slug, spell.nivel))
        with patch('home.hunter_spells.grants_at', side_effect=AssertionError('legacy grants')), \
                patch('home.hunter_spells.preparation', side_effect=AssertionError('legacy preparation')), \
                patch('home.hunter_traveler.final_grants', side_effect=AssertionError('legacy final')):
            for order in self.orders:
                self.pc.id_subclasse = self.orders[order]
                for level in (1, 3, 5, 9, 13, 17, 18):
                    with self.subTest(order=order, level=level):
                        self.pc.nivel = level
                        self.pc.save(update_fields=['id_subclasse', 'nivel'])
                        self.other_pc.nivel = 20 - level
                        self.other_pc.save(update_fields=['nivel'])
                        expected = {self.spells[g['english']].slug: self.spells[g['english']].nivel
                            for g in self.data['spell_grants']
                            if g['level'] <= level and g['order'] in ('', order)}
                        actual = magias_concedidas(self.person, ruleset=self.tagged)
                        self.assertEqual({g['slug']: g['nivel'] for g in actual['concedidas']}, expected)
                        self.assertEqual(len(actual['concedidas']), len(expected))
                        self.assertEqual(granted_spells(self.person, self.tagged), [])

    def test_contract_is_per_snapshot_not_class_name_or_any_tag(self):
        self.assertFalse(uses_tag_spell_grants(self.profile))
        from home.class_revision_editor import create_class_revision, preview_class_revision

        arguments = (self.legacy.checksum, self.cl.pk, [])
        contracts = {'spell_grants': 'tags-v1'}
        preview = preview_class_revision(*arguments, contracts=contracts)
        created = create_class_revision(*arguments, contracts=contracts)
        self.assertEqual(preview['ruleset_checksum'], created.checksum)
        self.assertEqual(VersionedClassCatalog(created, self.cl.pk).contracts, contracts)
        self.assertEqual(VersionedClassCatalog(self.legacy, self.cl.pk).contracts, {})
        for invalid in ({'spell_grants': 'tags-v2'}, {'unknown': 'tags-v1'}):
            with self.subTest(contracts=invalid), CaptureQueriesContext(connection) as queries:
                for operation in (preview_class_revision, create_class_revision):
                    with self.assertRaises(ValueError):
                        operation(*arguments, contracts=invalid)
            self.assertFalse(any(q['sql'].lstrip().upper().startswith(
                ('INSERT', 'UPDATE', 'DELETE')) for q in queries))
        self.cl.slug = 'another-identity'
        self.cl.save(update_fields=['slug'])
        renamed = self.seal(tagged=True)
        self.bind(renamed)
        with patch('home.hunter_spells.grants_at', side_effect=AssertionError('legacy')):
            self.assertTrue(uses_tag_spell_grants(self.profile))
            self.assertEqual(granted_spells(self.person, renamed), [])

    def test_legacy_profile_keeps_static_grants_and_final_choices(self):
        self.assertEqual(VersionedClassCatalog(self.legacy, self.cl.pk).contracts, {})
        expected = {self.spells[g['english']].slug for g in self.data['spell_grants']
                    if g['order'] in ('', 'ordem-dos-viajantes-primordiais')}
        grants = granted_spells(self.person, self.legacy)
        self.assertEqual({g['slug'] for g in grants}, expected | set(self.final_slugs[:2]))
        self.assertEqual([g['slug'] for g in final_grants(self.profile)], self.final_slugs[:2])
        self.assertTrue(panel(self.profile)['final_selection_open'])

    def test_tagged_revision_does_not_need_legacy_spell_references(self):
        poisoned = deepcopy(self.data)
        poisoned['spell_grants'] = [{'english': 'Absent legacy reference', 'level': 1, 'order': ''}]
        self.bind(self.seal(tagged=True, data=poisoned))
        self.assertTrue(magias_concedidas(self.person, ruleset=self.profile.ruleset)['concedidas'])
        self.assertEqual(granted_spells(self.person, self.profile.ruleset), [])

    def test_missing_reference_in_legacy_revision_is_still_rejected(self):
        poisoned = deepcopy(self.data)
        poisoned['spell_grants'] = [{'english': 'Absent legacy reference', 'level': 1, 'order': ''}]
        pin = self.seal(data=poisoned)
        self.bind(pin)
        with self.assertRaisesMessage(ValueError, 'absent or ambiguous'):
            granted_spells(self.person, pin)

    def test_divergent_profile_ruleset_remains_an_error_for_both_contracts(self):
        for pin, wrong in ((self.tagged, self.legacy), (self.legacy, self.tagged)):
            with self.subTest(pin=pin.checksum):
                self.bind(pin)
                with self.assertRaisesMessage(ValueError, 'differ'):
                    granted_spells(self.person, wrong)
                self.pc.ruleset = wrong
                self.pc.save(update_fields=['ruleset'])
                self.profile.refresh_from_db()
                with self.assertRaisesMessage(ValueError, 'differ'):
                    granted_spells(self.person, pin)

    def test_common_choice_is_pending_then_grants_only_valid_selected_options(self):
        self.bind(self.tagged)
        initial = magias_concedidas(self.person, ruleset=self.tagged)
        pending = initial['pendentes']
        self.assertEqual(len(pending), 1)
        self.assertEqual((pending[0]['opcoes'], pending[0]['qtd']), (self.final_slugs, 2))
        self.assertFalse(set(self.final_slugs) & {g['slug'] for g in initial['concedidas']})
        choice = TbPersonagemEscolha.objects.create(id_personagem=self.person,
            origem=self.final_feature.nome, tipo='magia-concedida', slot=0,
            valor=','.join([self.final_slugs[0], self.final_slugs[0], 'unrelated']))
        result = magias_concedidas(self.person, ruleset=self.tagged)
        self.assertEqual(result['pendentes'][0]['escolhidos'], self.final_slugs[:1])
        choice.valor = ','.join(self.final_slugs[:3])
        choice.save(update_fields=['valor'])
        with CaptureQueriesContext(connection) as queries:
            result = magias_concedidas(self.person, ruleset=self.tagged)
        self.assertFalse(result['pendentes'])
        finals = [g for g in result['concedidas'] if g['fonte'] == self.final_feature.nome]
        self.assertEqual([(g['slug'], g['nivel']) for g in finals], [(s, 6 + i % 2) for i, s in enumerate(self.final_slugs[:2])])
        self.assertFalse(any(q['sql'].lstrip().upper().startswith(('INSERT', 'UPDATE', 'DELETE')) for q in queries))

    def test_common_selection_is_locked_by_source_class_not_multiclass_total(self):
        self.bind(self.tagged)
        self.pc.nivel = 17
        self.pc.save(update_fields=['nivel'])
        self.other_pc.nivel = 3
        self.other_pc.save(update_fields=['nivel'])
        self.assertFalse(magias_concedidas(self.person, ruleset=self.tagged)['pendentes'])
        self.pc.nivel = 18
        self.pc.save(update_fields=['nivel'])
        self.other_pc.nivel = 2
        self.other_pc.save(update_fields=['nivel'])
        self.assertEqual(len(magias_concedidas(self.person, ruleset=self.tagged)['pendentes']), 1)

    def test_tagged_legacy_panel_options_and_rest_are_disabled_without_state_loss(self):
        self.bind(self.tagged)
        before = deepcopy(self.profile.traveler)
        with patch('home.hunter_traveler.preparation', side_effect=AssertionError('legacy selection')):
            self.assertEqual(final_grants(self.profile), [])
            self.assertEqual(final_options(self.profile), [])
            grant_long_rest(self.person)
        state = panel(self.profile)
        for key in ('final_eligible', 'final_selection_open'):
            self.assertFalse(state[key])
        for key in ('final_choices', 'final_used', 'final_options'):
            self.assertEqual(state[key], [])
        self.assertEqual(state['runes'], before['runes'])
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.traveler, before)
        self.assertEqual(self.profile.version, 0)

    def event(self, action, **values):
        return command(character_id=self.person.pk, owner_id=self.owner.pk,
            operation_id=uuid4(), expected_version=self.profile.version,
            action=action, confirmed=True, **values)

    def test_tagged_legacy_selection_and_cast_reject_without_receipts_or_resource_changes(self):
        self.bind(self.tagged)
        before = deepcopy(self.profile.traveler)
        for action, values in (
            ('select_final', {'final_spells': self.final_slugs[2:4]}),
            ('cast_final', {'spell_slug': self.final_slugs[1]}),
        ):
            with self.subTest(action=action), self.assertRaisesMessage(ValueError, 'escolha comum'):
                self.event(action, **values)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.traveler, before)
        self.assertEqual(self.profile.version, 0)
        self.assertFalse(TbOperacaoRecurso.objects.filter(id_personagem=self.person).exists())
        self.assertFalse(self.person.recursos.exists())

    def test_legacy_selection_and_rest_still_work(self):
        grant_long_rest(self.person)
        self.profile.refresh_from_db()
        self.assertTrue(self.profile.traveler['final_selection_open'])
        result = self.event('select_final', final_spells=self.final_slugs[2:4])
        self.assertEqual(result['final_choices'], self.final_slugs[2:4])
        self.assertFalse(result['final_selection_open'])
        self.profile.refresh_from_db()
        self.assertEqual([g['slug'] for g in final_grants(self.profile)], self.final_slugs[2:4])

    def test_legacy_cast_spends_once_and_new_contract_rejects_replay(self):
        from home.hunter_preparation import preparation
        from home.hunter_resources import contract
        from home.resource_engine import ensure_resource

        resource = ensure_resource(self.person, contract(self.profile, preparation(self.profile)))
        before = resource.atual
        arguments = dict(character_id=self.person.pk, owner_id=self.owner.pk,
            operation_id=uuid4(), expected_version=self.profile.version,
            action='cast_final', confirmed=True, spell_slug=self.final_slugs[1])
        result = command(**arguments)
        self.assertEqual(command(**arguments), result)
        resource.refresh_from_db()
        self.assertEqual(resource.atual, before - 4)
        self.assertEqual(TbOperacaoRecurso.objects.filter(id_personagem=self.person).count(), 1)
        self.bind(self.tagged)
        with self.assertRaisesMessage(ValueError, 'escolha comum'):
            command(**arguments)
        resource.refresh_from_db()
        self.assertEqual(resource.atual, before - 4)
        self.assertEqual(TbOperacaoRecurso.objects.filter(id_personagem=self.person).count(), 1)


if ISOLATED:
    from django.test.runner import DiscoverRunner
    if connection.vendor != 'sqlite' or connection.settings_dict['NAME'] != ':memory:':
        raise RuntimeError('Only disposable in-memory SQLite is allowed.')
    labels = [argument for argument in sys.argv[1:] if argument != '--isolated']
    raise SystemExit(bool(DiscoverRunner(verbosity=1, interactive=False).run_tests(labels or [
        'home.test_spell_grants_contract', 'home.test_subclass_spell_catalog',
    ])))
