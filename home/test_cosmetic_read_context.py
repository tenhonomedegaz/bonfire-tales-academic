from unittest.mock import Mock, patch
from decimal import Decimal
from importlib import import_module
from types import SimpleNamespace

from django.apps import apps
from django.contrib.auth import get_user_model
from django.db import connection, transaction
from django.test import RequestFactory, TestCase
from django.utils import timezone

from .cosmetics import (_READ_CONTEXT, catalog_options, cosmetic_allowed,
                        cosmetic_read_context, cosmetic_read_scope, invalidate_cosmetic_cache)
from .models import (AsaasCheckoutOrder, CosmeticCheckoutPurchase, TbClasse,
                     TbCosmetico, TbPersonagem, TbPersonagemClasse,
                     TbUsuarioConquista, TbUsuarioCosmetico)


class CosmeticReadContextTests(TestCase):
    def purchase(self, user):
        order = AsaasCheckoutOrder.objects.create(user=user, product_code='synthetic-read-test',
            mode='single', amount=Decimal('1.00'))
        return CosmeticCheckoutPurchase.objects.create(order=order, beneficiary=user,
            cosmetico=self.item, slug=self.item.slug, name=self.item.nome, granted_at=timezone.now())

    def setUp(self):
        invalidate_cosmetic_cache()
        self.addCleanup(invalidate_cosmetic_cache)
        self.owner = get_user_model().objects.create_user('cosmetic-read-owner')
        self.other = get_user_model().objects.create_user('cosmetic-read-other')
        self.item = TbCosmetico.objects.create(slug='tema-read-test', nome='Read test',
            tipo='tema', origem='staff', escopo='perfil')
        self.grant = TbUsuarioCosmetico.objects.create(user=self.owner, cosmetico=self.item, origem='staff')

    def test_snapshot_is_account_and_scope_specific_and_does_not_escape_request(self):
        with cosmetic_read_context():
            self.assertTrue(cosmetic_allowed(self.owner, 'theme', 'read-test', 'perfil'))
            self.assertFalse(cosmetic_allowed(self.other, 'theme', 'read-test', 'perfil'))
            self.assertFalse(cosmetic_allowed(self.owner, 'theme', 'read-test', 'ficha'))
            self.assertFalse(cosmetic_allowed(self.owner, 'theme', 'missing', 'perfil'))
        self.assertIsNone(_READ_CONTEXT.get())
        TbUsuarioCosmetico.objects.filter(pk=self.grant.pk).update(suspenso_em=timezone.now())
        with cosmetic_read_context():
            self.assertFalse(cosmetic_allowed(self.owner, 'theme', 'read-test', 'perfil'))

    def test_write_inside_read_invalidates_snapshot(self):
        with cosmetic_read_context():
            self.assertTrue(cosmetic_allowed(self.owner, 'theme', 'read-test'))
            TbUsuarioCosmetico.objects.filter(pk=self.grant.pk).update(suspenso_em=timezone.now())
            self.assertFalse(cosmetic_allowed(self.owner, 'theme', 'read-test'))

    def test_commented_raw_update_invalidates_ownership_before_suspension_read(self):
        quote = connection.ops.quote_name
        table = quote(TbUsuarioCosmetico._meta.db_table)
        suspended = quote(TbUsuarioCosmetico._meta.get_field('suspenso_em').column)
        primary_key = quote(TbUsuarioCosmetico._meta.pk.column)
        with cosmetic_read_context():
            self.assertTrue(cosmetic_allowed(self.owner, 'theme', 'read-test'))
            with connection.cursor() as cursor:
                cursor.execute(f'/* staff suspension */ UPDATE {table} SET {suspended} = %s WHERE {primary_key} = %s',
                               [connection.ops.adapt_datetimefield_value(timezone.now()), self.grant.pk])
            self.assertFalse(cosmetic_allowed(self.owner, 'theme', 'read-test'))
        self.grant.refresh_from_db()
        self.assertIsNotNone(self.grant.suspenso_em)

    def test_unknown_commented_and_non_text_sql_clear_snapshot_without_coercion(self):
        class ComposedSQL:
            def __str__(self):
                raise AssertionError('SQL objects must not be coerced by the memo wrapper')
        for sql in (b'SELECT 1', ComposedSQL(), None, '', '   ', '/* comment */ SELECT 1',
                    '-- comment\nUPDATE table_name SET value=1', 'WITH data AS (SELECT 1) SELECT * FROM data',
                    'ROLLBACK TO SAVEPOINT test', 'COMMIT', 'CALL unknown_procedure()'):
            with self.subTest(sql_type=type(sql).__name__), cosmetic_read_context():
                state = _READ_CONTEXT.get()
                state['sentinel'] = True
                execute = Mock(return_value='delegated')
                context = {'connection': connection}
                wrapper = connection.execute_wrappers[-1]
                self.assertEqual(wrapper(execute, sql, None, False, context), 'delegated')
                self.assertEqual(state, {})
                execute.assert_called_once_with(sql, None, False, context)

    def test_only_known_first_tokens_keep_snapshot(self):
        for command in ('SELECT', 'SHOW', 'EXPLAIN', 'SAVEPOINT', 'RELEASE', 'BEGIN'):
            with self.subTest(command=command), cosmetic_read_context():
                state = _READ_CONTEXT.get()
                state['sentinel'] = True
                wrapper = connection.execute_wrappers[-1]
                wrapper(Mock(), '\n  ' + command.lower() + ' synthetic', None, False, {'connection': connection})
                self.assertTrue(state['sentinel'])

    def test_grant_delete_regrant_and_suspension_are_visible_in_same_request(self):
        with cosmetic_read_context():
            self.assertTrue(cosmetic_allowed(self.owner, 'theme', 'read-test'))
            self.grant.delete()
            self.assertFalse(cosmetic_allowed(self.owner, 'theme', 'read-test'))
            grant = TbUsuarioCosmetico.objects.create(user=self.owner, cosmetico=self.item, origem='staff')
            self.assertTrue(cosmetic_allowed(self.owner, 'theme', 'read-test'))
            TbUsuarioCosmetico.objects.filter(pk=grant.pk).update(suspenso_em=timezone.now())
            self.assertFalse(cosmetic_allowed(self.owner, 'theme', 'read-test'))
            TbUsuarioCosmetico.objects.filter(pk=grant.pk).update(suspenso_em=None)
            self.assertTrue(cosmetic_allowed(self.owner, 'theme', 'read-test'))
        with cosmetic_read_context():
            self.assertTrue(cosmetic_allowed(self.owner, 'theme', 'read-test'))

    def test_paid_confirmation_revocation_and_suspended_inventory_keep_existing_semantics(self):
        from .cosmetic_entitlements import permanent_cosmetic_slugs
        with cosmetic_read_context():
            self.assertFalse(cosmetic_allowed(self.other, 'theme', 'read-test'))
            purchase = self.purchase(self.other)
            self.assertTrue(cosmetic_allowed(self.other, 'theme', 'read-test'))
            grant = TbUsuarioCosmetico.objects.create(user=self.other, cosmetico=self.item,
                                                     origem='staff', suspenso_em=timezone.now())
            self.assertTrue(cosmetic_allowed(self.other, 'theme', 'read-test'))
            self.assertIn(self.item.slug, permanent_cosmetic_slugs(self.other, 'tema'))
            CosmeticCheckoutPurchase.objects.filter(pk=purchase.pk).update(granted_at=None)
            self.assertFalse(cosmetic_allowed(self.other, 'theme', 'read-test'))
            CosmeticCheckoutPurchase.objects.filter(pk=purchase.pk).update(granted_at=timezone.now())
            self.assertTrue(cosmetic_allowed(self.other, 'theme', 'read-test'))
            grant.refresh_from_db()
            self.assertIsNotNone(grant.suspenso_em)

    def test_paid_purchase_rollback_does_not_leave_temporary_permanent_source(self):
        from .cosmetic_entitlements import permanent_cosmetic_slugs
        with cosmetic_read_context():
            self.assertNotIn(self.item.slug, permanent_cosmetic_slugs(self.other))
            with transaction.atomic():
                self.purchase(self.other)
                self.assertTrue(cosmetic_allowed(self.other, 'theme', 'read-test'))
                transaction.set_rollback(True)
            self.assertFalse(cosmetic_allowed(self.other, 'theme', 'read-test'))
            self.assertNotIn(self.item.slug, permanent_cosmetic_slugs(self.other))
        with cosmetic_read_context():
            self.assertFalse(cosmetic_allowed(self.other, 'theme', 'read-test'))

    def test_rank_signal_grants_are_not_retained_after_preview_rollback(self):
        editor = SimpleNamespace(connection=connection)
        import_module('home.migrations.0164_rank_cosmetic_rewards').seed_rank_rewards(apps, editor)
        import_module('home.migrations.0165_rank_themes').seed_rank_themes(apps, editor)
        klass = TbClasse.objects.create(nome='Read context class', slug='read-context-class')
        invalidate_cosmetic_cache()
        with cosmetic_read_context():
            self.assertFalse(cosmetic_allowed(self.other, 'theme', 'rank-diamante'))
            with transaction.atomic():
                character = TbPersonagem.objects.create(dono=self.other, nome='Temporary build',
                                                        nivel=20, aventuras=160)
                TbPersonagemClasse.objects.create(id_personagem=character, id_classe=klass,
                                                  nivel=20, principal=True)
                self.assertTrue(cosmetic_allowed(self.other, 'theme', 'rank-diamante'))
                transaction.set_rollback(True)
            self.assertFalse(cosmetic_allowed(self.other, 'theme', 'rank-diamante'))
        self.assertFalse(TbUsuarioConquista.objects.filter(user=self.other).exists())
        self.assertFalse(TbUsuarioCosmetico.objects.filter(user=self.other).exists())

    def test_inactive_user_and_catalog_contract_is_not_redefined_by_snapshot(self):
        self.owner.is_active = False
        self.owner.save(update_fields=['is_active'])
        baseline = cosmetic_allowed(self.owner, 'theme', 'read-test')
        with cosmetic_read_context():
            self.assertEqual(cosmetic_allowed(self.owner, 'theme', 'read-test'), baseline)
            self.item.ativo = False
            self.item.save(update_fields=['ativo'])
            self.assertFalse(cosmetic_allowed(self.owner, 'theme', 'read-test'))

    def test_savepoint_rollback_cannot_keep_temporary_ownership(self):
        with cosmetic_read_context():
            self.assertFalse(cosmetic_allowed(self.other, 'theme', 'read-test'))
            with transaction.atomic():
                TbUsuarioCosmetico.objects.create(user=self.other, cosmetico=self.item, origem='staff')
                self.assertTrue(cosmetic_allowed(self.other, 'theme', 'read-test'))
                transaction.set_rollback(True)
            self.assertFalse(cosmetic_allowed(self.other, 'theme', 'read-test'))
        self.assertFalse(TbUsuarioCosmetico.objects.filter(user=self.other).exists())

    def test_catalog_reads_are_reused_without_reusing_selected_state(self):
        with cosmetic_read_context():
            first = catalog_options(self.owner, 'theme', selected='read-test')
            with self.assertNumQueries(0):
                second = catalog_options(self.owner, 'theme', selected='another')
                self.assertTrue(cosmetic_allowed(self.owner, 'theme', 'read-test'))
            self.assertTrue(first[0]['selected'])
            self.assertFalse(second[0]['selected'])

    def test_rank_sync_runs_once_per_account_per_read(self):
        self.item.definicao_json = {'desbloqueio': {'schema_version': 1,
            'metric': 'rank_reached', 'rank': 'Obsidiana', 'permanent': True}}
        self.item.save()
        with patch('home.rank_cosmetic_rewards.sync_rank_cosmetics', return_value=0) as sync:
            with cosmetic_read_context():
                catalog_options(self.owner, 'theme')
                catalog_options(self.owner, 'frame')
                catalog_options(self.owner, 'theme')
                catalog_options(self.other, 'theme')
                self.assertEqual(sync.call_count, 2)
            with cosmetic_read_context():
                catalog_options(self.owner, 'theme')
            self.assertEqual(sync.call_count, 3)

    def test_scope_is_reset_after_exception_and_save_post_is_not_scoped(self):
        factory = RequestFactory()
        @cosmetic_read_scope
        def view(request):
            if request.method == 'GET':
                self.assertIsNotNone(_READ_CONTEXT.get())
                raise ValueError('synthetic render failure')
            self.assertIsNone(_READ_CONTEXT.get())
            return 'post'
        with self.assertRaises(ValueError):
            view(factory.get('/perfil/'))
        self.assertIsNone(_READ_CONTEXT.get())
        self.assertEqual(view(factory.post('/perfil/')), 'post')
