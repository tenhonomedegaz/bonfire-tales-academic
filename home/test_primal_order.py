"""Q07: conteúdo Bonfire, escolha única e efeitos da Ordem Primal."""
from io import StringIO

from django.core.management import call_command
from django.urls import reverse
from django.test import SimpleTestCase

from home import picks, views
from home.character_engine import derive, magias_concedidas
from home.models import TbClasse, TbClassehabilidade, TbPersonagem, TbPersonagemClasse
from home.primal_order_repair import PRIMAL_TAGS, PrimalOrderConflict, repair_primal_order
from home.test_criador import _CriadorBase


class ConditionalGrantTests(SimpleTestCase):
  def test_outer_choice_preserves_nested_planar_spell_menu(self):
    from home.character_engine import _grants_de_tag
    tag = ('spell_selection:any{spell:pick{lista:cantrip, '
      'match(pick:energia){lumen:{chama_sagrada | luz}, umbra:{toque_gelido}}}}')
    catalog = {'chama-sagrada': 0, 'luz': 0, 'toque-gelido': 0}
    for source in (tag, 'match(pick:ordem){sim:{' + tag + '}, nao:{}}'):
      fixed, choice, _ = _grants_de_tag(source,
        {'energia': 'lumen', 'ordem': 'sim'}, catalog, 2)
      self.assertEqual(fixed, [])
      self.assertIsNotNone(choice)
      self.assertEqual(choice['opcoes'], ['chama-sagrada', 'luz'])
      self.assertEqual(choice['qtd'], 1)
    self.assertEqual(_grants_de_tag('match(pick:ordem){sim:{' + tag + '}, nao:{}}',
      {'energia': 'lumen', 'ordem': 'nao'}, catalog, 2), ([], None, []))


