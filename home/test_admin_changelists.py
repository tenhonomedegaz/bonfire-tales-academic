# -*- coding: utf-8 -*-
"""Smoke das changelists do admin.

Regressao: o modelo principal `TbPersonagem` (ficha de personagem) nunca chegou
a ser registrado no admin — so `TbPersonagemAventura`/`TbTransacao` estavam. Com
isso `/admin/home/tbpersonagem/` dava 404 e a table nem aparecia no indice ("nao
consigo acessar a table de personagens pelo admin"). Ver `TbPersonagemAdmin` em
home/admin.py.

Este smoke abre a changelist de TbPersonagem (com dados) e varre TODAS as
changelists registradas exigindo 200. Modelos `managed = False` (as tabelas
externas do Bot — rpg_quests, transactions, etc., que vivem no banco do bot e nem
existem no banco de teste/dev SQLite) sao pulados de proposito: falham por causa
DIFERENTE (tabela ausente), nao pelo bug desta correcao.
"""
from django.contrib import admin
from django.contrib.auth.models import User
from django.db import connection
from django.test import TestCase
from django.urls import reverse

from home.models import TbItemMundano, TbPersonagem


class TbPersonagemChangelistTests(TestCase):
    """A causa-raiz reportada pelo PO: a changelist de personagens abre de novo."""

    def setUp(self):
        self.superuser = User.objects.create_superuser(
            username="super-changelist",
            email="super-changelist@example.com",
            password="senha-forte-123",
        )
        self.client.force_login(self.superuser)
        # Uma ficha para a changelist renderizar com dados (exercita list_display,
        # raca_display null-safe, list_select_related e a coluna global "Excluir").
        TbPersonagem.objects.create(dono=self.superuser, nome="Smoke Hero")

    def test_tbpersonagem_changelist_opens(self):
        url = reverse("admin:home_tbpersonagem_changelist")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200, url)
        self.assertContains(response, "Smoke Hero")

    def test_tbpersonagem_add_form_opens(self):
        response = self.client.get(reverse("admin:home_tbpersonagem_add"))
        self.assertEqual(response.status_code, 200)

    def test_todas_as_armaduras_abrem_no_formulario_de_edicao(self):
        for item in TbItemMundano.objects.filter(categoria='armadura'):
            url = reverse('admin:home_tbitemmundano_change', args=[item.pk])
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200, '%s -> %s' % (item.slug, response.status_code))


class AllChangelistsSmokeTests(TestCase):
    """Superuser abre TODAS as changelists registradas — 200 em cada uma.

    Pula modelos `managed = False` (tabelas externas do Bot), que nao tem tabela
    no banco de teste e falhariam por motivo alheio a esta correcao."""

    def setUp(self):
        self.superuser = User.objects.create_superuser(
            username="super-smoke-all",
            email="super-smoke-all@example.com",
            password="senha-forte-123",
        )
        self.client.force_login(self.superuser)

    def test_every_registered_changelist_returns_200(self):
        existing_tables = set(connection.introspection.table_names())
        checked = []
        for model, model_admin in admin.site._registry.items():
            meta = model._meta
            # Tabelas externas (Bot, managed=False) vivem no banco do bot; sao
            # puladas — a ausencia delas no banco de teste nao e o bug desta fix.
            if not meta.managed or meta.db_table not in existing_tables:
                continue
            url = reverse(
                "admin:%s_%s_changelist" % (meta.app_label, meta.model_name)
            )
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200, "%s -> %s" % (url, response.status_code))
            checked.append(url)

        # Sanidade: garante que a varredura de fato exercitou a changelist alvo
        # e um conjunto significativo de tabelas do site.
        self.assertIn("/admin/home/tbpersonagem/", checked)
        self.assertGreater(len(checked), 20)
