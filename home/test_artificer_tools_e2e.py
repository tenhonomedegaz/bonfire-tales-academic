"""Q08: indicação e escolha de ferramenta no navegador real."""
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

from home.models import (TbClasse, TbItemMundano, TbPersonagem, TbPersonagemClasse,
  TbPersonagemProficiencia, TbPersonagemTalento, TbTalento)


@unittest.skipUnless(os.environ.get('BONFIRE_PLAYWRIGHT_MODULE'), 'Configure Playwright para Q08.')
class ArtificerToolsBrowserTests(StaticLiveServerTestCase):
  def test_known_tool_disabled_and_new_tool_persists(self):
    self.assertEqual(connection.vendor,'postgresql')
    self.assertTrue(connection.settings_dict['NAME'].startswith('test_'))
    user=get_user_model().objects.create_user(username='tools-browser')
    p=TbPersonagem.objects.create(dono=user,nome='Artesã',nivel=4)
    classe=TbClasse.objects.create(nome='Guerreiro',slug='guerreiro')
    TbPersonagemClasse.objects.create(id_personagem=p,id_classe=classe,nivel=4,principal=True)
    data=json.loads((Path(__file__).parent/'fixtures/conteudo.json').read_text(encoding='utf-8'))
    source=next(r['fields'] for r in data if r['model']=='home.tbtalento' and r['pk']==70)
    feat=TbTalento.objects.create(**source)
    TbPersonagemTalento.objects.create(id_personagem=p,id_talento=feat,nome=feat.nome,nivel=4)
    for slug,name,sub in [('ferreiro','Ferramentas de Ferreiro','ferramenta_artesao'),
        ('carpinteiro','Ferramentas de Carpinteiro','ferramenta_artesao'),('flauta','Flauta','instrumento')]:
      TbItemMundano.objects.create(slug=slug,nome=name,categoria='ferramenta',subcategoria=sub)
    TbPersonagemProficiencia.objects.create(id_personagem=p,tipo='ferramenta',
      nome='Ferramentas de Ferreiro',origem='antecedente')
    self.client.force_login(user)
    env=dict(os.environ, TOOLS_ORIGIN=self.live_server_url,
      TOOLS_PATH=reverse('personagem_subir_nivel',args=[p.pk]),
      TOOLS_COOKIE_NAME=settings.SESSION_COOKIE_NAME,
      TOOLS_COOKIE_VALUE=self.client.cookies[settings.SESSION_COOKIE_NAME].value)
    result=subprocess.run(['node',str(Path(__file__).parent/'js_tests/artificer_tools.e2e.cjs')],
      env=env,capture_output=True,encoding='utf-8',timeout=90)
    print(result.stdout)
    self.assertEqual(result.returncode,0,result.stdout+result.stderr)
    self.assertEqual(p.escolhas.filter(tipo='ferramenta',valor='carpinteiro').count(),1)
    self.assertEqual(p.proficiencias.filter(tipo='ferramenta').count(),2)
