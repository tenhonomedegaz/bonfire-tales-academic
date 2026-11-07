"""Regressões de origem e contagem do laboratório contra o conteúdo real."""
import json
from unittest.mock import patch

from django.urls import reverse

from home.models import (TbClassPublication, TbClasse, TbClassehabilidade, TbMagia,
                         TbPersonagem, TbPersonagemClasse, TbPersonagemMagia)
from home.pathbuilder_spells import apply_spell_selection, spell_sources
from home.test_criador import _CriadorBase


class PathbuilderSpellTests(_CriadorBase):
    def setUp(self):
        self.user = self._novo_usuario('spell-lab')
        self.client.force_login(self.user)

    def preview(self, base, classes=None, spells=None):
        build = {'modo': 'regras', 'classes': classes or [{'slug': base['classe'], 'nivel': 1}],
                 'magias': spells or []}
        before = TbPersonagem.objects.count()
        response = self.client.post(reverse('pathbuilder_preview'),
            data=json.dumps({'base': base, 'build': build}), content_type='application/json')
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(TbPersonagem.objects.count(), before)
        return response.json()['build']

    def test_preparation_override_of_base_counts_once_and_is_reversible(self):
        base = self._payload('mago')
        initial = self.preview(base)
        source = initial['magias_fontes'][0]
        prepared = [m for m in source['magias'] if m['nivel'] > 0 and m['preparada']]
        self.assertTrue(prepared)
        override = {'slug': prepared[0]['slug'], 'classe': 'mago', 'preparada': False}
        changed = self.preview(base, spells=[override])['magias_fontes'][0]
        self.assertEqual(changed['preparadas'], source['preparadas'] - 1)
        self.assertEqual(changed['conhecidas'], source['conhecidas'])
        self.assertEqual(self.preview(base)['magias_fontes'][0]['preparadas'], source['preparadas'])

    def test_published_spell_access_ignores_unpublished_live_spell_edit(self):
        from home.class_revision_editor import create_class_revision
        from home.test_creator_pinned_catalog import CreatorPinnedCatalogTests
        from home.views import _criador_persistir, _criador_public_resolution

        base = self._payload('mago')
        classe = TbClasse.objects.get(slug='mago')
        feature = TbClassehabilidade.objects.filter(id_classe=classe).first()
        self.assertIsNotNone(feature)
        initial = CreatorPinnedCatalogTests.seal(self, classe)
        published = create_class_revision(initial.checksum, classe.pk, [
            {'model': 'home.tbclassehabilidade', 'action': 'update',
             'pk': feature.pk, 'fields': {'descricao': '## Revisao publicada do Mago'}}
        ], presentation_source='catalog')
        TbClassPublication.objects.create(id_classe=classe, ruleset=published)
        resolved, errors = _criador_public_resolution(base)
        self.assertEqual(errors, [])
        character = _criador_persistir(self.user, base, resolved)
        allowed = spell_sources(character, ruleset=published)[0]['allowed']
        spell = TbMagia.objects.filter(pk__in=allowed, nivel=0).exclude(
            slug__in=base['truques']).first()
        self.assertIsNotNone(spell)

        TbMagia.objects.filter(pk=spell.pk).update(classes_slugs=[], classes='', nivel=9)
        self.assertNotIn(spell.pk, spell_sources(character)[0]['allowed'])
        self.assertIn(spell.pk, spell_sources(character, ruleset=published)[0]['allowed'])
        result = self.preview(base, spells=[{'slug': spell.slug, 'classe': 'mago'}])
        self.assertNotIn('fora da lista', ' '.join(result['validacao']['magias']))
        selected = [row for row in result['magias_fontes'][0]['magias']
                    if row['slug'] == spell.slug]
        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0]['nivel'], 0)

    def test_invalid_or_duplicated_spell_selection_preserves_preview(self):
        base = self._payload('mago')
        slug = base['truques'][0]
        valid = {'slug': slug, 'classe': 'mago', 'preparada': True}
        before = TbPersonagem.objects.count()
        for rows in (None, {}, [valid, valid],
                     [valid, {'slug': slug, 'preparada': False}],
                     [{'slug': slug, 'classe': 'mago', 'preparada': 1}],
                     [{'slug': slug, 'classe': 'mago', 'preparada': 'false'}]):
            with self.subTest(rows=rows):
                response = self.client.post(reverse('pathbuilder_preview'),
                    data=json.dumps({'base': base, 'build': {
                        'modo': 'regras', 'classes': [{'slug': 'mago', 'nivel': 1}],
                        'magias': rows}}), content_type='application/json')
                self.assertEqual(response.status_code, 400, response.content)
                self.assertEqual(TbPersonagem.objects.count(), before)
        corrected = self.preview(base, spells=[valid])
        self.assertEqual(corrected['magias_fontes'][0]['truques'],
                         self.preview(base)['magias_fontes'][0]['truques'])
        self.assertEqual(TbPersonagem.objects.count(), before)

    def test_prepared_limit_includes_base_and_manual_spells(self):
        base = self._payload('mago')
        spells = [{'slug': slug, 'classe': 'mago', 'preparada': True} for slug in base['magias']]
        result = self.preview(base, spells=spells)
        source = result['magias_fontes'][0]
        self.assertGreater(source['preparadas'], source['limite_magias'])
        self.assertIn('magias preparadas', ' '.join(result['validacao']['magias']))

    def test_cantrip_excess_and_grimoire_progression_are_specific(self):
        base = self._payload('mago')
        from home.views import _spell_catalog_queryset
        extra = _spell_catalog_queryset(['Mago']).filter(nivel=0).exclude(slug__in=base['truques']).first()
        self.assertIsNotNone(extra)
        result = self.preview(base, spells=[{'slug': extra.slug, 'classe': 'mago'}])
        self.assertIn('truques', ' '.join(result['validacao']['magias']))
        higher = self.preview(base, classes=[{'slug': 'mago', 'nivel': 2}])
        self.assertIn('grimório', ' '.join(higher['validacao']['magias']))

    def test_known_repertoire_limit_comes_from_class_contract(self):
        base = self._payload('bardo')
        from home.views import _spell_catalog_queryset
        extra = _spell_catalog_queryset(['Bardo']).filter(nivel=1).exclude(slug__in=base['magias']).first()
        self.assertIsNotNone(extra)
        initial = self.preview(base)
        self.assertEqual(initial['validacao']['magias'], [])
        result = self.preview(base, spells=[{'slug': extra.slug, 'classe': 'bardo'}])
        self.assertIn('magias conhecidas', ' '.join(result['validacao']['magias']))

    def test_invalid_source_and_pooled_slots_do_not_grant_access(self):
        base = self._payload('mago')
        spell = TbMagia.objects.filter(nivel=2).first()
        result = self.preview(base, classes=[{'slug': 'mago', 'nivel': 1}, {'slug': 'clerigo', 'nivel': 2}],
            spells=[{'slug': spell.slug, 'classe': 'mago'}])
        self.assertIn(spell.nome, ' '.join(result['validacao']['magias']))
        invalid = self.preview(base, spells=[{'slug': base['truques'][0], 'classe': 'bardo'}])
        self.assertIn('não é uma classe conjuradora', ' '.join(invalid['validacao']['magias']))

    def test_same_spell_has_independent_class_origins_and_preserves_innate_grant(self):
        from home.views import _criador_resolver, _criador_persistir
        base = self._payload('mago')
        resolved, errors = _criador_resolver(base)
        self.assertFalse(errors)
        character = _criador_persistir(self.user, base, resolved)
        TbPersonagemClasse.objects.create(id_personagem=character,
            id_classe=TbClasse.objects.get(slug='bardo'), nivel=1)
        sources = spell_sources(character)
        shared = sources[0]['allowed'] & sources[1]['allowed']
        spell = TbMagia.objects.filter(pk__in=shared, nivel=0).exclude(
            pk__in=character.magias.values_list('id_magia_id', flat=True)).first()
        self.assertIsNotNone(spell)
        innate = TbPersonagemMagia.objects.create(id_personagem=character, id_magia=spell,
            nome=spell.nome, nivel=0, origem='Concessão inata', sempre_preparada=True, preparada=True)
        apply_spell_selection(character, {'magias': [{'slug': spell.slug}]})
        self.assertIn('mais de uma fonte', ' '.join(character._pathbuilder_spell_issues))
        apply_spell_selection(character, {'magias': [
            {'slug': spell.slug, 'classe': 'mago', 'preparada': False},
            {'slug': spell.slug, 'classe': 'bardo', 'preparada': True}]})
        self.assertEqual(character.magias.filter(id_magia=spell, origem='Mago').count(), 1)
        self.assertEqual(character.magias.filter(id_magia=spell, origem='Bardo').count(), 1)
        self.assertFalse(character.magias.get(id_magia=spell, origem='Mago').preparada)
        self.assertTrue(character.magias.get(id_magia=spell, origem='Bardo').preparada)
        innate.refresh_from_db()
        self.assertTrue(innate.preparada)
        self.assertTrue(innate.sempre_preparada)

    def test_legacy_spell_resolves_unique_source_without_duplicate(self):
        base = self._payload('mago')
        result = self.preview(base, spells=[{'slug': base['truques'][0]}])
        self.assertEqual(result['validacao']['magias'], [])
        source = result['magias_fontes'][0]
        self.assertEqual(sum(m['slug'] == base['truques'][0] for m in source['magias']), 1)

    def test_unresolved_declared_limit_cannot_report_valid_spell_review(self):
        base = self._payload('mago')
        with patch('home.pathbuilder_spells.limit_at', return_value=None):
            result = self.preview(base)
        self.assertIn('limite de magia indisponível', ' '.join(result['validacao']['magias']))
        self.assertFalse(result['validacao']['valida'])
