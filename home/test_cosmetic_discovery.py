"""Discovery never purchases, repairs grants, activates drafts or saves appearance."""
from copy import deepcopy
from datetime import timedelta
from decimal import Decimal
from html.parser import HTMLParser
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.contrib.auth.models import AnonymousUser
from django.template.loader import get_template, render_to_string
from django.test import RequestFactory, SimpleTestCase, override_settings
from django.urls import resolve, reverse
from django.utils import timezone

from home import cosmetic_discovery as discovery
from home.views import cosmetic_discovery as discovery_view


def item(slug, *, origin='staff', scope='ambos', **extra):
    kind, _, key = slug.partition('-')
    return dict(slug=slug, key=key, tipo=kind, label=slug.replace('-', ' ').title(),
                origem=origin, escopo=scope, descricao='', **{'class': ''}, **extra)


def snapshot_fixture():
    entries = [
        item('moldura-gold-trim', origin='livre'), item('moldura-frost', origin='livre'),
        item('moldura-verdant', origin='livre'), item('moldura-arcane-pulse'),
        item('efeito-aurora', origin='evento_manual'), item('badge-beta', origin='evento_manual'),
        item('tema-arcane', origin='conquista'), item('moldura-owned'),
        item('moldura-suspended'), item('moldura-future', origin='loja_braseiro'),
        item('moldura-expired', origin='loja_braseiro'), item('tema-unavailable', origin='loja_mm'),
    ]
    names = {'moldura-gold-trim': ('Friso Dourado', 'frame-gold-trim'),
             'moldura-frost': ('Coroa de Gelo', 'frame-frost'),
             'moldura-verdant': ('Trança Verdejante', 'frame-verdant'),
             'moldura-arcane-pulse': ('Pulso Arcano', 'frame-arcane-pulse'),
             'tema-arcane': ('Arcano Violeta', 'theme-arcane'),
             'efeito-aurora': ('Aurora', 'effect-aurora')}
    for entry in entries:
        if entry['slug'] in names:
            entry['label'], entry['class'] = names[entry['slug']]
    now = timezone.now()
    return {'catalog': {entry['slug']: entry for entry in entries},
            'inventory': {'moldura-suspended': {'origem': 'staff', 'suspenso_em': now}},
            'permanent': {'moldura-owned'}, 'tier': None, 'cash': [],
            'events': [dict(pk=i + 1, cosmetico__slug=slug, active=True, starts_at=start,
                            ends_at=end, cost_braseiros=cost)
                       for i, (slug, start, end, cost) in enumerate([
                           ('badge-beta', None, None, 0),
                           ('moldura-future', now + timedelta(days=2), None, 10),
                           ('moldura-expired', None, now - timedelta(days=2), 20)])],
            'rules': {'tema-arcane': [{'slug': 'arcane-rule', 'nome': 'Marco Arcano',
                                      'descricao': 'Alcance o marco publicado.', 'criterio': 'automatico'}]},
            'legacy': [{'slug': slug, 'status': 'Publicado'} for slug in discovery.LEGACY_FRAME_SLUGS]}


def browser_fixture(query=None):
    request = RequestFactory().get('/cosmeticos/descobrir/')
    request.user = SimpleNamespace(pk=1, username='QA', is_authenticated=True,
                                   is_staff=True, is_superuser=False)
    with override_settings(STATIC_URL='https://discovery.invalid/static/'), patch.object(
            discovery, '_read_snapshot', return_value=snapshot_fixture()):
        context = discovery.discovery_context(request.user, query or {})
        return render_to_string('home/pages/cosmetic_discovery.html',
                                dict(context, request=request, user=request.user, csrf_token='x' * 32))


