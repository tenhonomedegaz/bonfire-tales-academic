from home import picks
from home.models import TbClasse, TbClassehabilidade
from home.test_criador import _CriadorBase
from django.urls import reverse
from django.utils.html import strip_tags


class ClassPageOptionWidgetTests(_CriadorBase):
    def test_guerreiro_progressao_usa_nome_canonico_em_todos_os_marcos_asi(self):
        fighter = TbClasse.objects.get(slug='guerreiro')
        self.assertIn('asi_choices{4, 6, 8, 12, 14, 16, 19}', fighter.tags_json)
        response = self.client.get(reverse('classe_detail', args=['guerreiro']))
        self.assertEqual(response.status_code, 200)
        feature_index = next(i for i, column in enumerate(response.context['colunas'])
                             if column['is_feature'])
        for level in (4, 6, 8, 12, 14, 16, 19):
            with self.subTest(level=level):
                cell = response.context['progression_table'][level - 1]['cells'][feature_index]
                text = strip_tags(str(cell['valor']))
                self.assertIn('Aprimoramento de Atributo ou Talento', text)
                self.assertNotIn('Incremento de Atributo ou Talento', text)

    def test_acl_de_um_tipo_nao_esconde_catalogo_global_de_outro_tipo(self):
        fighter = TbClasse.objects.get(slug='guerreiro')
        feature = TbClassehabilidade.objects.get(
            id_classe=fighter, nome='Fundamentos de Batalha')
        groups = picks.resolve_groups(
            [feature], classe=fighter, nivel=2, kinds={'opcao'})
        maneuvers = next(group for group in groups
                         if picks.normalize_slug(group['tipo']) == 'manobras-de-combate')
        self.assertEqual(maneuvers['n'], 2)
        self.assertGreater(len(maneuvers['universo']), 10)

    def test_fundamentos_de_batalha_armazena_widget_sem_catalogo_embutido(self):
        fighter = TbClasse.objects.get(slug='guerreiro')
        feature = TbClassehabilidade.objects.get(
            id_classe=fighter, nome='Fundamentos de Batalha')
        self.assertIn('::options=Manobras de Combate', feature.descricao)
        self.assertNotIn('#### Emboscada', feature.descricao)

    def test_manifestacao_mistica_armazena_tabelas_com_limites_validos(self):
        mystic = TbClasse.objects.get(slug='mistico')
        feature = TbClassehabilidade.objects.get(
            id_classe=mystic, nome='Manifestação Mística')
        self.assertNotIn('::\n| Nível de Místico', feature.descricao)
        self.assertNotIn('### [Marca Mística](', feature.descricao)
        self.assertEqual(feature.descricao.count('::\n\n| Nível de Místico'), 4)
