# -*- coding: utf-8 -*-
from django.test import TestCase

from home.management.commands.sanear_descricoes_habilidades import (
    _reference_index,
    sanitize_description,
)
from home.models import TbClasse, TbClassehabilidade


class ClassDescriptionSanitizerTests(TestCase):
    def test_remove_rotulos_e_link_table_only_sem_apagar_texto(self):
        classe = TbClasse.objects.create(nome='Sentinela', slug='sentinela')
        TbClassehabilidade.objects.create(
            id_classe=classe, nome='Progressão Interna', niveladquirido=1,
            descricao='Somente tabela.', table_only=True)
        source = TbClassehabilidade.objects.create(
            id_classe=classe, nome='Postura', niveladquirido=1,
            descricao=(
                '**Efeito:**\n- **Ativação:** Como uma **Ação Bônus**, use '
                '[Progressão Interna](tbClassehabilidade, sentinela, progressao-interna).'))

        cleaned, counters, warnings = sanitize_description(
            source.descricao, source=source, index=_reference_index())

        self.assertNotIn('**Efeito:**', cleaned)
        self.assertNotIn('**Ativação:**', cleaned)
        self.assertIn('Como uma **Ação Bônus**', cleaned)
        self.assertIn('Progressão Interna', cleaned)
        self.assertNotIn('(tbClassehabilidade', cleaned)
        self.assertEqual(counters['labels'], 2)
        self.assertEqual(counters['table_only_links'], 1)
        self.assertFalse(warnings)

    def test_referencia_cruzada_vira_texto_sem_perder_rotulo(self):
        origem = TbClasse.objects.create(nome='Sentinela', slug='sentinela')
        destino = TbClasse.objects.create(nome='Guardião', slug='guardiao')
        target = TbClassehabilidade.objects.create(
            id_classe=destino, nome='Vigília', niveladquirido=1,
            descricao='Permaneça atento.')
        source = TbClassehabilidade.objects.create(
            id_classe=origem, nome='Emular', niveladquirido=1,
            descricao='Use [Vigília](tbClassehabilidade, guardiao, vigilia).')

        cleaned, counters, warnings = sanitize_description(
            source.descricao, source=source, index=_reference_index())

        self.assertEqual(cleaned, 'Use Vigília.')
        self.assertEqual(counters['invalid_links'], 0)
        self.assertEqual(counters['cross_owner_links'], 1)
        self.assertFalse(warnings)
