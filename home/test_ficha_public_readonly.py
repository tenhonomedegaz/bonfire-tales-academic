"""Leitura de ficha alheia não materializa recursos nem magias do dono."""

from unittest.mock import patch

from django.db import connection
from django.urls import reverse

from home.models import TbPersonagemItem, TbPersonagemMagia, TbPersonagemRecurso
from home.test_levelup import LevelUpLoteBase


class PublicFichaReadOnlyTests(LevelUpLoteBase):
    def test_public_viewer_can_read_without_synchronizing_owner_state(self):
        character = self._guerreiro_no_nivel(1, apelido='ficha-leitura-publica')
        character.publico = False
        character.save(update_fields=['publico'])
        viewer = self._novo_usuario('ficha-leitura-visitante')
        self.client.force_login(viewer)
        url = reverse('ficha_detail', args=[character.pk])
        self.assertEqual(self.client.get(url).status_code, 404)

        character.publico = True
        character.save(update_fields=['publico'])
        charged_item = TbPersonagemItem.objects.create(
            id_personagem=character, nome='Kit carregado', qtd=1,
            tags_json=['charges:3(reset:dawn)'])
        before = (TbPersonagemMagia.objects.filter(id_personagem=character).count(),
                  TbPersonagemRecurso.objects.filter(id_personagem=character).count())
        writes = []

        def capture_writes(execute, sql, params, many, context):
            if sql.lstrip().upper().startswith(('INSERT ', 'UPDATE ', 'DELETE ')):
                writes.append(sql.split()[0])
            return execute(sql, params, many, context)

        with (patch('home.market_services.sync_training',
                    side_effect=AssertionError('training write on public read')),
              patch('home.views._sync_magias_concedidas',
                    side_effect=AssertionError('spell write on public read')),
              patch('home.resource_engine.ensure_resource',
                    side_effect=AssertionError('resource write on public read')),
              patch('home.resource_engine.sync_item_charges',
                    side_effect=AssertionError('item charge write on public read')),
              connection.execute_wrapper(capture_writes)):
            page = self.client.get(url)
            reopened = self.client.get(url)
        public_url = reverse('ficha_publica', args=[character.pk])
        self.assertEqual((page.status_code, reopened.status_code), (302, 302))
        self.assertEqual(page.url, public_url)
        self.assertEqual(reopened.url, public_url)
        public_page = self.client.get(public_url)
        self.assertContains(public_page, character.nome)
        self.assertNotContains(public_page, charged_item.nome)
        after = (TbPersonagemMagia.objects.filter(id_personagem=character).count(),
                 TbPersonagemRecurso.objects.filter(id_personagem=character).count())
        self.assertEqual(after, before)
        self.assertEqual(writes, [])

    def test_owner_read_keeps_existing_synchronization(self):
        character = self._guerreiro_no_nivel(1, apelido='ficha-leitura-dono')
        self.client.force_login(character.dono)
        with (patch('home.market_services.sync_training') as training,
              patch('home.views._sync_magias_concedidas') as spells):
            page = self.client.get(reverse('ficha_detail', args=[character.pk]))
        self.assertEqual(page.status_code, 200)
        self.assertTrue(page.context['pode_editar'])
        training.assert_called_once()
        spells.assert_called_once()
