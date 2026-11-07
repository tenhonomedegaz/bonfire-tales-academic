"""Run: py -m home.test_master_market_quantity --isolated (SQLite memory only)."""

import ast
import sys
from pathlib import Path

ISOLATED = __name__ == '__main__' and '--isolated' in sys.argv
ROOT = Path(__file__).resolve().parents[1]
if ISOLATED:
    from django.conf import settings

    settings.configure(
        SECRET_KEY='isolated-master-market-tests', USE_TZ=True, BASE_DIR=ROOT,
        INSTALLED_APPS=['django.contrib.auth', 'django.contrib.contenttypes', 'home'],
        DATABASES={'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':memory:'}},
        DEFAULT_AUTO_FIELD='django.db.models.AutoField', ROOT_URLCONF=__name__,
        ALLOWED_HOSTS=['testserver'], MIDDLEWARE=[], STATIC_URL='/static/',
        TEMPLATES=[{'BACKEND': 'django.template.backends.django.DjangoTemplates',
                    'OPTIONS': {'context_processors': ['django.template.context_processors.request'],
                                'loaders': [
                                    ('django.template.loaders.locmem.Loader', {'home/base.html':
                                     '<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
                                     '<style>*,::before,::after{box-sizing:border-box}body{margin:0}</style>'
                                     '{% block extra_head %}{% endblock %}</head>'
                                     '<body class="bft-master-market"><main class="mm-main">'
                                     '{% block content %}{% endblock %}</main></body></html>'}),
                                    ('django.template.loaders.filesystem.Loader', [ROOT / 'home/templates'])]}}],
    )
    import django

    django.setup()

import unittest
from types import ModuleType, SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.db import connection
from django.http import Http404, HttpResponse
from django.shortcuts import redirect, render
from django.test import RequestFactory, TestCase, override_settings
from django.urls import path, reverse
from django.views.decorators.http import require_POST

from home.master_market import RedemptionError, quantity_limit, redeem_reward, redemption_token
from home.models import (MestreOuroDireito, TbRecompensaMestre, TbReiDaColina,
                         TbTransacaoMestre, TbPersonagem, TbPersonagemAventura,
                         TbTransacao, UserProfile)


def market_views():
    """Load only these real views, without importing unrelated integrations/settings."""
    names = {'_perfil_mestre', 'mercado_mestre_view', 'mercado_mestre_resgatar',
             'mercado_mestre_resgatar_braseiros'}
    tree = ast.parse((ROOT / 'home/views.py').read_text(encoding='utf-8-sig'))
    module = ModuleType('home._isolated_master_market_views')
    module.__package__ = 'home'
    module.__dict__.update(login_required=login_required, require_POST=require_POST,
                           Http404=Http404, redirect=redirect, render=render, reverse=reverse)
    selected = ast.Module(body=[node for node in tree.body
                               if isinstance(node, ast.FunctionDef) and node.name in names], type_ignores=[])
    exec(compile(selected, str(ROOT / 'home/views.py'), 'exec'), module.__dict__)
    return module


views = market_views()
urlpatterns = [path('market/', views.mercado_mestre_view, name='mestre_mercado'),
               path('redeem/', views.mercado_mestre_resgatar, name='mestre_resgatar'),
               path('old-embers/', views.mercado_mestre_resgatar_braseiros,
                    name='mestre_resgatar_braseiros')]
for route in ('character_slots', 'guia_mestres', 'profile', 'mestre_resgatar_braseiros',
              'mestre_registrar_aventura'):
    if route == 'mestre_resgatar_braseiros':
        continue
    urlpatterns.append(path(route + '/', lambda request: HttpResponse(), name=route))


@override_settings(ROOT_URLCONF=__name__)
class MasterMarketQuantityTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='quantity-owner')
        self.profile = UserProfile.objects.get(user=self.user)
        self.profile.moedas_mestragem = 1000
        self.profile.mm_ganhas_total = 2000
        self.profile.moedas_evento = 20
        self.profile.save()
        self.reward = TbRecompensaMestre.objects.create(
            slug='quantity-reward', nome='Recompensa de teste', preco_mm=7)
        self.factory = RequestFactory()

    def token(self, reward=None, user=None, price=None):
        reward, user = reward or self.reward, user or self.user
        return redemption_token(user.pk, reward.pk, reward.preco_mm if price is None else price,
                                reward.efeito)

    def balance(self):
        self.profile.refresh_from_db()
        return self.profile.moedas_mestragem

    def assert_rejected(self, code, quantity, **kwargs):
        before, receipts = self.balance(), TbTransacaoMestre.objects.count()
        with self.assertRaisesMessage(RedemptionError, code):
            redeem_reward(self.user, self.reward.pk, quantity, **kwargs)
        self.assertEqual(self.balance(), before)
        self.assertEqual(TbTransacaoMestre.objects.count(), receipts)

    def post(self, data=None, method='post', allowed=True):
        request = getattr(self.factory, method)('/redeem/', data or {})
        request.user = self.user
        with patch('home.permissions.is_mestre', return_value=allowed):
            return views.mercado_mestre_resgatar(request)

    def delivery_setup(self, **fields):
        self.reward.efeito = 'aventura_recompensa'
        self.reward.save(update_fields=['efeito'])
        with patch('home.rank_cosmetic_rewards.sync_rank_cosmetics'):
            return TbPersonagem.objects.create(dono=self.user, nome='Mesmo nome', **fields)

    def deliver(self, character, quantity='1', events=None, token=None):
        return redeem_reward(self.user, self.reward.pk, quantity, token or self.token(),
                             character_id=character.pk, use_event_coins=events)

    def test_adventure_reward_delivers_gold_and_destination_by_id(self):
        character = self.delivery_setup(aventuras=8, carteira_pc=100, braseiros=5, nivel=4)
        self.assertEqual(self.deliver(character, '2'), 'entregue')
        character.refresh_from_db()
        self.assertEqual((character.aventuras, character.carteira_pc, character.braseiros,
                          character.nivel), (10, 37100, 5, 4))
        receipt = TbTransacaoMestre.objects.get()
        self.assertEqual((receipt.personagem_id, receipt.recompensa_id, receipt.quantidade),
                         (character.pk, self.reward.pk, 2))
        self.assertEqual(receipt.detalhes_json['moedas_evento_gastas'], 0)
        self.assertEqual(receipt.detalhes_json['niveis_recompensa'], [4, 5])
        adventure = TbPersonagemAventura.objects.get()
        self.assertEqual((adventure.origem, adventure.qtd_aventuras, adventure.ouro_pago_pc),
                         ('mercado_mestre', 2, 37000))
        self.assertIsNone(adventure.id_mestre_id)
        self.assertIsNone(adventure.data_missao)
        self.assertEqual(TbTransacao.objects.get().valor_pc, 37000)
        self.assertEqual(self.balance(), 986)
        self.assertEqual((self.profile.mm_ganhas_total, self.profile.moedas_evento), (2000, 20))

    def test_event_coins_are_joint_and_use_sequential_rank_engine(self):
        character = self.delivery_setup(aventuras=8, nivel=4)
        token = self.token()
        self.assertEqual(self.deliver(character, '2', 'on', token), 'entregue')
        character.refresh_from_db()
        self.assertEqual((character.aventuras, character.carteira_pc, character.braseiros),
                         (10, 37000, 5))
        self.assertEqual(self.balance(), 986)
        self.assertEqual(self.profile.moedas_evento, 18)
        receipt = TbTransacaoMestre.objects.get()
        self.assertEqual(receipt.detalhes_json['moedas_evento_gastas'], 2)
        self.assertEqual(receipt.detalhes_json['braseiros_pago'], 5)
        self.assertEqual(receipt.detalhes_json['ranks_recompensa'], ['Obsidiana', 'Ametista'])
        self.assertEqual(receipt.detalhes_json['nivel_personagem_no_resgate'], 4)
        self.assertEqual(receipt.detalhes_json['criterio_braseiros'],
                         'rank_progressao_antes_de_cada_aventura')
        self.reward.ativo = False
        self.reward.efeito = 'manual'
        self.reward.preco_mm = 999
        self.reward.save()
        TbPersonagem.objects.filter(pk=character.pk).update(arquivado=True)
        self.assertEqual(self.deliver(character, '2', 'on', token), 'entregue')
        self.assertEqual(TbPersonagemAventura.objects.count(), 1)
        self.assertEqual(TbTransacao.objects.count(), 1)
        self.assertEqual(self.balance(), 986)
        self.assertEqual(self.profile.moedas_evento, 18)

    def test_rank_of_recipient_uses_progression_not_unspent_class_levels(self):
        from home.character_engine import derive
        character = self.delivery_setup(aventuras=9, nivel=4)
        before = derive(character)
        self.assertEqual(before['nivel_total'], 4)
        self.assertEqual(before['bonus_proficiencia'], 2)
        self.assertEqual(before['progressao']['rank'], 'Ametista')
        self.assertEqual(before['progressao']['nivel_aventuras'], 5)
        self.deliver(character, '2', 'on')
        character.refresh_from_db()
        self.assertEqual((character.nivel, character.aventuras, character.braseiros), (4, 11, 6))
        receipt = TbTransacaoMestre.objects.get()
        self.assertEqual(receipt.detalhes_json['ranks_recompensa'], ['Ametista', 'Ametista'])
        self.assertEqual(receipt.detalhes_json['nivel_personagem_no_resgate'], 4)

    def reward_admin(self):
        from django.contrib.admin import AdminSite, ModelAdmin
        tree = ast.parse((ROOT / 'home/admin.py').read_text(encoding='utf-8-sig'))
        definition = next(node for node in tree.body
                          if isinstance(node, ast.ClassDef) and node.name == 'TbRecompensaMestreAdmin')
        definition.decorator_list = []
        namespace = {'admin': SimpleNamespace(ModelAdmin=ModelAdmin)}
        exec(compile(ast.Module(body=[definition], type_ignores=[]),
                     str(ROOT / 'home/admin.py'), 'exec'), namespace)
        return namespace['TbRecompensaMestreAdmin'](TbRecompensaMestre, AdminSite(name='market-test'))

    def test_existing_product_can_be_activated_by_id_in_admin_form(self):
        registered = self.reward_admin()
        request = self.factory.post('/admin/home/tbrecompensamestre/%s/change/' % self.reward.pk)
        request.user = self.user
        self.assertFalse(registered.has_change_permission(request, self.reward))
        self.user.is_superuser = True
        self.assertTrue(registered.has_change_permission(request, self.reward))
        original = (self.reward.pk, self.reward.slug, self.reward.preco_mm)
        form_class = registered.get_form(request, self.reward)
        self.assertIn('efeito', form_class.base_fields)
        self.assertIn('efeito', registered.list_display)
        self.assertIn('efeito', registered.list_filter)
        form = form_class(data={
            'nome': self.reward.nome, 'slug': self.reward.slug, 'preco_mm': 7,
            'mensalidade_mm': 0, 'preco_vitalicio_aprovado_mm': '', 'tipo': 'normal',
            'efeito': 'aventura_recompensa', 'ativo': 'on', 'ordem': 0,
        }, instance=self.reward)
        self.assertTrue(form.is_valid(), form.errors.as_json())
        self.assertEqual(form.changed_data, ['efeito'])
        registered.save_model(request, form.save(commit=False), form, change=True)
        self.reward.refresh_from_db()
        self.assertEqual((self.reward.pk, self.reward.slug, self.reward.preco_mm), original)
        self.assertEqual(TbRecompensaMestre.objects.count(), 1)
        self.assertEqual(self.reward.efeito, 'aventura_recompensa')
        self.assertEqual(self.balance(), 1000)
        self.assertFalse(TbTransacaoMestre.objects.exists())
        with patch('home.rank_cosmetic_rewards.sync_rank_cosmetics'):
            character = TbPersonagem.objects.create(dono=self.user, nome='Destino por ID')
        self.assertIn('name="personagem" required', self.page_html(self.reward.pk, [character]))
        self.assertEqual(self.deliver(character, '1', 'on'), 'entregue')
        self.assertEqual(TbTransacaoMestre.objects.get().recompensa_id, original[0])

    def test_catalog_validation_rejects_adventure_effect_on_special_offers(self):
        from django.core.exceptions import ValidationError
        self.reward.efeito = 'aventura_recompensa'
        for kind in ('assinatura', 'leilao'):
            with self.subTest(kind=kind):
                self.reward.tipo = kind
                with self.assertRaises(ValidationError) as caught:
                    self.reward.full_clean()
                self.assertIn('efeito', caught.exception.message_dict)
        self.reward.refresh_from_db()
        self.assertEqual(self.reward.efeito, 'manual')

    def test_replay_cannot_change_destination_quantity_or_event_choice(self):
        first = self.delivery_setup()
        second = self.delivery_setup()
        token = self.token()
        self.deliver(first, '2', 'on', token)
        for character, quantity, events in ((second, '2', 'on'), (first, '3', 'on'),
                                             (first, '2', None)):
            with self.subTest(character=character.pk, quantity=quantity, events=events):
                with self.assertRaisesMessage(RedemptionError, 'operacao'):
                    self.deliver(character, quantity, events, token)
        self.assertEqual(self.balance(), 986)
        self.assertEqual(self.profile.moedas_evento, 18)
        self.assertEqual(TbPersonagemAventura.objects.count(), 1)

    def test_delivery_requires_active_owned_character_not_a_name(self):
        character = self.delivery_setup()
        other = get_user_model().objects.create_user(username='different-owner')
        with patch('home.rank_cosmetic_rewards.sync_rank_cosmetics'):
            foreign = TbPersonagem.objects.create(dono=other, nome=character.nome)
        TbPersonagem.objects.filter(pk=character.pk).update(arquivado=True)
        for destination in (None, '', 'Mesmo nome', 'abc', '-1', '1e2', '9' * 50,
                            foreign.pk, character.pk, 999999):
            with self.subTest(destination=destination):
                self.assert_rejected('sem_personagem', '1', token=self.token(),
                                     character_id=destination)
        self.assertFalse(TbPersonagemAventura.objects.exists())

    def test_joint_delivery_rejects_insufficient_events_without_partial_mm_debit(self):
        character = self.delivery_setup()
        self.profile.moedas_evento = 1
        self.profile.save(update_fields=['moedas_evento'])
        self.assert_rejected('sem_evento', '2', token=self.token(),
                             character_id=character.pk, use_event_coins='on')
        character.refresh_from_db()
        self.assertEqual((character.aventuras, character.carteira_pc, character.braseiros), (0, 0, 0))
        self.assertEqual(self.profile.moedas_evento, 1)

    def test_joint_delivery_mm_failure_preserves_events_and_character(self):
        character = self.delivery_setup()
        self.profile.moedas_mestragem = 6
        self.profile.save(update_fields=['moedas_mestragem'])
        self.assert_rejected('saldo', '1', token=self.token(), character_id=character.pk,
                             use_event_coins='on')
        self.assertEqual(self.profile.moedas_evento, 20)
        self.assertFalse(TbPersonagemAventura.objects.exists())

    def test_delivery_and_receipt_failures_roll_back_all_writes(self):
        character = self.delivery_setup()
        for target in ('TbPersonagemAventura.objects.create', 'TbTransacao.objects.create',
                       'TbTransacaoMestre.save'):
            with self.subTest(target=target):
                with patch('home.master_market.' + target, side_effect=RuntimeError('failed')):
                    with self.assertRaises(RuntimeError):
                        self.deliver(character, '2', 'on')
                self.assertEqual(self.balance(), 1000)
                self.assertEqual(self.profile.moedas_evento, 20)
                character.refresh_from_db()
                self.assertEqual((character.aventuras, character.carteira_pc, character.braseiros), (0, 0, 0))
                self.assertFalse(TbTransacaoMestre.objects.exists())
                self.assertFalse(TbPersonagemAventura.objects.exists())
                self.assertFalse(TbTransacao.objects.exists())

    def test_final_receipt_failure_rolls_back_delivery_and_same_token_can_retry(self):
        character = self.delivery_setup()
        token = self.token()
        original = TbTransacaoMestre.save

        def fail_final_receipt(instance, *args, **kwargs):
            if kwargs.get('update_fields') == ['detalhes_json']:
                raise RuntimeError('final receipt failed')
            return original(instance, *args, **kwargs)

        with patch.object(TbTransacaoMestre, 'save', new=fail_final_receipt):
            with self.assertRaisesMessage(RuntimeError, 'final receipt failed'):
                self.deliver(character, '2', 'on', token)
        self.assertEqual(self.balance(), 1000)
        self.assertEqual(self.profile.moedas_evento, 20)
        character.refresh_from_db()
        self.assertEqual((character.aventuras, character.carteira_pc, character.braseiros), (0, 0, 0))
        self.assertFalse(TbTransacaoMestre.objects.exists())
        self.assertFalse(TbTransacao.objects.exists())
        self.assertFalse(TbPersonagemAventura.objects.exists())
        self.assertEqual(self.deliver(character, '2', 'on', token), 'entregue')
        self.assertEqual(self.balance(), 986)
        self.assertEqual(self.profile.moedas_evento, 18)

    def test_exact_event_balance_is_consumed_without_clamping(self):
        character = self.delivery_setup()
        self.profile.moedas_evento = 2
        self.profile.save(update_fields=['moedas_evento'])
        self.deliver(character, '2', 'on')
        self.assertEqual(self.balance(), 986)
        self.assertEqual(self.profile.moedas_evento, 0)
        self.assertEqual(TbTransacaoMestre.objects.get().detalhes_json['moedas_evento_gastas'], 2)

    def test_no_text_inference_and_no_events_on_manual_rewards(self):
        self.reward.nome = 'Aventura e Recompensa'
        self.reward.descricao = '1 aventura e braseiros'
        self.reward.save()
        redeem_reward(self.user, self.reward.pk, token=self.token())
        self.assertFalse(TbPersonagemAventura.objects.exists())
        self.assert_rejected('contrato', '1', token=self.token(), use_event_coins='on')
        self.assert_rejected('operacao', '1', token=self.token(), use_event_coins='2')

    def test_delivery_requires_signed_current_contract(self):
        stale = self.token()
        character = self.delivery_setup()
        self.assert_rejected('contrato', '1', token=stale, character_id=character.pk)
        self.assert_rejected('operacao', '1', character_id=character.pk)

    def test_legacy_receipt_never_causes_a_new_debit_or_invented_delivery(self):
        from django.core import signing
        from home.master_market import TOKEN_SALT
        operation = 'b' * 32
        token = signing.dumps([self.user.pk, self.reward.pk, 7, operation], salt=TOKEN_SALT)
        TbTransacaoMestre.objects.create(mestre=self.user, tipo='resgate', valor_mm=-7,
            saldo_mm=1000, descricao='Resgate antigo [mm:%s:%s:1]' % (operation, self.reward.pk))
        self.assertEqual(redeem_reward(self.user, self.reward.pk, token=token), 'resgatado')
        character = self.delivery_setup()
        self.assert_rejected('conciliacao', '1', token=token, character_id=character.pk,
                             use_event_coins='on')
        receipt = TbTransacaoMestre.objects.get()
        self.assertIsNone(receipt.personagem_id)
        self.assertEqual(receipt.detalhes_json, {})
        self.assertEqual(self.balance(), 1000)

    def test_joint_post_and_retired_standalone_endpoint(self):
        character = self.delivery_setup()
        response = self.post({'recompensa': self.reward.pk, 'quantidade': '2',
            'personagem': str(character.pk), 'usar_moedas_evento': 'on', 'operacao_token': self.token()})
        self.assertEqual(response.url, '/market/?m=entregue')
        request = self.factory.post('/old-embers/', {'personagem': character.pk, 'moedas': '2'})
        request.user = self.user
        with patch('home.permissions.is_mestre', return_value=True):
            self.assertEqual(views.mercado_mestre_resgatar_braseiros(request).url,
                             '/market/?m=resgate_conjunto')
        self.assertEqual(self.balance(), 986)
        self.assertEqual(self.profile.moedas_evento, 18)

    def test_real_routes_use_only_new_market_scoped_views(self):
        tree = ast.parse((ROOT / 'home/urls.py').read_text(encoding='utf-8-sig'))
        routes = {node.args[0].value: ast.unparse(node.args[1])
                  for node in ast.walk(tree) if isinstance(node, ast.Call)
                  and isinstance(node.func, ast.Name) and node.func.id == 'path'
                  and len(node.args) > 1 and isinstance(node.args[0], ast.Constant)}
        self.assertEqual(routes['mestre/mercado-de-mestre/resgatar/'],
                         'views.mercado_mestre_resgatar')
        self.assertEqual(routes['mestre/mercado-de-mestre/resgatar-braseiros/'],
                         'views.mercado_mestre_resgatar_braseiros')

    def test_thirty_units_one_receipt_and_no_event_or_lifetime_changes(self):
        self.assertEqual(redeem_reward(self.user, self.reward.pk, '30', self.token()), 'resgatado')
        self.assertEqual(self.balance(), 790)
        receipt = TbTransacaoMestre.objects.get()
        self.assertEqual((receipt.valor_mm, receipt.saldo_mm, receipt.tipo), (-210, 790, 'resgate'))
        for text in ('30 x Recompensa de teste', '7 MM/un.', 'total 210 MM'):
            self.assertIn(text, receipt.descricao)
        self.assertEqual((self.profile.mm_ganhas_total, self.profile.moedas_evento), (2000, 20))
        self.assertFalse(MestreOuroDireito.objects.exists())

    def test_legacy_missing_quantity_and_token_defaults_to_one(self):
        response = self.post({'recompensa': self.reward.pk})
        self.assertEqual(response.url, '/market/?m=resgatado')
        self.assertEqual(self.balance(), 993)

    def test_full_batch_requires_full_balance(self):
        self.profile.moedas_mestragem = 209
        self.profile.save(update_fields=['moedas_mestragem'])
        self.assert_rejected('saldo', '30')

    def test_invalid_quantities_are_not_coerced_or_clamped(self):
        for value in ('0', '-1', '', '1.5', '1e2', '30.0', 'abc', '101', '1001', '999999999999', ' 30 ', '+30'):
            with self.subTest(value=value):
                self.assert_rejected('quantidade', value)

    @override_settings(MASTER_MARKET_MAX_QUANTITY=30)
    def test_configured_limit_applies_on_server(self):
        self.assertEqual(quantity_limit(self.reward), 30)
        self.assert_rejected('quantidade', '31')
        redeem_reward(self.user, self.reward.pk, '30')
        self.assertEqual(self.balance(), 790)

    def test_exact_balance_and_free_rewards(self):
        self.profile.moedas_mestragem = 210
        self.profile.save(update_fields=['moedas_mestragem'])
        redeem_reward(self.user, self.reward.pk, '30')
        self.assertEqual(self.balance(), 0)
        self.reward.preco_mm = 0
        self.reward.save()
        redeem_reward(self.user, self.reward.pk, '30')
        self.assertEqual(self.balance(), 0)
        self.assertEqual(TbTransacaoMestre.objects.count(), 2)

    def test_client_price_total_and_balance_are_ignored(self):
        response = self.post({'recompensa': self.reward.pk, 'quantidade': '30',
                              'preco_mm': '0', 'total': '0', 'saldo': '999999',
                              'operacao_token': self.token()})
        self.assertEqual(response.url, '/market/?m=resgatado')
        self.assertEqual(self.balance(), 790)

    def test_same_form_replay_has_one_debit_even_after_offer_changes(self):
        token = self.token()
        redeem_reward(self.user, self.reward.pk, '30', token)
        self.reward.preco_mm = 99
        self.reward.ativo = False
        self.reward.save()
        self.assertEqual(redeem_reward(self.user, self.reward.pk, '30', token), 'resgatado')
        self.assertEqual(self.balance(), 790)
        self.assertEqual(TbTransacaoMestre.objects.count(), 1)
        self.assert_rejected('operacao', '31', token=token)

    def test_distinct_forms_can_redeem_same_quantity(self):
        for _ in range(2):
            redeem_reward(self.user, self.reward.pk, '30', self.token())
        self.assertEqual(self.balance(), 580)
        self.assertEqual(TbTransacaoMestre.objects.count(), 2)

    def test_token_is_bound_to_user_reward_and_signed_price(self):
        other = get_user_model().objects.create_user(username='quantity-other')
        self.assert_rejected('operacao', '30', token=self.token(user=other))
        second = TbRecompensaMestre.objects.create(slug='second', nome='Other', preco_mm=7)
        self.assert_rejected('operacao', '30', token=self.token(reward=second))
        self.assert_rejected('operacao', '30', token=self.token() + 'tampered')
        self.assert_rejected('preco', '30', token=self.token(price=1))
        stale = self.token()
        self.reward.preco_mm = 8
        self.reward.save()
        self.assert_rejected('preco', '30', token=stale)

    def test_receipt_failure_rolls_back_wallet(self):
        with patch('home.master_market.TbTransacaoMestre.objects.create', side_effect=RuntimeError('receipt failure')):
            with self.assertRaisesMessage(RuntimeError, 'receipt failure'):
                redeem_reward(self.user, self.reward.pk, '30', self.token())
        self.assertEqual(self.balance(), 1000)
        self.assertFalse(TbTransacaoMestre.objects.exists())

    def test_missing_inactive_and_negative_price_offers_do_not_debit(self):
        self.assertEqual(self.post({'recompensa': 'invalid'}).url, '/market/?m=invalido')
        self.assertEqual(self.post({'recompensa': self.reward.pk + 12345}).url, '/market/?m=invalido')
        self.reward.ativo = False
        self.reward.save()
        self.assert_rejected('invalido', '30')
        self.reward.ativo = True
        self.reward.preco_mm = -1
        self.reward.save()
        self.assert_rejected('invalido', '30')

    def test_permission_and_post_only(self):
        with self.assertRaises(Http404):
            self.post({'recompensa': self.reward.pk, 'quantidade': '30'}, allowed=False)
        self.assertEqual(self.post(method='get').status_code, 405)
        self.assertEqual(self.balance(), 1000)

    def test_auction_single_unit_current_price_and_idempotent_replay(self):
        self.reward.tipo = 'leilao'
        self.reward.save()
        self.assertEqual(quantity_limit(self.reward), 1)
        self.assert_rejected('quantidade', '30')
        self.assertFalse(TbReiDaColina.objects.exists())
        state = TbReiDaColina.objects.create(preco_atual=120)
        token = self.token(price=120)
        self.assertEqual(redeem_reward(self.user, self.reward.pk, '1', token), 'rei')
        self.assertEqual(redeem_reward(self.user, self.reward.pk, '1', token), 'rei')
        state.refresh_from_db()
        self.assertEqual((state.holder_id, state.preco_atual), (self.user.pk, 220))
        self.assertEqual(self.balance(), 880)
        self.assertEqual(TbTransacaoMestre.objects.count(), 1)
        self.assert_rejected('ja_rei', '1')

    def test_auction_initialization_and_failure_are_atomic(self):
        self.reward.tipo = 'leilao'
        self.reward.save()
        with patch('home.master_market.TbReiDaColina.save', side_effect=RuntimeError('auction failure')):
            with self.assertRaisesMessage(RuntimeError, 'auction failure'):
                redeem_reward(self.user, self.reward.pk)
        self.assertFalse(TbReiDaColina.objects.exists())
        self.assertEqual(self.balance(), 1000)
        state = TbReiDaColina.objects.create(preco_atual=120)
        with patch('home.master_market.TbReiDaColina.save', side_effect=RuntimeError('auction failure')):
            with self.assertRaises(RuntimeError):
                redeem_reward(self.user, self.reward.pk)
        state.refresh_from_db()
        self.assertIsNone(state.holder_id)
        self.assertEqual(self.balance(), 1000)
        self.assertFalse(TbTransacaoMestre.objects.exists())

    def test_legacy_subscription_redirects_without_granting_slots(self):
        self.reward.tipo = 'assinatura'
        self.reward.save()
        self.assert_rejected('quantidade', '30')
        self.assertEqual(self.post({'recompensa': self.reward.pk}).url, '/character_slots/')
        self.assertEqual(self.balance(), 1000)
        self.assertFalse(TbTransacaoMestre.objects.exists())

    def test_long_names_keep_complete_delivery_details_and_replay_marker(self):
        self.reward.nome = 'R' * 120
        self.reward.save()
        token = self.token()
        redeem_reward(self.user, self.reward.pk, '30', token)
        receipt = TbTransacaoMestre.objects.get()
        self.assertLessEqual(len(receipt.descricao), 255)
        self.assertIn('total 210 MM', receipt.descricao)
        redeem_reward(self.user, self.reward.pk, '30', token)
        self.assertEqual(self.balance(), 790)

    def page_html(self, reward_id, characters=None):
        request = self.factory.get('/market/', {'recompensa': reward_id})
        request.user = SimpleNamespace(pk=self.user.pk, id=self.user.pk, profile=self.profile, is_authenticated=True,
                                       personagens=SimpleNamespace(filter=lambda **kw: SimpleNamespace(only=lambda *a: characters or [])),
                                       aventuras_mestradas=SimpleNamespace(all=lambda: []),
                                       transacoes_mm=self.user.transacoes_mm)
        with patch('home.permissions.is_mestre', return_value=True), patch(
                'home.mestre_ouro.has_unreconciled_mestre_ouro_history', return_value=False), patch(
                'home.models.MestreOuroDireito.objects.filter') as rights:
            rights.return_value.exists.return_value = False
            response = views.mercado_mestre_view(request)
        return response.content.decode()

    def test_no_js_template_selects_requested_reward_and_posts_quantity(self):
        second = TbRecompensaMestre.objects.create(slug='second', nome='Second reward', preco_mm=11)
        html = self.page_html(second.pk)
        self.assertIn('name="quantidade" type="number"', html)
        self.assertIn('max="100" step="1" value="1" required', html)
        self.assertIn('name="operacao_token"', html)
        self.assertIn('data-mm-unit-price="11"', html)
        self.assertNotIn('aria-labelledby="mm-name-%s" hidden' % second.pk, html)
        self.assertIn('aria-labelledby="mm-name-%s" hidden' % self.reward.pk, html)
        self.assertIn('<noscript>', html)
        self.assertFalse(TbTransacaoMestre.objects.exists())

    def test_delivery_template_has_native_destination_and_joint_coin_choice(self):
        character = self.delivery_setup()
        html = self.page_html(self.reward.pk, [character])
        self.assertIn('name="personagem" required', html)
        self.assertIn('name="usar_moedas_evento"', html)
        self.assertIn('value="%s">Mesmo nome</option>' % character.pk, html)
        self.assertNotIn('data-mm-review="eventos"', html)
        self.assertNotIn('action="/old-embers/"', html)
        self.assertNotIn('A cada 100 MM', html)

    def test_0175_matches_market_contract_without_rewriting_legacy_data(self):
        from django.db import migrations
        from django.db.migrations.loader import MigrationLoader
        loader = MigrationLoader(None)
        migration = loader.disk_migrations[('home', '0175_master_market_delivery')]
        self.assertFalse(any(isinstance(operation, (migrations.RunPython, migrations.RunSQL))
                             for operation in migration.operations))
        state = loader.project_state([('home', '0175_master_market_delivery')])
        for model, fields in ((TbRecompensaMestre, ['efeito']),
                              (TbTransacaoMestre, ['operacao', 'recompensa', 'personagem',
                                                   'quantidade', 'detalhes_json']),
                              (TbPersonagemAventura, ['origem'])):
            migrated = state.apps.get_model('home', model.__name__)
            for field in fields:
                self.assertEqual(migrated._meta.get_field(field).deconstruct()[1:],
                                 model._meta.get_field(field).deconstruct()[1:])

    def test_history_displays_exact_destination_and_delivered_values(self):
        character = self.delivery_setup()
        self.deliver(character, '2', 'on')
        html = self.page_html(self.reward.pk, [character])
        self.assertIn('Personagem: Mesmo nome (#%s)' % character.pk, html)
        self.assertIn('2 aventura(s) · 24000 PC · 4 Braseiros · 2 Moeda(s) de Evento', html)


