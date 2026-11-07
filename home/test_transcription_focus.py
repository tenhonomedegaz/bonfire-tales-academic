"""Q03: subclasse, foco e cobrança de transcrição têm identidades distintas."""
from django.test import TestCase
from django.urls import reverse

from home.magic_workshop import character_casters, transcription_terms_for_character
from home.models import TbOpcaojogo, TbPersonagemEscolha, TbSubclasse, TbSolicitacaoTranscricao


class TranscriptionFocusTests(TestCase):
  def setUp(self):
    from home.test_magic_workshop import MagicWorkshopTests
    MagicWorkshopTests.setUp(self)
    self.subclass = TbSubclasse.objects.create(
      id_classe=self.classe, nome='Mago da Guerra', slug='mago-da-guerra')
    self.pc = self.personagem.classes.get()
    self.pc.id_subclasse = self.subclass
    self.pc.save(update_fields=['id_subclasse'])
    self.spell.escola = 'Abjuração'
    self.spell.save(update_fields=['escola'])
    option = TbOpcaojogo.objects.create(nome='Abjuração', slug='abjuracao', tipo='Escola de Foco')
    self.focus = TbPersonagemEscolha.objects.create(
      id_personagem=self.personagem, origem='Escolas de Foco', tipo='escola_de_foco',
      slot=0, id_opcao=option, valor=option.nome)
    self.client.force_login(self.user)

  def terms(self):
    return transcription_terms_for_character(
      self.personagem, character_casters(self.personagem)[0], self.spell)

  def test_quote_separates_base_focus_and_subclass(self):
    terms = self.terms()
    self.assertEqual((terms['base_cost_po'], terms['cost_po']), (50, 25))
    self.assertEqual((terms['base_time_hours'], terms['time_hours']), (2, 1))
    self.assertEqual(terms['focus_school'], 'Abjuração')
    self.assertEqual(terms['discount_percent'], 50)
    self.pc.refresh_from_db()
    self.assertEqual(self.pc.id_subclasse_id, self.subclass.pk)

  def test_unrelated_school_and_legacy_typed_focus(self):
    self.focus.id_opcao = None
    self.focus.valor = 'Abjuração'
    self.focus.save(update_fields=['id_opcao', 'valor'])
    self.assertEqual(self.terms()['cost_po'], 25)
    self.focus.tipo = 'subclasse'
    self.focus.save(update_fields=['tipo'])
    terms = self.terms()
    self.assertEqual(terms['cost_po'], 50)
    self.assertEqual(terms['discount_percent'], 0)
    self.assertEqual(terms['focus_school'], '')

  def test_scroll_preview_and_charge_have_the_same_breakdown(self):
    item = self.personagem.inventario.create(nome='Pergaminho', qtd=1,
      tags_json=['spell_scroll{spell:fogo_de_teste, level:1}', 'consumable'])
    response = self.client.get(reverse('oficina_magia'), {'personagem': self.personagem.pk})
    quote = response.context['transcricoes'][0]['terms']
    self.assertEqual(quote['cost_po'], 25)
    self.assertContains(response, 'Base: 50 PO')
    self.assertContains(response, 'Escola de Foco: Abjuração')
    endpoint = reverse('personagem_transcrever_magia', args=[self.personagem.pk])
    payload = {'classe': self.classe.pk, 'item': item.pk, 'next': 'oficina'}
    self.assertIn('status=ok', self.client.post(endpoint, payload)['Location'])
    self.personagem.refresh_from_db()
    self.assertEqual(self.personagem.carteira_pc, 7500)
    self.assertEqual(self.personagem.transacoes.get().detalhes_json['transcription_terms'], quote)
    self.client.post(endpoint, payload)
    self.assertEqual(self.personagem.transacoes.count(), 1)
    self.pc.refresh_from_db()
    self.assertEqual(self.pc.id_subclasse_id, self.subclass.pk)

  def source(self):
    from django.contrib.auth.models import User
    from home.models import TbPersonagem, TbPersonagemClasse
    owner = User.objects.create_user(username='fonte-q03')
    source = TbPersonagem.objects.create(dono=owner, nome='Outro grimório', nivel=3)
    TbPersonagemClasse.objects.create(id_personagem=source, id_classe=self.classe, nivel=3)
    source.magias.create(id_magia=self.spell, nome=self.spell.nome, nivel=1, origem=self.classe.nome)
    return source, owner

  def test_book_preview_request_and_authorization_preserve_subclass(self):
    source, owner = self.source()
    response = self.client.get(reverse('oficina_magia'), {'personagem': self.personagem.pk})
    quote = response.context['grimorios_disponiveis'][0]['spells'][0]['terms']
    payload = {'personagem': self.personagem.pk, 'fonte': source.pk,
      'magia': self.spell.pk, 'classe': self.classe.pk}
    endpoint = reverse('oficina_solicitar_transcricao', args=[self.personagem.pk])
    self.client.post(endpoint, payload)
    self.client.post(endpoint, payload)
    row = TbSolicitacaoTranscricao.objects.get()
    self.assertEqual(row.detalhes_json['transcription_terms'], quote)
    self.client.force_login(owner)
    response = self.client.post(reverse('oficina_responder_transcricao', args=[row.pk]),
      {'personagem': source.pk, 'acao': 'aceitar'})
    self.assertIn('status=aceita', response['Location'])
    self.personagem.refresh_from_db()
    self.assertEqual(self.personagem.carteira_pc, 7500)
    self.assertEqual(self.personagem.transacoes.get().detalhes_json['transcription_terms'], quote)
    self.pc.refresh_from_db()
    self.assertEqual(self.pc.id_subclasse_id, self.subclass.pk)

  def test_authorization_records_current_focus_when_request_became_stale(self):
    source, owner = self.source()
    self.client.post(reverse('oficina_solicitar_transcricao', args=[self.personagem.pk]),
      {'personagem': self.personagem.pk, 'fonte': source.pk,
       'magia': self.spell.pk, 'classe': self.classe.pk})
    row = TbSolicitacaoTranscricao.objects.get()
    self.focus.valor = 'Evocação'
    self.focus.id_opcao = None
    self.focus.save(update_fields=['id_opcao', 'valor'])
    self.client.force_login(owner)
    self.client.post(reverse('oficina_responder_transcricao', args=[row.pk]),
      {'personagem': source.pk, 'acao': 'aceitar'})
    row.refresh_from_db()
    self.assertEqual(row.custo_po, 50)
    self.assertFalse(row.detalhes_json['desconto_escola_foco'])
    self.assertEqual(row.detalhes_json['transcription_terms']['discount_percent'], 0)
