from copy import deepcopy
from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.test import TestCase

from .content_versions import create_revision, seal_ruleset
from .models import TbClasse, TbItemMundano, TbPersonagem
from .starting_equipment import resolve_starting_equipment, starting_equipment_for_class
from .versioned_classes import EVALUATOR, VOCABULARY, inventory_class
from .versioned_items import snapshot_mundane_items
from .test_criador import _CriadorBase
from . import views


def seal_equipment(classe):
    return seal_ruleset([
        create_revision('class-catalog:%s' % classe.pk, inventory_class(classe.pk)),
        snapshot_mundane_items(),
    ], evaluator_version=EVALUATOR, vocabulary_version=VOCABULARY)


class FrozenEquipmentTests(TestCase):
    def setUp(self):
        self.weapon = TbItemMundano.objects.create(nome='Frozen sword', slug='frozen-sword',
            categoria='arma', subcategoria='arma_simples', preco=Decimal('2.50'),
            peso=Decimal('1.25'), tags_json=['damage:1d6'])
        self.classe = TbClasse.objects.create(nome='Caçador', slug='cacador', tags_json=[
            'starting_equipment{item{slug:frozen-sword,qty:2},'
            'pick{count:1,option{category:arma,subcategory_prefix:arma_simples}},'
            'currency{po:3},alternative{currency{po:50}}}'])
        self.ruleset = seal_equipment(self.classe)
        self.selection = {'equipment_pick_1': ['frozen-sword']}

    def test_frozen_choices_items_and_gold_ignore_live_mutation(self):
        expected, errors = resolve_starting_equipment(self.classe, 'inicial', self.selection, ruleset=self.ruleset)
        self.assertEqual(errors, [])
        self.assertEqual(expected['items'][0]['qty'], 3)
        self.assertEqual(expected['items'][0]['custo'], '2.50')
        self.weapon.nome = 'Changed'; self.weapon.preco = 99
        self.weapon.tags_json = ['damage:99d6']; self.weapon.save()
        self.classe.tags_json = []; self.classe.save()
        newcomer = TbItemMundano.objects.create(nome='Live only', slug='live-only', categoria='arma', subcategoria='arma_simples')
        actual, errors = resolve_starting_equipment(self.classe, 'inicial', self.selection, ruleset=self.ruleset)
        self.assertEqual((actual, errors), (expected, []))
        _, errors = resolve_starting_equipment(self.classe, 'inicial', {'equipment_pick_1':[newcomer.slug]}, ruleset=self.ruleset)
        self.assertTrue(errors)
        gold, errors = resolve_starting_equipment(self.classe, 'ouro', ruleset=self.ruleset)
        self.assertEqual((gold['items'], gold['currency_po'], errors), ([], 50, []))
        self.assertIsNone(starting_equipment_for_class(self.classe))

    def test_missing_revision_and_incomplete_bundle_are_not_silently_accepted(self):
        incomplete = seal_ruleset([create_revision('class-catalog:%s' % self.classe.pk,
            inventory_class(self.classe.pk))], evaluator_version=EVALUATOR, vocabulary_version=VOCABULARY)
        with self.assertRaises(ObjectDoesNotExist):
            starting_equipment_for_class(self.classe, ruleset=incomplete)
        self.classe.tags_json = ['starting_equipment{pick{count:1,option{key:bundle,item{slug:frozen-sword},item{slug:absent}}}}']
        self.classe.save()
        _, errors = resolve_starting_equipment(self.classe, 'inicial', {'equipment_pick_1':['bundle']})
        self.assertTrue(errors)


class CreatorEquipmentSnapshotTests(_CriadorBase):
    def test_endpoint_persists_validated_possessions_after_catalog_change(self):
        user = self._novo_usuario('equipment-snapshot', staff=True)
        payload = self._payload('guerreiro', equip_classe='inicial')
        resolved, errors = views._criador_resolver(payload)
        self.assertEqual(errors, [])
        expected = deepcopy(resolved['equipment_plan']['items'])
        original = views._criador_resolver
        def change_after_validation(data):
            result, errors = original(data)
            for row in result['equipment_plan']['items']:
                TbItemMundano.objects.filter(pk=row['id']).update(
                    nome='Changed item', preco=999, peso=99, tags_json=['damage:99d6'])
            return result, errors
        with patch('home.views._criador_resolver', side_effect=change_after_validation):
            response = self._post_criar(user, payload)
        self.assertEqual(response.status_code, 200, response.content)
        person = TbPersonagem.objects.get(pk=response.json()['id'])
        self.assertEqual(person.inventario.count(), len(expected))
        for row in expected:
            item = person.inventario.get(id_item_mundano_id=row['id'])
            self.assertEqual((item.nome, item.qtd, item.tags_json, item.equipado),
                (row['nome'], row['qty'], row['tags_json'], row['categoria']=='armadura'))
            self.assertEqual(item.custo, row['custo'])
            self.assertEqual(item.peso, row['peso'])

    def test_frozen_equipment_plan_reaches_creator_inventory(self):
        user = self._novo_usuario('frozen-creator', staff=True)
        payload = self._payload('guerreiro', equip_classe='inicial')
        resolved, errors = views._criador_resolver(payload)
        self.assertEqual(errors, [])
        ruleset = seal_equipment(resolved['classe'])
        plan, errors = resolve_starting_equipment(resolved['classe'], 'inicial',
            payload.get('equip_choices'), ruleset=ruleset)
        self.assertEqual(errors, [])
        resolved['equipment_plan'] = plan
        for row in plan['items']:
            TbItemMundano.objects.filter(pk=row['id']).update(nome='Live changed', preco=999)
        with transaction.atomic():
            person = views._criador_persistir(user, payload, resolved, strict_spell_choices=True)
        self.assertEqual(set(person.inventario.values_list('nome',flat=True)), {row['nome'] for row in plan['items']})

    def test_missing_item_identity_rolls_back_entire_creation(self):
        user = self._novo_usuario('equipment-missing', staff=True)
        payload = self._payload('guerreiro', equip_classe='inicial')
        original = views._criador_resolver
        def missing_identity(data):
            result, errors = original(data)
            # Mimic a catalog identity removed after server validation.
            result['equipment_plan']['items'][0]['id'] = 2147483647
            return result, errors
        with patch('home.views._criador_resolver', side_effect=missing_identity):
            response = self._post_criar(user, payload)
        self.assertEqual(response.status_code, 400, response.content)
        self.assertFalse(TbPersonagem.objects.filter(dono=user).exists())
