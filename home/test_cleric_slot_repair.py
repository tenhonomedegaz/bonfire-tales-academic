"""Q04: progressão Bonfire, reparo repetível e consumo sem repor gastos."""
import json
from io import StringIO
from pathlib import Path
import uuid
import os
import subprocess
import unittest

from django.contrib.auth import get_user_model
from django.conf import settings
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.db import connection
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from home.cleric_slot_repair import LEGACY_TABLES, SlotRepairConflict, repair_cleric_slots
from home.models import TbClasse, TbClassehabilidade, TbPersonagem, TbPersonagemClasse, TbRecursoclasse, TbSubclasse
from home.resource_engine import ensure_resource
from home.spellcasting import slot_table_at
from home.views import _spell_slot_rows, _spell_slot_totals


# Tabela importada Bonfire, com apenas a errata Q04 (5º em 18+) aplicada.
# O 2º círculo no nível 5 permanece 4 até haver errata editorial própria.
EXPECTED = [
  [2,0,0,0,0,0,0,0,0], [3,0,0,0,0,0,0,0,0],
  [4,2,0,0,0,0,0,0,0], [4,3,0,0,0,0,0,0,0],
  [4,4,2,0,0,0,0,0,0], [4,3,3,0,0,0,0,0,0],
  [4,3,3,1,0,0,0,0,0], [4,3,3,2,0,0,0,0,0],
  [4,3,3,3,1,0,0,0,0], [4,3,3,3,2,0,0,0,0],
  [4,3,3,3,2,1,0,0,0], [4,3,3,3,2,1,0,0,0],
  [4,3,3,3,2,1,1,0,0], [4,3,3,3,2,1,1,0,0],
  [4,3,3,3,2,1,1,1,0], [4,3,3,3,2,1,1,1,0],
  [4,3,3,3,2,1,1,1,1], [4,3,3,3,3,1,1,1,1],
  [4,3,3,3,3,2,1,1,1], [4,3,3,3,3,2,2,1,1],
]


