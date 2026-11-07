"""Whole-route measurements on synthetic data; run only with a disposable test DB."""

import json
import re
import statistics
from contextlib import nullcontext
from unittest.mock import patch
from collections import Counter
from importlib import import_module
from time import perf_counter
from types import SimpleNamespace

from django.apps import apps
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import connection
from django.test import Client, TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from .models import TbClasse, TbCosmetico, TbPersonagem, TbPersonagemClasse, TbUsuarioCosmetico, UserProfile


class ProfileRoutePerformanceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        editor = SimpleNamespace(connection=connection)
        import_module('home.migrations.0164_rank_cosmetic_rewards').seed_rank_rewards(apps, editor)
        import_module('home.migrations.0165_rank_themes').seed_rank_themes(apps, editor)
        for slug, kind, css in (('tema-bonfire', 'tema', 'theme-bonfire'),
                                 ('moldura-none', 'moldura', ''), ('efeito-none', 'efeito', '')):
            TbCosmetico.objects.get_or_create(slug=slug, defaults={
                'tipo': kind, 'nome': slug, 'css_class': css, 'origem': 'livre', 'escopo': 'ambos'})
        cls.owner = get_user_model().objects.create_user('profile-perf-synthetic', password='test-only')
        cls.other = get_user_model().objects.create_user('profile-perf-other', password='test-only')
        klass = TbClasse.objects.create(nome='Performance class', slug='performance-class')
        for index in range(6):
            character = TbPersonagem.objects.create(dono=cls.owner,
                nome=('PRIVATE-PERF-' if index % 2 else 'PUBLIC-PERF-') + str(index),
                publico=index % 2 == 0, nivel=20 if index == 5 else 1,
                aventuras=160 if index == 5 else 0)
            TbPersonagemClasse.objects.create(id_personagem=character, id_classe=klass,
                                              nivel=character.nivel, principal=True)
        for kind in ('tema', 'moldura', 'efeito'):
            for index in range(8):
                TbCosmetico.objects.create(slug=f'{kind}-perf-locked-{index}', nome=f'Locked {kind} {index}',
                    tipo=kind, origem='staff', escopo='ambos', descricao='Synthetic catalog entry. ' * 8)
        for kind in ('badge', 'titulo'):
            cosmetic = TbCosmetico.objects.create(slug=f'{kind}-perf-owned', nome=f'Owned {kind}',
                                                   tipo=kind, origem='staff')
            TbUsuarioCosmetico.objects.create(user=cls.owner, cosmetico=cosmetic, origem='staff')
        profile = UserProfile.objects.get(user=cls.owner)
        profile.profile_theme = 'rank-esmeralda'
        profile.avatar_frame = 'elo-esmeralda-aberta'
        profile.titulo_equipado = 'titulo-perf-owned'
        profile.badges_destaque = ['badge-perf-owned']
        profile.save()

    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)

    def test_measure_profile_routes(self):
        owner = Client()
        owner.force_login(self.owner)
        anonymous = Client()
        other = Client()
        other.force_login(self.other)
        public = reverse('public_profile', args=[self.owner.username])
        cases = (
            ('private_get', lambda: owner.get(reverse('profile'))),
            ('preview_post', lambda: owner.post(reverse('perfil_preview'), {
                'profile_theme': 'rank-esmeralda', 'avatar_frame': 'elo-esmeralda-aberta',
                'profile_effect': 'none', 'titulo_equipado': 'titulo-perf-owned',
                'badges_destaque': ['badge-perf-owned']})),
            ('public_anonymous_get', lambda: anonymous.get(public)),
            ('public_other_get', lambda: other.get(public)),
            ('public_owner_get', lambda: owner.get(public)),
        )
        report = {}
        for name, invoke in cases:
            cache.clear()
            samples = []
            for sample in range(4):
                with CaptureQueriesContext(connection) as captured:
                    start = perf_counter()
                    response = invoke()
                    elapsed = (perf_counter() - start) * 1000
                self.assertEqual(response.status_code, 200, response.content[:500])
                signatures = Counter(re.sub(r"'[^']*'|\b\d+\b", '?', query['sql']) for query in captured)
                tables = Counter(table for query in captured
                                 for table in re.findall(r'FROM\s+["`]?([\w]+)', query['sql'], re.I))
                samples.append({'ms': round(elapsed, 2), 'queries': len(captured),
                    'sql_ms': round(sum(float(query['time']) * 1000 for query in captured), 2),
                    'duplicate_queries': sum(count - 1 for count in signatures.values()),
                    'tables': tables.most_common(8), 'bytes': len(response.content)})
                if name in ('preview_post', 'public_anonymous_get', 'public_other_get'):
                    self.assertNotIn(b'PRIVATE-PERF-', response.content)
            report[name] = {'cold': samples[0], 'warm_median_ms': statistics.median(
                sample['ms'] for sample in samples[1:]), 'warm_queries': samples[-1]['queries'],
                'warm_duplicates': samples[-1]['duplicate_queries'], 'warm_tables': samples[-1]['tables'],
                'bytes': samples[-1]['bytes']}
        print('PROFILE_PERFORMANCE=' + json.dumps(report))

    def test_paired_before_after_read_scope(self):
        owner = Client()
        owner.force_login(self.owner)
        anonymous = Client()
        other = Client()
        other.force_login(self.other)
        public = reverse('public_profile', args=[self.owner.username])
        cases = {
            'private_get': lambda: owner.get(reverse('profile')),
            'preview_post': lambda: owner.post(reverse('perfil_preview'), {
                'profile_theme': 'rank-esmeralda', 'avatar_frame': 'elo-esmeralda-aberta',
                'profile_effect': 'none', 'titulo_equipado': 'titulo-perf-owned',
                'badges_destaque': ['badge-perf-owned']}),
            'public_anonymous_get': lambda: anonymous.get(public),
            'public_other_get': lambda: other.get(public),
            'public_owner_get': lambda: owner.get(public),
            'public_visible_cosmetics_get': lambda: anonymous.get(public),
        }
        report = {}
        for name, invoke in cases.items():
            if name == 'public_visible_cosmetics_get':
                # Publish only this synthetic source before timing, not inside the GET.
                TbPersonagem.objects.filter(dono=self.owner, nome='PRIVATE-PERF-5').update(
                    publico=True, nome='PUBLIC-PERF-5')
            invoke()  # Template compilation and cold catalog are outside the warm A/B.
            samples = {'before': [], 'after': []}
            for index in range(3):
                for mode in (('before', 'after') if index % 2 == 0 else ('after', 'before')):
                    control = patch('home.cosmetics.cosmetic_read_context', nullcontext) if mode == 'before' else nullcontext()
                    with control, CaptureQueriesContext(connection) as queries:
                        start = perf_counter()
                        response = invoke()
                        elapsed = (perf_counter() - start) * 1000
                    self.assertEqual(response.status_code, 200)
                    if name in ('preview_post', 'public_anonymous_get', 'public_other_get', 'public_visible_cosmetics_get'):
                        self.assertNotIn(b'PRIVATE-PERF-', response.content)
                    samples[mode].append((round(elapsed, 2), len(queries)))
            report[name] = {mode: {'median_ms': statistics.median(item[0] for item in data),
                'queries': [item[1] for item in data], 'ms': [item[0] for item in data]}
                for mode, data in samples.items()}
            if name in ('private_get', 'preview_post', 'public_owner_get', 'public_visible_cosmetics_get'):
                self.assertLess(samples['after'][0][1], samples['before'][0][1])
            else:
                self.assertLessEqual(samples['after'][0][1], samples['before'][0][1])
        print('PROFILE_PAIRED_AB=' + json.dumps(report))

    def test_public_owner_visitor_anonymous_inactive_and_unknown_keep_access_contract(self):
        from .cosmetics import _READ_CONTEXT
        cosmetic = TbCosmetico.objects.create(slug='tema-perf-independent', tipo='tema',
            nome='Independent owner theme', origem='staff', escopo='ambos',
            definicao_json={'accent': '#34d399', 'motif': 'leaves'})
        TbUsuarioCosmetico.objects.create(user=self.owner, cosmetico=cosmetic, origem='staff')
        UserProfile.objects.filter(user=self.owner).update(profile_theme='perf-independent')
        viewed = reverse('public_profile', args=[self.owner.username])
        visitor = Client()
        visitor.force_login(self.other)
        for client in (Client(), visitor):
            response = client.get(viewed)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.context['appearance']['theme_key'], 'perf-independent')
            self.assertNotIn(b'PRIVATE-PERF-', response.content)
        denied = visitor.post(reverse('perfil_preview'), {'profile_theme': 'perf-independent'})
        self.assertIn('profile_theme', denied.json()['recusados'])
        self.owner.is_active = False
        self.owner.save(update_fields=['is_active'])
        before_client, after_client = Client(), Client()
        with patch('home.cosmetics.cosmetic_read_context', nullcontext):
            baseline = before_client.get(viewed)
        updated = after_client.get(viewed)
        self.assertEqual(updated.status_code, baseline.status_code)
        self.assertEqual(updated.context['appearance'], baseline.context['appearance'])
        self.assertNotIn(b'PRIVATE-PERF-', updated.content)
        self.assertEqual(after_client.get(reverse('public_profile', args=['unknown-synthetic-profile'])).status_code, 404)
        self.assertIsNone(_READ_CONTEXT.get())
