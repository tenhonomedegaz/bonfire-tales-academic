from importlib import import_module
from types import SimpleNamespace
from unittest.mock import patch

from django.apps import apps
from django.db import connection

from .cosmetics import invalidate_cosmetic_cache
from .models import TbConquistaNotificacao, TbPersonagem, TbUsuarioConquista, TbUsuarioCosmetico
from .pathbuilder import default_build, simulate_build
from .test_criador import _CriadorBase


class RankCosmeticPreviewTests(_CriadorBase):
    def test_real_laboratory_pipeline_rolls_back_cosmetic_inventory(self):
        seed = import_module('home.migrations.0164_rank_cosmetic_rewards')
        seed.seed_rank_rewards(apps, SimpleNamespace(connection=connection))
        invalidate_cosmetic_cache()
        self.addCleanup(invalidate_cosmetic_cache)
        owner = self._novo_usuario('rank-real-preview')
        data = self._payload('guerreiro')

        def inspect_before_rollback(ficha, character, build, *args, **kwargs):
            self.assertEqual(TbUsuarioCosmetico.objects.filter(user=owner).count(), 2)
            self.assertEqual(character.nivel, 1)
            return {'checked': True}

        # Exercise actual persistence and rollback; rendering belongs to another task.
        with patch('home.pathbuilder._summary', side_effect=inspect_before_rollback):
            result = simulate_build(owner, data, default_build(data))
        self.assertTrue(result['checked'])
        self.assertFalse(TbPersonagem.objects.filter(dono=owner).exists())
        self.assertFalse(TbUsuarioCosmetico.objects.filter(user=owner).exists())
        self.assertFalse(TbUsuarioConquista.objects.filter(user=owner).exists())
        self.assertFalse(TbConquistaNotificacao.objects.filter(concessao__user=owner).exists())