class MainForms(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.in_main = False
        self.forms = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        if tag == 'main':
            self.in_main = True
        if self.in_main and tag == 'form':
            self.forms.append(dict(attrs))

    def handle_endtag(self, tag):
        if tag == 'main':
            self.in_main = False


class DiscoveryRightsTests(SimpleTestCase):
    def setUp(self):
        self.snapshot = snapshot_fixture()

    def cards(self, snapshot=None, **kwargs):
        return {card['slug']: card for card in discovery.build_discovery(
            snapshot if snapshot is not None else self.snapshot, **kwargs)['cards']}

    def test_all_published_include_unowned_and_legacy_free_activation(self):
        cards = self.cards()
        self.assertEqual(len(cards), len(self.snapshot['catalog']) + 8)
        for slug in discovery.LEGACY_FRAME_SLUGS:
            self.assertEqual(cards[slug]['state'], 'disponivel')
            self.assertEqual([link['url'] for link in cards[slug]['links']],
                             ['/perfil/#perfil-aparencia', '/jogador/personagens/'])
        self.assertEqual(cards['moldura-arcane-pulse']['state'], 'exclusivo')
        self.assertEqual(cards['moldura-arcane-pulse']['links'], [])

    def test_only_eight_explicit_public_proposals_without_any_operation(self):
        entries, _ = discovery.editorial_proposals()
        expected = {kind + '-' + slug for kind in ('efeito', 'moldura') for slug in
                    ('lua-vermelha', 'lua-negra', 'lua-cristal', 'vigilia-das-lanternas')}
        self.assertEqual({entry['slug'] for entry in entries}, expected)
        for slug in expected:
            card = self.cards()[slug]
            self.assertEqual(card['state'], 'preparacao')
            self.assertEqual(card['reason'], 'Em preparação – obtenção ainda não publicada')
            self.assertFalse(card['links'])
            self.assertTrue(card['preview']['package'])
            self.assertNotIn('preco', card)
        self.assertNotIn('moldura-secret-draft', self.cards())

    def test_published_slug_replaces_proposal_without_duplicate_or_new_right(self):
        self.snapshot['catalog']['efeito-lua-vermelha'] = item('efeito-lua-vermelha')
        context = discovery.build_discovery(self.snapshot)
        cards = [card for card in context['cards'] if card['slug'] == 'efeito-lua-vermelha']
        self.assertEqual(len(cards), 1)
        self.assertFalse(cards[0]['proposal'])
        self.assertEqual(cards[0]['state'], 'exclusivo')
        self.assertEqual(cards[0]['links'], [])

    def test_cash_requires_real_active_positive_nondemonstration_offer(self):
        slug = 'moldura-arcane-pulse'
        for active, demo, amount, expected in [(True, False, 12, 'obtivel'),
                (False, False, 12, 'exclusivo'), (True, True, 12, 'exclusivo'),
                (True, False, 0, 'exclusivo')]:
            with self.subTest(active=active, demo=demo, amount=amount):
                self.snapshot['cash'] = [dict(cosmetico__slug=slug, active=active,
                                              demonstration=demo, amount=Decimal(amount))]
                card = self.cards()[slug]
                self.assertEqual(card['state'], expected)
                if expected == 'obtivel':
                    self.assertEqual(card['links'][0]['url'], '/cosmeticos/checkout/#cosmetic-offer-' + slug)

    def test_event_window_boundaries_origin_and_disabled_offer(self):
        now = timezone.now()
        offer = self.snapshot['events'][0]
        offer.update(starts_at=now, ends_at=now + timedelta(hours=1))
        self.assertEqual(self.cards(now=now)['badge-beta']['state'], 'obtivel')
        offer['ends_at'] = now
        self.assertEqual(self.cards(now=now)['badge-beta']['state'], 'indisponivel')
        offer.update(ends_at=None, active=False)
        self.assertNotEqual(self.cards(now=now)['badge-beta']['state'], 'obtivel')
        offer.update(active=True)
        self.snapshot['catalog']['badge-beta']['origem'] = 'staff'
        self.assertNotEqual(self.cards(now=now)['badge-beta']['state'], 'obtivel')

    def test_future_expired_and_unavailable_have_no_acquisition_link(self):
        for slug, state in [('moldura-future', 'futuro'), ('moldura-expired', 'indisponivel'),
                            ('tema-unavailable', 'indisponivel')]:
            self.assertEqual(self.cards()[slug]['state'], state)
            self.assertEqual(self.cards()[slug]['links'], [])

    def test_suspension_scope_and_receipts_follow_existing_independent_rights(self):
        self.snapshot['permanent'].add('moldura-suspended')
        self.assertEqual(self.cards()['moldura-suspended']['state'], 'possuido')
        self.assertTrue(self.cards()['moldura-suspended']['links'])
        self.snapshot['permanent'].remove('moldura-suspended')
        self.assertEqual(self.cards()['moldura-suspended']['state'], 'suspenso')
        self.assertFalse(self.cards()['moldura-suspended']['links'])
        self.snapshot['inventory']['moldura-arcane-pulse'] = {'origem': 'conquista:revoked', 'suspenso_em': timezone.now()}
        self.assertEqual(self.cards()['moldura-arcane-pulse']['state'], 'suspenso')
        owned = self.snapshot['catalog']['moldura-owned']
        owned['escopo'] = 'ficha'
        self.assertEqual(self.cards()['moldura-owned']['links'],
                         [{'label': 'Escolher ficha', 'url': '/jogador/personagens/'}])

    def test_achievement_cta_is_existing_anchor_not_redeem(self):
        card = self.cards()['tema-arcane']
        self.assertEqual(card['state'], 'obtivel')
        self.assertEqual(card['links'][0]['url'], '/perfil/#conquistas')
        self.assertIn('Marco Arcano', card['reason'])

    @override_settings(BONFIRE_COMMERCE_ENABLED=True)
    def test_mm_only_supported_atelier_collection_and_pilot_cash_exclusion(self):
        slug = 'tema-forja-de-brasas'
        self.snapshot['catalog'][slug] = item(slug, origin='loja_mm', preco=5)
        self.snapshot['catalog'][slug]['class'] = 'theme-data'
        self.snapshot['cash'] = [dict(cosmetico__slug=slug, active=True,
                                      demonstration=False, amount=Decimal('20'))]
        self.assertEqual(self.cards()[slug]['links'][0]['url'], '/atelie/?tema=forja-de-brasas')
        self.snapshot['catalog'][slug]['origem'] = 'staff'
        self.assertFalse(self.cards()[slug]['links'])
        with override_settings(BONFIRE_COMMERCE_ENABLED=False):
            self.snapshot['catalog'][slug]['origem'] = 'loja_mm'
            self.assertNotEqual(self.cards()[slug]['state'], 'obtivel')

    def test_no_mutations_or_account_snapshot_leak(self):
        before = deepcopy(self.snapshot)
        self.cards()
        self.assertEqual(before, self.snapshot)
        other = deepcopy(self.snapshot)
        other['permanent'] = set()
        self.assertEqual(self.cards()['moldura-owned']['state'], 'possuido')
        self.assertEqual(self.cards(other)['moldura-owned']['state'], 'exclusivo')

    def test_availability_matches_canonical_free_permanent_suspended_colab_and_inactive(self):
        from home import cosmetics
        user = SimpleNamespace(pk=1, is_authenticated=True)
        cases = [
            ('livre', 'staff', True, False, None, True, True),
            ('staff', 'compra_asaas', True, True, None, True, True),
            ('conquista', 'conquista:rank', True, False, None, True, False),
            ('colaborador', 'colaborador', True, False, 'duque', True, True),
            ('colaborador', 'colaborador', False, False, None, True, False),
            ('staff', 'colaborador', True, False, 'duque', True, False),
            ('livre', 'staff', False, False, None, False, False),
        ]
        for origin, inv_origin, suspended, permanent, tier, active, expected in cases:
            with self.subTest(origin=origin, suspended=suspended, permanent=permanent, tier=tier, active=active):
                entry = item('moldura-parity', origin=origin, requer_plano='conde')
                snapshot = deepcopy(self.snapshot)
                snapshot['catalog'] = {entry['slug']: entry} if active else {}
                snapshot['inventory'] = {entry['slug']: {'origem': inv_origin,
                    'suspenso_em': timezone.now() if suspended else None}}
                snapshot['permanent'] = {entry['slug']} if permanent else set()
                snapshot['tier'] = tier
                values = ({entry['key']} if permanent or
                          (not suspended and not inv_origin.startswith('colaborador')) else set())
                with patch.object(cosmetics, 'get_catalog', return_value={entry['key']: entry} if active else {}), patch.object(
                    cosmetics, '_user_inventory_values', return_value=values
                ), patch.object(cosmetics, '_read_colab_tier', return_value=tier), cosmetics.cosmetic_read_context():
                    allowed = cosmetics.cosmetic_allowed(user, 'moldura', entry['key'])
                    projected = self.cards(snapshot).get(entry['slug'])
                self.assertEqual(allowed, expected)
                self.assertEqual(bool(projected and projected['state'] in {'disponivel', 'possuido'}), allowed)


class DiscoveryRequestTests(SimpleTestCase):
    def test_editors_offer_plain_get_links_without_changing_preview_scripts(self):
        for path in ('home/pages/perfil.html', 'home/pages/ficha_detail.html'):
            source = get_template(path).template.source
            self.assertIn('href="{% url \'cosmetic_discovery\' %}" target="_blank" rel="noopener">Explorar cosméticos', source)

    def test_auth_get_only_and_no_grant_service(self):
        self.assertIs(resolve('/cosmeticos/descobrir/').func, discovery_view)
        factory = RequestFactory()
        request = factory.get(reverse('cosmetic_discovery'))
        request.user = AnonymousUser()
        self.assertEqual(discovery_view(request).status_code, 302)
        request = factory.post(reverse('cosmetic_discovery'), {'slug': 'tema-lua-vermelha'})
        request.user = SimpleNamespace(pk=1, is_authenticated=True)
        self.assertEqual(discovery_view(request).status_code, 405)
        request = factory.get(reverse('cosmetic_discovery'))
        request.user = SimpleNamespace(pk=1, is_authenticated=True, username='QA',
                                       is_active=True, is_staff=False, is_superuser=False)
        with patch.object(discovery, '_read_snapshot', return_value=snapshot_fixture()), patch(
            'home.rank_cosmetic_rewards.sync_rank_cosmetics', side_effect=AssertionError('must not grant')
        ), patch('home.context_processors.user_profile', side_effect=AssertionError('must not create profile')), patch(
            'home.models.UserProfile.objects.filter'
        ) as profile_read:
            profile_read.return_value.first.return_value = None
            response = discovery_view(request)
            self.assertEqual(response.status_code, 200)
            self.assertIn('8 propostas de arte', response.content.decode())
            self.assertEqual(response['Cache-Control'], 'private, no-store')
            self.assertIn('Cookie', response['Vary'])
            profile_read.assert_called_once_with(user=request.user)

    def test_search_accents_slug_filters_and_invalid_parameters(self):
        for query, expected in [({'q': 'TRANCA'}, 1), ({'q': 'moldura-frost'}, 1),
                ({'colecao': 'luas'}, 6), ({'colecao': 'vigilia'}, 2),
                ({'estado': 'preparacao', 'tipo': 'moldura'}, 4),
                ({'estado': 'suspenso'}, 1), ({'q': 'not-present'}, 0)]:
            with self.subTest(query=query), patch.object(discovery, '_read_snapshot', return_value=snapshot_fixture()):
                self.assertEqual(discovery.discovery_context(SimpleNamespace(pk=1), query)['visible_count'], expected)
        with patch.object(discovery, '_read_snapshot', return_value=snapshot_fixture()):
            context = discovery.discovery_context(SimpleNamespace(pk=1), {'tipo': 'invalid', 'estado': 'bad'})
            self.assertEqual(context['visible_count'], len(context['cards']))

    def test_template_contains_no_transaction_or_equipping_form(self):
        html = browser_fixture()
        self.assertEqual([form.get('method') for form in MainForms(html).forms], ['get'])
        self.assertNotIn('name="slug"', html)
        self.assertNotIn('data-purchase-review', html)
        self.assertIn('name="q"', html)
        self.assertIn('Em preparação – obtenção ainda não publicada', html)
        self.assertIn('moldura-gold-trim', html)
        self.assertNotIn('R$ ', html)

    def test_snapshot_queries_are_read_only_batched_and_user_scoped(self):
        from contextlib import ExitStack
        source = snapshot_fixture()
        with ExitStack() as stack:
            managers = {}
            for model in ('CosmeticCheckoutOffer', 'EventCosmeticOffer', 'TbConquista',
                          'TbCosmetico', 'TbUsuarioCosmetico'):
                managers[model] = stack.enter_context(patch('home.models.' + model + '.objects'))
            managers['TbUsuarioCosmetico'].filter.return_value.values.return_value = []
            managers['TbConquista'].filter.return_value.values.return_value = []
            managers['TbCosmetico'].filter.return_value.values_list.return_value = []
            managers['CosmeticCheckoutOffer'].filter.return_value.values.return_value = []
            managers['EventCosmeticOffer'].filter.return_value.values.return_value = []
            stack.enter_context(patch.object(discovery, 'get_catalog', side_effect=lambda kind: {
                value['key']: value for value in source['catalog'].values() if value['tipo'] == kind}))
            stack.enter_context(patch('home.cosmetic_entitlements.permanent_cosmetic_slugs', return_value=set()))
            user = SimpleNamespace(pk=7)
            snapshot = discovery._read_snapshot(user)
            self.assertEqual(len(snapshot['catalog']), len(source['catalog']))
            self.assertTrue(all(row['status'] == 'Ausente no banco' for row in snapshot['legacy']))
            managers['TbUsuarioCosmetico'].filter.assert_called_once_with(
                user=user, cosmetico__slug__in=set(source['catalog']))
            managers['TbConquista'].filter.assert_called_once_with(ativo=True, secreta=False)
            for manager in managers.values():
                self.assertFalse(any(call[0].split('.')[-1] in
                    {'create', 'update', 'delete', 'get_or_create', 'update_or_create'}
                    for call in manager.mock_calls))
