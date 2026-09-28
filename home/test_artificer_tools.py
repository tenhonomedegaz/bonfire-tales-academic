"""Q08: ferramentas elegíveis, proficiências prévias e persistência."""
from types import SimpleNamespace

from django.urls import reverse

from home import picks, views
from home.models import (TbClasse, TbItemMundano, TbPersonagem, TbPersonagemClasse,
  TbPersonagemProficiencia, TbPersonagemTalento, TbTalento)
from home.test_criador import _CriadorBase


class ArtificerToolTests(_CriadorBase):
  def setUp(self):
    self.p = TbPersonagem.objects.create(dono=self._novo_usuario('tools'),nome='Tools',nivel=4)
    self.feat = TbTalento.objects.get(slug='iniciado-artifice')
    TbPersonagemTalento.objects.create(id_personagem=self.p,id_talento=self.feat,
      nome=self.feat.nome,categoria='geral',nivel=4)
    self.artisans = list(TbItemMundano.objects.filter(categoria='ferramenta',
      subcategoria='ferramenta_artesao').order_by('nome'))
    self.known = self.artisans[0]
    TbPersonagemProficiencia.objects.create(id_personagem=self.p,tipo='ferramenta',
      nome=self.known.nome,origem='antecedente')
    self.client.force_login(self.p.dono)

  def group(self):
    return next(g for g in picks.resolve_personagem(self.p,kinds={'ferramenta'})
      if g['origem']==self.feat.nome)

  def test_artisan_pool_marks_known_and_excludes_other_categories(self):
    group=self.group()
    self.assertEqual({o['slug'] for o in group['universo']},{i.slug for i in self.artisans})
    option=next(o for o in group['universo'] if o['slug']==self.known.slug)
    self.assertTrue(option['ja_proficiente'])
    self.assertTrue(picks.registry_entry('ferramenta')['validate'](group,[self.known.slug]))
    self.assertEqual(picks.registry_entry('ferramenta')['validate'](group,[self.artisans[1].slug]),[])
    self.assertTrue(picks.registry_entry('ferramenta')['validate'](dict(group,n=2),
      [self.artisans[1].slug,str(self.artisans[1].pk)]))
    nested=views._talento_picks_contexto(self.feat,self.p)
    tool=next(g for g in nested if g['label']=='Ferramenta')
    self.assertTrue(next(o for o in tool['options'] if o['val']==str(self.known.pk))['ja_proficiente'])

  def test_levelup_rejects_owned_and_nonartisan_then_persists_once(self):
    payload={'slug':'ferramenta','classe':'','val':str(self.known.pk)}
    self.assertEqual(views._lvl_aplicar_opcao(self.p,payload),[views._ERR_OPCAO_INVALIDA])
    other=TbItemMundano.objects.filter(categoria='ferramenta',subcategoria='instrumento').first()
    payload['val']=other.slug
    self.assertEqual(views._lvl_aplicar_opcao(self.p,payload),[views._ERR_OPCAO_INVALIDA])
    self.assertEqual(self.p.escolhas.filter(tipo='ferramenta').count(),0)
    payload['val']=self.artisans[1].slug
    self.assertEqual(views._lvl_aplicar_opcao(self.p,payload),[])
    self.assertEqual(views._lvl_aplicar_opcao(self.p,payload),[views._ERR_OPCAO_INVALIDA])
    self.assertEqual(self.p.escolhas.filter(tipo='ferramenta').count(),1)
    self.assertEqual(self.p.proficiencias.filter(tipo='ferramenta').count(),2)

  def test_class_and_tag_grants_also_block_duplicates(self):
    classe=TbClasse.objects.create(nome='Tools class',slug='tools-class',
      tags_json=['proficiencias{ferramentas_de_funileiro}'])
    TbPersonagemClasse.objects.create(id_personagem=self.p,id_classe=classe,nivel=4,principal=True)
    # A fonte ativa concede a proficiência sem linha manual de personagem.
    from home.models import TbClassehabilidade
    TbClassehabilidade.objects.create(id_classe=classe,nome='Tool grant',niveladquirido=1,
      tags_json=['prof:tool{%s}'%self.artisans[1].slug.replace('-','_')])
    group=self.group()
    self.assertTrue(next(o for o in group['universo'] if o['slug']==self.artisans[1].slug)['ja_proficiente'])

  def test_page_marks_disabled_and_post_rejects_stale_choice(self):
    url=reverse('personagem_subir_nivel',args=[self.p.pk])
    page=self.client.get(url)
    self.assertContains(page,'já proficiente')
    self.assertContains(page,'value="%s" data-desc='%self.known.pk)
    payload={'acoes':[{'tipo':'opcao','payload':{'classe':'','slug':'ferramenta',
      'val':self.known.slug}}]}
    response=self.client.post(reverse('personagem_levelup_aplicar',args=[self.p.pk]),
      payload,content_type='application/json')
    self.assertEqual(response.status_code,400)
    self.assertEqual(self.p.escolhas.filter(tipo='ferramenta').count(),0)

  def test_all_known_keeps_pending_without_inventing_substitution(self):
    for item in self.artisans[1:]:
      TbPersonagemProficiencia.objects.create(id_personagem=self.p,tipo='ferramenta',
        nome=item.nome,origem='Treinamento')
    group=self.group()
    self.assertEqual(group['pendentes'],1)
    self.assertTrue(all(o['ja_proficiente'] for o in group['universo']))
    instrument=SimpleNamespace(nome='Instrumento',tags_json=['pick:ferramenta:instrumento:1'])
    group=picks.resolve_groups([instrument],personagem=self.p)[0]
    self.assertTrue(all(not o['ja_proficiente'] for o in group['universo']))

  def test_laboratory_blocks_owned_but_preserves_editable_selected_tool(self):
    from home.pathbuilder import _apply_choices, _groups_with_keys, _choice_groups, PathbuilderError
    group=next(g for g in _groups_with_keys(self.p) if g['kind']=='ferramenta')
    key=group['pathbuilder_key']
    with self.assertRaises(PathbuilderError):
      _apply_choices(self.p,{'escolhas':{key:[self.known.slug]}})
    selected=self.artisans[1].slug
    build={'escolhas':{key:[selected]}}
    _apply_choices(self.p,build)
    _apply_choices(self.p,build)
    self.assertEqual(self.p.escolhas.filter(tipo='ferramenta').count(),1)
    projected=next(g for g in _choice_groups(self.p,build) if g['key']==key)
    self.assertEqual(projected['selecionadas'],[selected])
    self.assertTrue(next(o for o in projected['opcoes'] if o['valor']==self.known.slug)['ja_proficiente'])
