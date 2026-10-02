from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from home.models import TbAcessoopcao, TbClasse, TbOpcaojogo, TbSubclasse
from home.views import SiteDataUnavailable


class OptionCatalogAccessTests(TestCase):
    def setUp(self):
        self.class_record = TbClasse.objects.create(nome='Bardo', slug='bardo')
        self.subclass_record = TbSubclasse.objects.create(
            nome='Colégio da Dança', slug='colegio-da-danca', id_classe=self.class_record
        )
        self.option = TbOpcaojogo.objects.create(
            nome='Passo', slug='passo', tipo='Bailado', pre_requisito='Destreza 13'
        )
        self.other = TbOpcaojogo.objects.create(nome='Livre', slug='livre', tipo='Bailado')
        TbAcessoopcao.objects.create(
            id_opcao=self.option, id_classe=self.class_record, nivel_recebimento=2
        )
        TbAcessoopcao.objects.create(
            id_opcao=self.option, id_subclasse=self.subclass_record, nivel_recebimento=6
        )

    def test_relational_catalog_includes_structured_access_separate_from_prerequisite(self):
        with patch('home.views._site_docs', side_effect=SiteDataUnavailable):
            response = self.client.get(reverse('jogador_opcoes'))

        self.assertEqual(response.status_code, 200)
        items = {item['slug']: item for item in response.context['json_opcoes']}
        self.assertEqual(items['passo']['pre_requisito'], 'Destreza 13')
        self.assertEqual(items['passo']['acessos'], [
            {'tipo': 'Classe', 'nome': 'Bardo', 'classe': 'Bardo', 'nivel': 2},
            {'tipo': 'Subclasse', 'nome': 'Colégio da Dança', 'classe': 'Bardo', 'nivel': 6},
        ])
        self.assertEqual(items['livre']['acessos'], [])

    def test_primary_postgres_document_path_uses_same_access_relationship(self):
        document = {
            'Id_Opcao': self.option.pk, 'Nome': 'Passo', 'Slug': 'passo',
            'Tipo': 'Bailado', 'PreRequisito': 'Destreza 13',
        }
        with patch('home.views._site_docs', return_value=[document]):
            response = self.client.get(reverse('jogador_opcoes'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['json_opcoes'][0]['acessos']), 2)
