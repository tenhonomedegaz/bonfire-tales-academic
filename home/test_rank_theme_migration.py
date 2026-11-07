"""Historical 0164 -> 0165 data upgrade; requires migrations-enabled PostgreSQL."""

from importlib import import_module
from types import SimpleNamespace

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from django.utils import timezone


class RankThemeMigrationTests(TransactionTestCase):
    def test_existing_grants_inherit_third_reward_even_without_character(self):
        before = [('home', '0164_rank_cosmetic_rewards')]
        after = [('home', '0165_rank_themes')]
        executor = MigrationExecutor(connection)
        executor.migrate(before)
        try:
            old = executor.loader.project_state(before).apps
            editor = SimpleNamespace(connection=connection)
            Cosmetic = old.get_model('home', 'TbCosmetico')
            Cosmetic.objects.filter(slug__startswith='tema-rank-').delete()
            previous = import_module('home.migrations.0164_rank_cosmetic_rewards')
            previous.seed_rank_rewards(old, editor)
            User = old.get_model('auth', 'User')
            Character = old.get_model('home', 'TbPersonagem')
            Class = old.get_model('home', 'TbClasse')
            CharacterClass = old.get_model('home', 'TbPersonagemClasse')
            Inventory = old.get_model('home', 'TbUsuarioCosmetico')
            Grant = old.get_model('home', 'TbUsuarioConquista')
            Notification = old.get_model('home', 'TbConquistaNotificacao')
            Achievement = old.get_model('home', 'TbConquista')
            owner = User.objects.create(username='rank-theme-migration-owner')
            klass = Class.objects.create(nome='Migration theme class', slug='migration-theme-class')
            character = Character.objects.create(
                dono_id=owner.pk, nome='Deleted real character', nivel=20,
                aventuras=160, publico=False, arquivado=True)
            CharacterClass.objects.create(id_personagem_id=character.pk,
                                          id_classe_id=klass.pk, nivel=20, principal=True)
            previous.backfill_rank_rewards(old, editor)
            old_inventory = set(Inventory.objects.filter(user_id=owner.pk).values_list('pk', flat=True))
            old_grants = set(Grant.objects.filter(user_id=owner.pk).values_list('pk', flat=True))
            old_notices = set(Notification.objects.filter(
                concessao__user_id=owner.pk).values_list('pk', flat=True))
            self.assertEqual(len(old_inventory), 14)
            self.assertEqual(len(old_grants), 7)
            rules = {rule.slug: (rule.pk, rule.criterio_json, rule.recompensa_id)
                     for rule in Achievement.objects.filter(slug__startswith='elo-')}
            character.delete()
            custom = Cosmetic.objects.create(
                slug='tema-rank-obsidiana', tipo='tema', nome='Existing custom theme',
                origem='conquista', escopo='ambos', css_class='theme-data',
                asset_url='/preserved-theme.png', definicao_json={'accent': '#123456'})
            now = timezone.now()
            suspended = Inventory.objects.create(
                user_id=owner.pk, cosmetico_id=custom.pk, origem='staff', suspenso_em=now)
            active_owner = User.objects.create(username='rank-theme-migration-private')
            active = Character.objects.create(dono_id=active_owner.pk, nome='Private valid',
                                              publico=False, arquivado=True)
            CharacterClass.objects.create(id_personagem_id=active.pk,
                                          id_classe_id=klass.pk, nivel=1, principal=True)
            invalid_owner = User.objects.create(username='rank-theme-migration-invalid')
            Character.objects.create(dono_id=invalid_owner.pk, nome='No build', nivel=20, aventuras=200)

            executor = MigrationExecutor(connection)
            executor.migrate(after)
            new = executor.loader.project_state(after).apps
            Inventory = new.get_model('home', 'TbUsuarioCosmetico')
            Grant = new.get_model('home', 'TbUsuarioConquista')
            Notification = new.get_model('home', 'TbConquistaNotificacao')
            Cosmetic = new.get_model('home', 'TbCosmetico')
            Achievement = new.get_model('home', 'TbConquista')
            self.assertEqual(Cosmetic.objects.filter(slug__startswith='tema-rank-').count(), 7)
            self.assertEqual(Achievement.objects.filter(slug__startswith='elo-').count(), 7)
            for rule in Achievement.objects.filter(slug__startswith='elo-'):
                self.assertEqual((rule.pk, rule.criterio_json, rule.recompensa_id), rules[rule.slug])
                self.assertTrue(rule.nome.startswith('Rank '))
                self.assertEqual(rule.recompensas_extras.count(), 2)
            self.assertEqual(Inventory.objects.filter(user_id=owner.pk).count(), 21)
            self.assertEqual(Inventory.objects.filter(user_id=active_owner.pk).count(), 3)
            self.assertFalse(Inventory.objects.filter(user_id=invalid_owner.pk).exists())
            self.assertTrue(old_inventory <= set(Inventory.objects.filter(
                user_id=owner.pk).values_list('pk', flat=True)))
            saved = Cosmetic.objects.get(slug=custom.slug)
            self.assertEqual(saved.pk, custom.pk)
            self.assertEqual(saved.asset_url, '/preserved-theme.png')
            self.assertEqual(saved.definicao_json['accent'], '#123456')
            baseline = set(Inventory.objects.filter(user_id=owner.pk).values_list('pk', flat=True))
            current = import_module('home.migrations.0165_rank_themes')
            for _ in range(2):
                current.seed_rank_themes(new, editor)
                current.backfill_rank_themes(new, editor)
            self.assertEqual(set(Inventory.objects.filter(
                user_id=owner.pk).values_list('pk', flat=True)), baseline)
            self.assertEqual(set(Grant.objects.filter(
                user_id=owner.pk).values_list('pk', flat=True)), old_grants)
            self.assertEqual(set(Notification.objects.filter(
                concessao__user_id=owner.pk).values_list('pk', flat=True)), old_notices)
            self.assertEqual(Inventory.objects.get(pk=suspended.pk).suspenso_em, now)
            self.assertEqual(Inventory.objects.get(pk=suspended.pk).origem, 'staff')
            self.assertFalse(Grant.objects.filter(user_id=owner.pk, revogada_em__isnull=False).exists())
        finally:
            executor = MigrationExecutor(connection)
            executor.migrate(executor.loader.graph.leaf_nodes())
