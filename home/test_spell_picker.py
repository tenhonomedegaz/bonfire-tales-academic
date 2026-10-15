"""Busca Q01 nos componentes reais de criação, avanço, preparação e oficina."""
import os
from pathlib import Path
import subprocess
import unittest

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.core.management import call_command
from django.db import connection
from django.urls import reverse

from home.models import TbClasse, TbClassehabilidade, TbMagia, TbPersonagem, TbPersonagemClasse, TbRecursoclasse, TbRegra


@unittest.skipUnless(os.environ.get('BONFIRE_PLAYWRIGHT_MODULE'), 'Configure Playwright para Q01.')
class SpellPickerBrowserTests(StaticLiveServerTestCase):
  def setUp(self):
    if connection.vendor != 'postgresql' or not connection.settings_dict['NAME'].startswith('test_'):
      self.skipTest('Requer PostgreSQL isolado test_.')
    # O criador real depende do catálogo canônico e da revisão publicada.
    TbRegra.objects.filter(slug='aumento-de-atributo').delete()
    call_command('loaddata', 'home/fixtures/conteudo.json', verbosity=0)
    self.user = get_user_model().objects.create_user(username='busca-q01')
    classe = TbClasse.objects.create(nome='Arquivista', slug='arquivista')
    TbClassehabilidade.objects.create(id_classe=classe, nome='Conjuração', niveladquirido=1,
      tags_json=['spellcasting{ability:int, slots{progression:full}, list:arquivista, '
        'mode:prepared, pool:spellbook, spell_limit{fixed:1}, acquire{initial:1, level_up:3}}'])
    TbRecursoclasse.objects.create(id_classe=classe,nome='1º',slug='1o',tipo='table-only',valores_json={'1':'2','2':'3'})
    self.character = TbPersonagem.objects.create(dono=self.user,nome='Buscador',nivel=1,aventuras=30)
    TbPersonagemClasse.objects.create(id_personagem=self.character,id_classe=classe,nivel=1,principal=True)
    for name, english, slug in [('Bênção','Bless','bencao'),('Proteção','Protection','protecao'),
        ('Fogo','Fire','fogo'),('Luz','Light','luz'),('Escudo','Shield','escudo')]:
      spell, _ = TbMagia.objects.update_or_create(slug=slug,defaults={
        'nome':name,'nome_ingles':english,'nivel':1,'escola':'Abjuração',
        'classes':'Arquivista','classes_slugs':['arquivista']})
      if slug in {'bencao', 'protecao', 'fogo'}:
        self.character.magias.create(id_magia=spell,nome=name,nivel=1,origem='Arquivista',preparada=(slug=='bencao'))
    cantrip = TbMagia.objects.create(nome='Faísca',nome_ingles='Spark',slug='faisca',nivel=0,
      escola='Evocação',classes='Arquivista',classes_slugs=['arquivista'])
    self.character.magias.create(id_magia=cantrip,nome=cantrip.nome,nivel=0,origem='Arquivista')
    self.client.force_login(self.user)

  def test_real_pages_search_preserves_choices_limits_and_context(self):
    root = Path(__file__).resolve().parent.parent
    env = dict(os.environ, PICKER_ORIGIN=self.live_server_url,
      PICKER_CREATION=reverse('criacao_ficha'),
      PICKER_LEVELUP=reverse('personagem_subir_nivel',args=[self.character.pk]),
      PICKER_SHEET=reverse('ficha_detail',args=[self.character.pk])+'?aba=magias',
      PICKER_WORKSHOP=reverse('oficina_magia')+'?personagem=%s'%self.character.pk,
      PICKER_COOKIE_NAME=settings.SESSION_COOKIE_NAME,
      PICKER_COOKIE_VALUE=self.client.cookies[settings.SESSION_COOKIE_NAME].value)
    # Este cenário testa busca de magias, sem a revisão selada do Caçador DEV.
    with self.settings(HUNTER_CREATOR_RULESET_CHECKSUM=''):
      result = subprocess.run(['node',str(root/'home/js_tests/spell_picker.e2e.cjs')],cwd=root,
        env=env,capture_output=True,encoding='utf-8',timeout=120)
    print(result.stdout)
    self.assertEqual(result.returncode,0,result.stdout+result.stderr)
    self.assertEqual(self.character.magias.filter(preparada=True).count(),1)
    self.assertEqual(TbPersonagem.objects.count(),1)