class PrimalOrderTests(_CriadorBase):
  def character(self, level=2, wisdom=18):
    p = TbPersonagem.objects.create(dono=self._novo_usuario('primal'), nome='Primal',
      nivel=level, inteligencia=12, sabedoria=wisdom)
    pc = TbPersonagemClasse.objects.create(id_personagem=p,
      id_classe=TbClasse.objects.get(slug='druida'), nivel=level, principal=True)
    self.client.force_login(p.dono)
    return p, pc

  def choose(self, p, pc, value):
    return views._lvl_aplicar_opcao(p, {'classe': pc.id_classe_id,
      'slug': 'ordem_primal', 'val': value})

  def test_empty_import_repair_preserves_identity_and_replays(self):
    feature = TbClassehabilidade.objects.get(pk=1180)
    self.assertEqual(feature.tags_json, PRIMAL_TAGS)
    feature.tags_json = []
    feature.save(update_fields=['tags_json'])
    p, pc = self.character()
    self.assertFalse(any(g['kind']=='ordem_primal' for g in picks.resolve_personagem(p)))
    output = StringIO()
    call_command('repair_primal_order', stdout=output)
    feature.refresh_from_db()
    self.assertEqual(feature.tags_json, [])
    self.assertEqual(len(repair_primal_order(apply=True)['changes']), 1)
    self.assertEqual(self.choose(p, pc, 'guardiao'), [])
    selected = list(p.escolhas.values())
    self.assertEqual(repair_primal_order(apply=True)['changes'], [])
    self.assertEqual(list(p.escolhas.values()), selected)
    feature.refresh_from_db()
    self.assertEqual(feature.pk, 1180)
    self.assertEqual(feature.niveladquirido, 2)

  def test_repair_refuses_editorial_changes(self):
    feature = TbClassehabilidade.objects.get(pk=1180)
    for changes in ({'tags_json': ['custom']}, {'niveladquirido': 1}, {'descricao': 'Revisada'}):
      original = {key: getattr(feature,key) for key in changes}
      for key,value in changes.items(): setattr(feature,key,value)
      feature.save(update_fields=list(changes))
      with self.assertRaises(PrimalOrderConflict): repair_primal_order(apply=True)
      feature.refresh_from_db()
      for key,value in changes.items(): self.assertEqual(getattr(feature,key),value)
      for key,value in original.items(): setattr(feature,key,value)
      feature.save(update_fields=list(original))

  def test_level_is_druid_level_and_both_choices_are_exclusive(self):
    p, pc = self.character(1)
    p.nivel=10
    p.save(update_fields=['nivel'])
    self.assertEqual(self.choose(p,pc,'xama'), [views._ERR_OPCAO_INVALIDA])
    pc.nivel=2
    pc.save(update_fields=['nivel'])
    group=next(g for g in picks.resolve_personagem(p) if g['kind']=='ordem_primal')
    self.assertEqual({o['slug'] for o in group['universo']}, {'xama','guardiao'})
    self.assertEqual(self.choose(p,pc,'guardiao'), [])
    self.assertEqual(self.choose(p,pc,'xama'), [views._ERR_OPCAO_INVALIDA])
    self.assertEqual(self.choose(p,pc,'guardiao'), [views._ERR_OPCAO_INVALIDA])
    self.assertEqual(p.escolhas.filter(tipo='ordem_primal').count(),1)

  def test_guardian_grants_proficiencies_without_shaman_effects(self):
    p, pc = self.character()
    self.assertEqual(self.choose(p,pc,'guardiao'), [])
    sheet=derive(p)
    self.assertIn('armas_marciais', sheet['proficiencias_arma'])
    self.assertIn('armadura_media', sheet['proficiencias_armadura'])
    self.assertFalse([r for r in magias_concedidas(p)['pendentes'] if r['fonte']=='Ordem Primal'])

  def test_shaman_two_wizard_cantrips_extra_and_wisdom_skills(self):
    p, pc = self.character()
    before=derive(p)
    pending_before=views._pendencias_magias(p,classe_id=pc.id_classe_id)
    self.assertEqual(self.choose(p,pc,'xama'), [])
    for wisdom, bonus in [(18,4),(8,1)]:
      p.sabedoria=wisdom
      p.save(update_fields=['sabedoria'])
      sheet=derive(p)
      for name in ['Arcanismo','Religião']:
        old=next(r for r in before['pericias'] if r['nome']==name)
        row=next(r for r in sheet['pericias'] if r['nome']==name)
        self.assertEqual(row['bonus'],old['bonus']+bonus)
    group=next(r for r in magias_concedidas(p)['pendentes'] if r['fonte']=='Ordem Primal')
    self.assertEqual(group['qtd'],2)
    from home.models import TbMagia
    for spell in TbMagia.objects.filter(slug__in=group['opcoes']):
      self.assertEqual(spell.nivel,0)
      self.assertIn('Mago',spell.classes)
    payload={'fonte':'Ordem Primal','slot':group['slot'],'magias':group['opcoes'][:1]}
    self.assertTrue(views._lvl_aplicar_magias_concedidas(p,payload))
    payload['magias']=group['opcoes'][:2]
    self.assertEqual(views._lvl_aplicar_magias_concedidas(p,payload), [])
    views._sync_magias_concedidas(p)
    views._sync_magias_concedidas(p)
    self.assertEqual(p.magias.filter(origem='Ordem Primal').count(),2)
    self.assertEqual(views._pendencias_magias(p,classe_id=pc.id_classe_id)['cantrips_pend'],
      pending_before['cantrips_pend'])
    pc.principal=False
    pc.save(update_fields=['principal'])
    TbPersonagemClasse.objects.create(id_personagem=p,
      id_classe=TbClasse.objects.get(slug='mago'),nivel=1,principal=True)
    info=views._magias_sheet_info(p,derive(p),[])
    granted=[row for group in info['grupos'] for row in group['magias']
             if row['slug'] in payload['magias'] and row['sempre_preparada']]
    self.assertEqual(len(granted),2)
    self.assertTrue(all(row['classe_id']==pc.id_classe_id for row in granted))
    self.assertTrue(all(row['origem']=='Druida' for row in granted))

  def test_page_and_batch_persist_choice_and_reject_repeat(self):
    p, pc = self.character()
    page=self.client.get(reverse('personagem_subir_nivel',args=[p.pk]))
    self.assertContains(page,'Ordem Primal')
    data={'acoes':[{'tipo':'opcao','payload':{'classe':pc.id_classe_id,
      'slug':'ordem_primal','val':'guardiao'}}]}
    url=reverse('personagem_levelup_aplicar',args=[p.pk])
    response=self.client.post(url,data,content_type='application/json')
    self.assertEqual(response.status_code,200,response.content)
    self.assertEqual(self.client.post(url,data,content_type='application/json').status_code,400)
    self.assertEqual(p.escolhas.filter(tipo='ordem_primal',valor='guardiao').count(),1)
