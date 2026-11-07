"""Q07 no navegador: duas alternativas, persistência e concessões extras."""
import json
import os
from pathlib import Path
import subprocess
import unittest

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.db import connection
from django.urls import reverse

from home.models import TbClasse, TbClassehabilidade, TbMagia, TbPersonagem, TbPersonagemClasse
from home.character_engine import derive


@unittest.skipUnless(os.environ.get('BONFIRE_PLAYWRIGHT_MODULE'), 'Configure Playwright para Q07.')
class PrimalOrderBrowserTests(StaticLiveServerTestCase):
  def test_choose_reload_and_complete_shaman_spells(self):
    self.assertEqual(connection.vendor, 'postgresql')
    self.assertTrue(connection.settings_dict['NAME'].startswith('test_'))
    user = get_user_model().objects.create_user(username='primal-browser')
    druid = TbClasse.objects.create(nome='Druida', slug='druida')
    TbClasse.objects.create(nome='Mago', slug='mago')
    fixture = json.loads((Path(__file__).parent/'fixtures/conteudo.json').read_text(encoding='utf-8'))
    fields = next(r['fields'] for r in fixture if r['model']=='home.tbclassehabilidade' and r['pk']==1180)
    TbClassehabilidade.objects.create(id_classe=druid, **{key: fields[key]
      for key in ('nome', 'descricao', 'tags_json', 'niveladquirido', 'table_only')})
    for slug, name in [('luz','Luz'), ('raio-de-fogo','Raio de Fogo'), ('maos-magicas','Mãos Mágicas')]:
      TbMagia.objects.create(nome=name, slug=slug, nivel=0, escola='Evocação',
        classes='Mago', classes_slugs=['mago'])
    characters = {}
    for choice in ('guardiao', 'xama'):
      p = TbPersonagem.objects.create(dono=user,nome=choice,nivel=2,sabedoria=18)
      TbPersonagemClasse.objects.create(id_personagem=p,id_classe=druid,nivel=2,principal=True)
      characters[choice] = p
    self.client.force_login(user)
    env = dict(os.environ, PRIMAL_ORIGIN=self.live_server_url,
      PRIMAL_PATHS=json.dumps({key:reverse('personagem_subir_nivel',args=[p.pk])
        for key,p in characters.items()}),
      PRIMAL_COOKIE_NAME=settings.SESSION_COOKIE_NAME,
      PRIMAL_COOKIE_VALUE=self.client.cookies[settings.SESSION_COOKIE_NAME].value)
    result = subprocess.run(['node',str(Path(__file__).parent/'js_tests/primal_order.e2e.cjs')],
      env=env,capture_output=True,encoding='utf-8',timeout=100)
    print(result.stdout)
    self.assertEqual(result.returncode,0,result.stdout+result.stderr)
    for choice,p in characters.items():
      self.assertEqual(p.escolhas.filter(tipo='ordem_primal',valor=choice).count(),1)
    self.assertIn('armas_marciais',derive(characters['guardiao'])['proficiencias_arma'])
    self.assertEqual(characters['xama'].magias.filter(origem='Ordem Primal').count(),2)