def bootstrap_isolated_schema():
    if (connection.vendor != 'sqlite' or connection.settings_dict['NAME'] != ':memory:'
            or 'bonfire.settings' in sys.modules or 'dotenv' in sys.modules):
        raise RuntimeError('Only in-memory SQLite without production settings/.env is allowed')
    from django.apps import apps
    with connection.schema_editor() as editor:
        for model in apps.get_models():
            if model._meta.managed and not model._meta.proxy:
                editor.create_model(model)


if ISOLATED:
    bootstrap_isolated_schema()
    if '--html-fixture' in sys.argv:
        import json

        fixture = MasterMarketQuantityTests()
        fixture.setUp()
        characters = None
        if '--delivery-fixture' in sys.argv:
            characters = [fixture.delivery_setup(), fixture.delivery_setup()]
        html = fixture.page_html(fixture.reward.pk, characters)
        html = html.replace('<link rel="stylesheet" href="/static/css/pages/master-market.css?v=6">',
                            '<style>' + (ROOT / 'home/static/css/pages/master-market.css').read_text() + '</style>')
        html = html.replace('<script defer src="/static/js/master-market.js?v=6"></script>', '')
        html = html.replace('</body>', '<script>' + (ROOT / 'home/static/js/master-market.js').read_text(
            encoding='utf-8') + '</script></body>')
        print(json.dumps({'html': html}))
    else:
        unittest.main(argv=[sys.argv[0]], verbosity=2)
