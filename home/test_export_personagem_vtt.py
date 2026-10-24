# -*- coding: utf-8 -*-
"""Regressão do export de personagem para o VTT (export_personagem_vtt).

Cobre o contrato v1 (doutrina: saída CRUA do derive + PKs; mapeamento de ids fica
no compilador do VTT):
  - forma do JSON (blocos personagem/derive/recursos/habilidades/magias/estado_mesa);
  - determinismo (dois exports do mesmo dado são byte-idênticos);
  - totais MULTICLASSE de espaços de magia (mesma conta de views._spell_slot_totals);
  - dados de vida por classe e recurso consumível com PK de TbRecursoclasse;
  - magias concedidas (sempre_preparada) saem com origem='concedida'.

E a evolução ADITIVA v1.1 (versao_contrato continua 1; versao_menor=1):
  - derive.salvaguardas: 6 entradas em ordem canônica, a MESMA conta da ficha
    (character_engine._saves — proficiência via saves_prof{} da classe principal);
  - derive.pericias: as 18 canônicas SEMPRE saem, cada uma com o atributo base;
  - derive.idiomas: proficiências tipo='idioma' do personagem.

Conteúdo SINTÉTICO mínimo (sem fixture pesada): duas classes full-caster com a
tabela de slots em TbRecursoclasse — suficiente para exercitar o caminho real.
"""
from django.contrib.auth.models import User
from django.test import TestCase

from home.character_engine import _SKILL_INFO
from home.management.commands.export_personagem_vtt import (
    exportar_personagem, serializar)
from home.models import (
    TbClasse, TbClassehabilidade, TbMagia, TbPersonagem, TbPersonagemClasse,
    TbPersonagemMagia, TbPersonagemProficiencia, TbPersonagemRecurso, TbRecursoclasse,
)


class ExportPersonagemVttTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username='vtt-tester', password='x')

        # duas classes conjuradoras FULL (o multiclasse soma níveis e lê a tabela
        # do primeiro full-caster — views._spell_slot_totals/_full_caster_slot_source).
        # O mago (classe PRINCIPAL) declara saves_prof — a regra da ficha só lê a
        # tag da principal (character_engine._saves), então é o mago quem manda.
        cls.mago = TbClasse.objects.create(
            nome='Mago Teste', slug='mago-teste-vtt', dado_vida='d6',
            tags_json=['saves_prof{int, wis}',
                       'spellcasting{ability:int, lista:mago-teste-vtt, '
                       'prepara:preparadas, slots:full}'])
        cls.clerigo = TbClasse.objects.create(
            nome='Clérigo Teste', slug='clerigo-teste-vtt', dado_vida='d8',
            tags_json=['spellcasting{ability:wis, lista:clerigo-teste-vtt, '
                       'prepara:preparadas, slots:full}'])

        # tabela de slots do mago (table-only 1o..3o) — nível efetivo 5 ⇒ 4/3/2
        TbRecursoclasse.objects.create(
            id_classe=cls.mago, nome='Espaços de 1º Círculo', slug='1o',
            tipo='table-only', valores_json={'1': '2', '3': '4', '5': '4'})
        TbRecursoclasse.objects.create(
            id_classe=cls.mago, nome='Espaços de 2º Círculo', slug='2o',
            tipo='table-only', valores_json={'3': '2', '5': '3'})
        TbRecursoclasse.objects.create(
            id_classe=cls.mago, nome='Espaços de 3º Círculo', slug='3o',
            tipo='table-only', valores_json={'5': '2'})
        # consumível de classe com PK exportável
        cls.canalizar = TbRecursoclasse.objects.create(
            id_classe=cls.clerigo, nome='Canalizar Divindade Teste',
            slug='canalizar-divindade-teste', tipo='consumable',
            reset='short-or-long', valores_json={'1': '1', '6': '2'})

        cls.hab_mago = TbClassehabilidade.objects.create(
            id_classe=cls.mago, nome='Recuperação Arcana Teste',
            descricao='x', niveladquirido=1)

        cls.bola = TbMagia.objects.create(
            nome='Bola de Fogo Teste', slug='bola-de-fogo-teste-vtt', nivel=3)
        cls.chama = TbMagia.objects.create(
            nome='Chama Concedida Teste', slug='chama-concedida-teste-vtt', nivel=1)

        cls.p = TbPersonagem.objects.create(
            dono=cls.user, nome='Multi Teste', nivel=5,
            forca=10, destreza=14, constituicao=14, inteligencia=16,
            sabedoria=12, carisma=8, velocidade='9 m / 30 ft', carteira_pc=134)
        TbPersonagemClasse.objects.create(
            id_personagem=cls.p, id_classe=cls.mago, nivel=3, principal=True)
        TbPersonagemClasse.objects.create(
            id_personagem=cls.p, id_classe=cls.clerigo, nivel=2)

        # idiomas do personagem (TbPersonagemProficiencia tipo='idioma' — a mesma
        # fonte de derive.idiomas via character_engine._proficiencias)
        TbPersonagemProficiencia.objects.create(
            id_personagem=cls.p, tipo='idioma', nome='Comum')
        TbPersonagemProficiencia.objects.create(
            id_personagem=cls.p, tipo='idioma', nome='Élfico')

        # magia de classe (preparada) + magia CONCEDIDA (materializada pelo
        # _sync_magias_concedidas: sempre_preparada=True, origem=nome da feature)
        TbPersonagemMagia.objects.create(
            id_personagem=cls.p, id_magia=cls.bola, nivel=3,
            nome=cls.bola.nome, preparada=True, origem='Mago Teste')
        TbPersonagemMagia.objects.create(
            id_personagem=cls.p, id_magia=cls.chama, nivel=1,
            nome=cls.chama.nome, preparada=True, sempre_preparada=True,
            origem='Vertente Teste')

    # ── forma ────────────────────────────────────────────────────────────────
    def test_forma_do_contrato(self):
        data = exportar_personagem(self.p)
        # topo FIXO em 1 (o compilador valida com z.literal(1) — igualdade exata);
        # a evolução aditiva v1.1 é sinalizada por versao_menor.
        self.assertEqual(data['versao_contrato'], 1)
        self.assertEqual(data['versao_menor'], 1)
        for chave in ('personagem', 'derive', 'recursos', 'habilidades',
                      'magias', 'estado_mesa', 'moedas', 'inspiracao', 'avisos'):
            self.assertIn(chave, data)

        pers = data['personagem']
        self.assertEqual(pers['pk'], self.p.pk)
        self.assertEqual(pers['nivel_total'], 5)
        self.assertEqual(
            [(c['classe_pk'], c['nivel']) for c in pers['classes']],
            [(self.mago.pk, 3), (self.clerigo.pk, 2)])
        self.assertIsNone(pers['raca_pk'])
        self.assertNotIn('essencia', pers)   # só aparece quando há essência

        d = data['derive']
        self.assertEqual(d['pb'], 3)
        self.assertEqual(d['atributos']['INT'], {'valor': 16, 'mod': 3})
        # PV: d6 principal (6+2, depois 4+2 ×2) + d8 (5+2 ×2) = 34
        self.assertEqual(d['pv_max'], 34)
        # Percepção não-proficiente ⇒ passiva = 10 + mod SAB (1)
        self.assertEqual(d['percepcao_passiva'], 11)
        self.assertEqual(len(d['pericias']), 18)
        perc = next(p for p in d['pericias'] if p['id'] == 'percepcao')
        self.assertEqual(perc, {'id': 'percepcao', 'nome': 'Percepção',
                                'atributo': 'SAB', 'proficiente': False,
                                'bonus': 1})

        # estado de mesa neutro semeado do derive
        self.assertEqual(data['estado_mesa'],
                         {'pv_atual': 34, 'pv_temp': 0, 'morte_s': 0, 'morte_f': 0})
        self.assertEqual(data['moedas'],
                         {'pc_total': 134, 'po': 1, 'pp': 3, 'pc': 4})
        self.assertIs(data['inspiracao'], False)

        # habilidade de classe com PK do modelo
        fontes = [h['fonte'] for h in data['habilidades']]
        self.assertIn('TbClassehabilidade:%d' % self.hab_mago.pk, fontes)

    # ── v1.1: salvaguardas ───────────────────────────────────────────────────
    def test_inspiracao_exporta_somente_concessao_registrada(self):
        grant = TbPersonagemRecurso.objects.create(
            id_personagem=self.p, chave='heroic_inspiration', nome='Inspiração Heróica',
            atual=1, maximo=1, origem='fonte:confirmada')
        self.assertIs(exportar_personagem(self.p)['inspiracao'], True)
        grant.atual = 0
        grant.save(update_fields=['atual'])
        self.assertIs(exportar_personagem(self.p)['inspiracao'], False)
        grant.atual = 1
        grant.origem = ''
        grant.save(update_fields=['atual', 'origem'])
        self.assertIs(exportar_personagem(self.p)['inspiracao'], False)

    def test_salvaguardas_com_proficiencia_de_classe(self):
        d = exportar_personagem(self.p)['derive']
        # 6 entradas SEMPRE, em ordem canônica de siglas (determinismo)
        self.assertEqual([s['atributo'] for s in d['salvaguardas']],
                         ['FOR', 'DES', 'CON', 'INT', 'SAB', 'CAR'])
        por_sig = {s['atributo']: s for s in d['salvaguardas']}
        # saves_prof{int, wis} do mago (principal): mod + PB(3) nos proficientes
        self.assertEqual(por_sig['INT'], {'atributo': 'INT', 'proficiente': True,
                                          'bonus': 6})   # mod 3 + pb 3
        self.assertEqual(por_sig['SAB'], {'atributo': 'SAB', 'proficiente': True,
                                          'bonus': 4})   # mod 1 + pb 3
        # não-proficientes: só o mod do atributo
        self.assertEqual(por_sig['FOR'], {'atributo': 'FOR', 'proficiente': False,
                                          'bonus': 0})
        self.assertEqual(por_sig['CAR'], {'atributo': 'CAR', 'proficiente': False,
                                          'bonus': -1})

    # ── v1.1: 18 perícias canônicas com atributo base ────────────────────────
    def test_pericias_completas_18_com_atributo(self):
        d = exportar_personagem(self.p)['derive']
        # TODAS as 18 canônicas saem (proficientes ou não), id = slug estável
        self.assertEqual({p['id'] for p in d['pericias']}, set(_SKILL_INFO))
        # sem override manual/tag no fixture, o atributo é o padrão de _SKILL_INFO
        for p in d['pericias']:
            self.assertEqual(p['atributo'], _SKILL_INFO[p['id']][1])
            self.assertIn('bonus', p)
            self.assertIn('proficiente', p)

    # ── v1.1: idiomas ────────────────────────────────────────────────────────
    def test_idiomas(self):
        d = exportar_personagem(self.p)['derive']
        # TbPersonagemProficiencia tipo='idioma', ordenados (determinismo)
        self.assertEqual(d['idiomas'], ['Comum', 'Élfico'])

    # ── espaços de magia multiclasse + dados de vida + consumível ────────────
    def test_recursos_multiclasse(self):
        data = exportar_personagem(self.p)
        por_id = {r['id_fonte']: r for r in data['recursos']}

        # nível efetivo 5 (mago 3 + clérigo 2, ambos full) lido da tabela do mago
        self.assertEqual(por_id['espaco-magia:1']['max'], 4)
        self.assertEqual(por_id['espaco-magia:2']['max'], 3)
        self.assertEqual(por_id['espaco-magia:3']['max'], 2)
        self.assertEqual(por_id['espaco-magia:1']['reset'], 'long-rest')
        self.assertEqual(por_id['espaco-magia:1']['circulo'], 1)

        # dados de vida por classe; total = nível total
        self.assertEqual(por_id['dado-de-vida:d6']['max'], 3)
        self.assertEqual(por_id['dado-de-vida:d8']['max'], 2)
        total_dv = sum(r['max'] for r in data['recursos']
                       if r['id_fonte'].startswith('dado-de-vida:'))
        self.assertEqual(total_dv, data['personagem']['nivel_total'])

        # consumível de classe carrega o PK real de TbRecursoclasse
        canal = por_id['TbRecursoclasse:%d' % self.canalizar.pk]
        self.assertEqual(canal['nome'], 'Canalizar Divindade Teste')
        self.assertEqual(canal['max'], 1)          # nível 2 na tabela {'1':1,'6':2}
        self.assertEqual(canal['reset'], 'short-or-long')

    # ── determinismo ─────────────────────────────────────────────────────────
    def test_determinismo_byte_identico(self):
        a = serializar(exportar_personagem(self.p))
        # segunda passada com objeto RE-buscado (nada de estado residual)
        p2 = TbPersonagem.objects.get(pk=self.p.pk)
        b = serializar(exportar_personagem(p2))
        self.assertEqual(a, b)
        self.assertTrue(a.endswith('\n'))
        self.assertNotIn('\r', a)   # LF puro

    # ── magias ───────────────────────────────────────────────────────────────
    def test_magias_concedidas_e_de_classe(self):
        data = exportar_personagem(self.p)
        por_pk = {m['magia_pk']: m for m in data['magias']}
        self.assertEqual(por_pk[self.bola.pk],
                         {'magia_pk': self.bola.pk, 'nome': 'Bola de Fogo Teste',
                          'circulo': 3, 'origem': 'classe', 'preparada': True})
        self.assertEqual(por_pk[self.chama.pk]['origem'], 'concedida')
        self.assertEqual(por_pk[self.chama.pk]['circulo'], 1)
