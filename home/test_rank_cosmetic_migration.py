"""Run with migrations enabled on a disposable database, not the syncdb UI runner."""

from importlib import import_module
from types import SimpleNamespace

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from django.utils import timezone


class RankCosmeticMigrationTests(TransactionTestCase):
    def test_historical_backfill_preserves_inventory_identity_and_suspension(self):
        before = [('home', '0163_tbpersonagem_public_default')]
        after = [('home', '0164_rank_cosmetic_rewards')]
        executor = MigrationExecutor(connection)
        executor.migrate(before)
        try:
            old = executor.loader.project_state(before).apps
            User = old.get_model('auth', 'User')
            Character = old.get_model('home', 'TbPersonagem')
            Class = old.get_model('home', 'TbClasse')
            CharacterClass = old.get_model('home', 'TbPersonagemClasse')
            Cosmetic = old.get_model('home', 'TbCosmetico')
            Inventory = old.get_model('home', 'TbUsuarioCosmetico')
            old.get_model('home', 'TbConquista').objects.filter(slug__startswith='elo-').delete()
            Cosmetic.objects.filter(slug__startswith='moldura-elo-').delete()
            owner = User.objects.create(username='rank-migration-owner')
            klass = Class.objects.create(nome='Migration class', slug='migration-class')
            character = Character.objects.create(
                dono_id=owner.pk, nome='Real private archived', nivel=20,
                aventuras=160, publico=False, arquivado=True)
            CharacterClass.objects.create(
                id_personagem_id=character.pk, id_classe_id=klass.pk, nivel=20, principal=True)
            cosmetic = Cosmetic.objects.create(
                slug='moldura-elo-obsidiana-aberta', nome='Existing frame',
                tipo='moldura', asset_url='/preserved.png', origem='staff')
            now = timezone.now()
            inventory = Inventory.objects.create(
                user_id=owner.pk, cosmetico_id=cosmetic.pk, suspenso_em=now, origem='staff')
            invalid_owner = User.objects.create(username='rank-migration-invalid')
            Character.objects.create(dono_id=invalid_owner.pk, nome='No build', nivel=20, aventuras=200)

            executor = MigrationExecutor(connection)
            executor.migrate(after)
            new = executor.loader.project_state(after).apps
            Inventory = new.get_model('home', 'TbUsuarioCosmetico')
            Cosmetic = new.get_model('home', 'TbCosmetico')
            self.assertEqual(Cosmetic.objects.filter(slug__startswith='moldura-elo-').count(), 14)
            self.assertEqual(Cosmetic.objects.get(slug=cosmetic.slug).pk, cosmetic.pk)
            self.assertEqual(Cosmetic.objects.get(pk=cosmetic.pk).asset_url, '/preserved.png')
            self.assertEqual(Inventory.objects.filter(user_id=owner.pk).count(), 14)
            saved = Inventory.objects.get(user_id=owner.pk, cosmetico_id=cosmetic.pk)
            self.assertEqual(saved.pk, inventory.pk)
            self.assertEqual(saved.suspenso_em, now)
            self.assertEqual(saved.origem, 'staff')
            self.assertFalse(Inventory.objects.filter(user_id=invalid_owner.pk).exists())
            Grant = new.get_model('home', 'TbUsuarioConquista')
            Notification = new.get_model('home', 'TbConquistaNotificacao')
            self.assertEqual(Grant.objects.filter(user_id=owner.pk).count(), 7)
            self.assertEqual(Notification.objects.filter(concessao__user_id=owner.pk).count(), 7)
            baseline = set(Inventory.objects.filter(user_id=owner.pk).values_list('pk', flat=True))
            seed = import_module('home.migrations.0164_rank_cosmetic_rewards')
            editor = SimpleNamespace(connection=connection)
            seed.seed_rank_rewards(new, editor)
            seed.backfill_rank_rewards(new, editor)
            seed.backfill_rank_rewards(new, editor)
            self.assertEqual(set(Inventory.objects.filter(
                user_id=owner.pk).values_list('pk', flat=True)), baseline)
            new.get_model('home', 'TbPersonagem').objects.filter(pk=character.pk).delete()
            seed.backfill_rank_rewards(new, editor)
            self.assertEqual(set(Inventory.objects.filter(
                user_id=owner.pk).values_list('pk', flat=True)), baseline)
            self.assertFalse(Grant.objects.filter(user_id=owner.pk, revogada_em__isnull=False).exists())
            self.assertEqual(Grant.objects.filter(user_id=owner.pk).count(), 7)
            self.assertEqual(Notification.objects.filter(concessao__user_id=owner.pk).count(), 7)
            self.assertEqual(Inventory.objects.get(pk=inventory.pk).suspenso_em, now)
        finally:
            executor = MigrationExecutor(connection)
            executor.migrate(executor.loader.graph.leaf_nodes())
