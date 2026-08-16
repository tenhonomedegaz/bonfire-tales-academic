from home import picks, views
from home.models import TbClasse, TbClassehabilidade
from home.test_criador import _CriadorBase


class ClassPageOptionWidgetTests(_CriadorBase):
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

    def test_api_do_widget_aplica_acl_somente_ao_tipo_que_a_declara(self):
        response = self.client.get('/api/opcoes/', {
            'tipo': 'Manobras de Combate',
            'classe': 'guerreiro',
            'nivel': 2,
        })
        self.assertEqual(response.status_code, 200)
        self.assertGreater(len(response.json()['opcoes']), 10)

    def test_pagina_da_classe_substitui_catalogo_embutido_por_widget_sem_mudar_banco(self):
        fighter = TbClasse.objects.get(slug='guerreiro')
        feature = TbClassehabilidade.objects.get(
            id_classe=fighter, nome='Fundamentos de Batalha')
        original = feature.descricao
        rendered = views._class_feature_display_description(feature, fighter)
        self.assertIn('::options=Manobras de Combate', rendered)
        self.assertNotIn('#### Emboscada', rendered)
        self.assertIn('#### Emboscada', original)
        feature.refresh_from_db()
        self.assertEqual(feature.descricao, original)

    def test_normalizador_separa_center_da_tabela_markdown_seguinte(self):
        with open('home/static/js/markdown.js', encoding='utf-8') as fh:
            source = fh.read()
        self.assertIn('return `\\n\\n<span class="bonfire-center">${html}</span>\\n\\n`', source)
        self.assertIn('parseInlineMarkdownLabel(st.title)', source)