class ClericSlotRepairTests(TestCase):
  def setUp(self):
    self.classe = TbClasse.objects.create(nome='Clérigo', slug='clerigo')
    TbClassehabilidade.objects.create(id_classe=self.classe, nome='Conjuração', niveladquirido=1,
      tags_json=['spellcasting{ability:wis, slots{progression:full}, list:clerigo, mode:prepared}'])
    self.resources = {}
    for circle, table in LEGACY_TABLES.items():
      self.resources[circle] = TbRecursoclasse.objects.create(id_classe=self.classe,
        nome='%s°' % circle, slug=str(circle), valores_json=table, tipo='table-only')
    self.user = get_user_model().objects.create_user(username='clerigo-q04')
    self.character = TbPersonagem.objects.create(dono=self.user, nome='Clérigo Q04', nivel=18)
    self.pc = TbPersonagemClasse.objects.create(id_personagem=self.character,
      id_classe=self.classe, nivel=18, principal=True)
    self.client.force_login(self.user)

  def test_preview_apply_and_replay_preserve_ids_and_user_data(self):
    before = list(TbRecursoclasse.objects.order_by('pk').values())
    spent = ensure_resource(self.character, {'key':'spell-slot:5','name':'spell-slot:5',
      'maximum':2, 'initial':1, 'reset':'long_rest'})
    spent.atual = 1
    spent.save(update_fields=['atual'])
    subclass = TbSubclasse.objects.create(id_classe=self.classe, nome='Domínio', slug='dominio')
    separate = TbRecursoclasse.objects.create(id_classe=self.classe, id_subclasse=subclass,
      nome='Reserva', slug='5', valores_json={'18':'7'}, tipo='table-only')
    output = StringIO()
    call_command('repair_cleric_slots', stdout=output)
    self.assertEqual(len(json.loads(output.getvalue())['changes']), 9)
    self.assertEqual(list(TbRecursoclasse.objects.filter(id_subclasse=None).order_by('pk').values()), before)
    repair_cleric_slots(apply=True)
    self.assertEqual(repair_cleric_slots(apply=True)['changes'], [])
    self.assertEqual(list(TbRecursoclasse.objects.filter(id_subclasse=None).order_by('pk').values_list('pk', flat=True)),
      [r['id_recurso'] for r in before])
    spent.refresh_from_db()
    self.assertEqual((spent.atual,spent.maximo),(1,2))
    separate.refresh_from_db()
    self.assertEqual((separate.slug,separate.valores_json),('5',{'18':'7'}))

  def test_full_progression_matches_fixture_and_character_class_level(self):
    repair_cleric_slots(apply=True)
    for level, expected in enumerate(EXPECTED, 1):
      with self.subTest(level=level):
        self.pc.nivel = level
        totals = _spell_slot_totals([{'pc': self.pc,'info':{'slots':'full'}}])
        self.assertEqual([totals.get(i,0) for i in range(1,10)],expected)
    fixture = json.loads((Path(__file__).parent/'fixtures/conteudo.json').read_text(encoding='utf-8'))
    resources = {r['fields']['slug']:r['fields'] for r in fixture
      if r['model']=='home.tbrecursoclasse' and r['fields']['id_classe']==5
      and not r['fields']['id_subclasse']}
    for circle, obj in self.resources.items():
      obj.refresh_from_db()
      self.assertEqual(resources[str(circle)]['valores_json'], obj.valores_json)

  def test_unknown_table_or_duplicate_aborts_entire_batch(self):
    for duplicate in [False,True]:
      with self.subTest(duplicate=duplicate):
        if duplicate:
          self.resources[9].valores_json = LEGACY_TABLES[9]
          self.resources[9].save(update_fields=['valores_json'])
          TbRecursoclasse.objects.create(id_classe=self.classe, nome='Duplicado',slug='9o',
            valores_json=LEGACY_TABLES[9],tipo='table-only')
        else:
          self.resources[9].valores_json = {'17':'7'}
          self.resources[9].save(update_fields=['valores_json'])
        before = list(TbRecursoclasse.objects.values())
        with self.assertRaises(SlotRepairConflict):
          repair_cleric_slots(apply=True)
        self.assertEqual(list(TbRecursoclasse.objects.values()),before)

  def test_sheet_and_consumption_at_18_19_20_preserve_spent_slots(self):
    repair_cleric_slots(apply=True)
    resource = ensure_resource(self.character, {'key':'spell-slot:5','name':'spell-slot:5',
      'maximum':2,'reset':'long_rest'})
    url = reverse('personagem_usar_slot_magia',args=[self.character.pk])
    for level in (18,19,20):
      with self.subTest(level=level):
        self.pc.nivel = level
        self.pc.save(update_fields=['nivel'])
        resource.atual,resource.maximo = 1,2
        resource.save(update_fields=['atual','maximo'])
        page = self.client.get(reverse('ficha_detail',args=[self.character.pk])+'?aba=magias')
        self.assertEqual(page.status_code,200)
        slot = next(s for s in page.context['magias_info']['slots'] if s['nivel']==5)
        self.assertEqual((slot['atual'],slot['total']),(2,3))
        resource.refresh_from_db()
        self.assertEqual((resource.atual,resource.maximo),(1,2),'leitura não sincroniza gastos')
        for remaining in (1,0):
          response = self.client.post(url,{'nivel':5,'acao':'gastar','operation_id':str(uuid.uuid4()),
            'expected_version':slot['version']},HTTP_ACCEPT='application/json')
          self.assertEqual(response.status_code,200,response.content)
          slot = response.json()['slot']
          self.assertEqual((slot['atual'],slot['total']),(remaining,3))
        exhausted = self.client.post(url,{'nivel':5,'acao':'gastar','operation_id':str(uuid.uuid4()),
          'expected_version':slot['version']},HTTP_ACCEPT='application/json')
        self.assertEqual(exhausted.status_code,409)
        self.assertEqual(_spell_slot_rows(self.character,{5:3})[4]['atual'],0)


@unittest.skipUnless(os.environ.get('BONFIRE_PLAYWRIGHT_MODULE'), 'Configure Playwright para E2E.')
class ClericSlotsBrowserTests(StaticLiveServerTestCase):
  def setUp(self):
    if connection.vendor != 'postgresql' or not connection.settings_dict['NAME'].startswith('test_'):
      self.skipTest('Requer PostgreSQL isolado test_.')
    ClericSlotRepairTests.setUp(self)
    repair_cleric_slots(apply=True)

  def test_fifth_circle_three_charges_and_reload(self):
    env = dict(os.environ,
      Q04_ORIGIN=self.live_server_url,
      Q04_PATH=reverse('ficha_detail',args=[self.character.pk])+'?aba=magias',
      Q04_COOKIE_NAME=settings.SESSION_COOKIE_NAME,
      Q04_COOKIE_VALUE=self.client.cookies[settings.SESSION_COOKIE_NAME].value)
    script = Path(__file__).parent/'js_tests/cleric_slots.e2e.cjs'
    result = subprocess.run(['node',str(script)],env=env,capture_output=True,
      encoding='utf-8',timeout=90)
    print(result.stdout)
    self.assertEqual(result.returncode,0,result.stdout+result.stderr)
    stored = self.character.recursos.get(chave='spell_slot:5')
    self.assertEqual((stored.atual,stored.maximo),(0,3))
