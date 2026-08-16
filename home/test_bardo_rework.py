# -*- coding: utf-8 -*-
"""Regressoes do rework do Bardo de 2026-07-24."""

from django.core.management import call_command
from django.test import TestCase

from home import picks, views
from home.character_engine import _resource_max_at, _resource_value_at
from home.models import (
    TbAcessoopcao,
    TbClasse,
    TbClassehabilidade,
    TbOpcaojogo,
    TbRegra,
    TbRecursoclasse,
    TbSubclasse,
)


class BardoReworkTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        TbRegra.objects.filter(slug="aumento-de-atributo").delete()
        call_command(
            "loaddata", "home/fixtures/conteudo.json", verbosity=0)
        cls.classe = TbClasse.objects.get(slug="bardo")

    def test_pagina_e_metadados_sao_da_versao_reworkada(self):
        self.assertEqual(self.classe.atributo_principal, "Carisma")
        self.assertEqual(self.classe.dado_vida, "1d8 por nível de Bardo")
        self.assertEqual(self.classe.multiclass_requisitos, "Carisma 13")
        self.assertNotIn("Perícia", self.classe.multiclass_pericias or "")

        abilities = TbClassehabilidade.objects.filter(id_classe=self.classe)
        self.assertEqual(abilities.count(), 78)
        self.assertFalse(
            abilities.filter(nome="Característica de Colégio").exists())
        self.assertTrue(
            abilities.filter(
                nome="Acordes de Poder",
                niveladquirido=2,
                id_subclasse__isnull=True,
            ).exists())
        self.assertTrue(
            abilities.filter(
                nome="Inspiração Superior",
                niveladquirido=18,
                id_subclasse__isnull=True,
            ).exists())

    def test_habilidades_removidas_nao_sobrevivem_ao_rework(self):
        legacy_refs = {
            (None, "Conjuração de Magias"),
            ("colegio-da-conspiracao", "Assalto Psíquico 3 Rolagens"),
            ("colegio-da-conspiracao", "Assalto Psíquico 4 Rolagens"),
            ("colegio-da-conspiracao", "Assalto Psíquico 5 Rolagens"),
            ("colegio-da-conspiracao", "Fragmento da Canção"),
            ("colegio-da-conspiracao", "Golpe Sorrateiro"),
            ("colegio-da-criacao", "Inspiração em Movimento"),
            ("colegio-da-danca", "Cena é Corpo"),
            ("colegio-da-danca", "Cortesia da Plateia"),
            ("colegio-da-danca", "Dança em Cena"),
            ("colegio-da-danca", "Defesa Desarmada & Golpe de Palco"),
            ("colegio-da-danca", "Estilo de Fuga"),
            ("colegio-da-danca", "Estilos de Dança"),
            ("colegio-da-danca", "Estilos de Dança 2º Estilo"),
            ("colegio-da-danca", "Estilos de Dança 3º Estilo"),
            ("colegio-da-danca", "Estilos de Dança 4º Estilo"),
            ("colegio-da-danca", "Magia em Passo"),
            ("colegio-das-laminas", "Segundo Ataque Mágico"),
            ("colegio-do-conselho", "Descobertas Mágicas"),
            ("colegio-dos-espiritos", "Foco Espiritual Aprimorado"),
            ("colegio-dos-espiritos", "Sussurros de Orientação"),
            ("colegio-skald", "Segundo Ataque Mágico"),
            ("colegio-skald", "Verso Afiado"),
        }
        abilities = TbClassehabilidade.objects.filter(id_classe=self.classe)
        for subclass_slug, name in legacy_refs:
            query = abilities.filter(nome=name)
            if subclass_slug is None:
                query = query.filter(id_subclasse__isnull=True)
            else:
                query = query.filter(id_subclasse__slug=subclass_slug)
            self.assertFalse(
                query.exists(),
                f"Resíduo da versão anterior: {subclass_slug or 'bardo'}:{name}",
            )

    def test_progressao_de_recursos_esta_compactada(self):
        resources = TbRecursoclasse.objects.filter(id_classe=self.classe)
        self.assertEqual(resources.count(), 14)
        acordes = resources.get(slug="acordes")
        conhecidas = resources.get(slug="magias_conhecidas")
        dado = resources.get(slug="dado-de-inspiracao")

        self.assertEqual(acordes.tipo, "choice")
        self.assertEqual(
            [_resource_max_at(acordes, level)
             for level in (2, 4, 6, 10, 14, 18)],
            [2, 3, 4, 5, 6, 7],
        )
        self.assertEqual(_resource_max_at(conhecidas, 1), 6)
        self.assertEqual(_resource_max_at(conhecidas, 20), 26)
        self.assertEqual(_resource_value_at(dado, 15), "d12")

    def test_builder_inicial_oferece_duas_cantrips_e_seis_magias(self):
        info = views._classe_conjuracao(self.classe)
        self.assertEqual(info["ability"], "cha")
        self.assertEqual(info["lista"], ["bardo"])
        self.assertEqual(info["truques_n"], 2)
        self.assertEqual(info["magias_n"], 6)

    def test_acordes_sao_escolha_generica_dirigida_por_tags(self):
        source = TbClassehabilidade.objects.get(
            id_classe=self.classe,
            id_subclasse__isnull=True,
            nome="Acordes de Poder",
        )
        expected = {
            2: (2, 4),
            4: (3, 4),
            6: (4, 8),
            10: (5, 11),
            14: (6, 11),
            18: (7, 14),
        }
        for level, (count, universe) in expected.items():
            groups = picks.resolve_groups(
                [source],
                classe=self.classe,
                nivel=level,
                kinds={"opcao"},
            )
            group = next(
                g for g in groups if g["tipo"] == "acordes_de_poder")
            self.assertEqual(group["n"], count)
            self.assertEqual(len(group["universo"]), universe)

    def test_bailados_sao_escolha_generica_dirigida_por_tags(self):
        subclass = TbSubclasse.objects.get(
            id_classe=self.classe, slug="colegio-da-danca")
        source = TbClassehabilidade.objects.get(
            id_subclasse=subclass, nome="Bailados de Combate")
        for level, count in ((3, 2), (6, 3), (14, 4), (18, 5)):
            groups = picks.resolve_groups(
                [source],
                classe=self.classe,
                subclasse=subclass,
                nivel=level,
                kinds={"opcao"},
            )
            group = next(
                g for g in groups if g["tipo"] == "bailados_de_combate")
            self.assertEqual(group["n"], count)
            self.assertEqual(len(group["universo"]), 8)

    def test_catalogos_e_acessos_estao_completos(self):
        acordes = TbOpcaojogo.objects.filter(tipo="Acordes de Poder")
        bailados = TbOpcaojogo.objects.filter(tipo="Bailados de Combate")
        self.assertEqual(acordes.count(), 14)
        self.assertEqual(bailados.count(), 8)
        self.assertEqual(
            TbAcessoopcao.objects.filter(id_opcao__in=acordes).count(), 14)
        self.assertEqual(
            TbAcessoopcao.objects.filter(id_opcao__in=bailados).count(), 8)
        self.assertFalse(
            acordes.filter(tags_json=[]).exists()
            or bailados.filter(tags_json=[]).exists())
