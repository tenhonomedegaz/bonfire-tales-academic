"""Ensaio de upgrade com linhas legadas, exclusivamente no banco de testes."""
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class ResourceCommandMigrationTests(TransactionTestCase):
    def test_upgrade_preserves_legacy_counter_and_reexecution(self):
        self.assertEqual(connection.vendor, 'postgresql')
        self.assertTrue(connection.settings_dict['NAME'].startswith('test_'))
        before = [('home', '0102_mercado_treinamentos_emprestimos')]
        after = [('home', '0103_resource_command_receipts')]
        executor = MigrationExecutor(connection)
        head = executor.loader.graph.leaf_nodes('home')
        current_apps = executor.loader.project_state(after).apps
        # A reversão só prepara o cenário vazio do teste. Não é um procedimento
        # de rollback para produção, onde recibos precisam ser preservados.
        self.assertEqual(current_apps.get_model('home', 'TbOperacaoRecurso').objects.count(), 0)
        executor.migrate(before)
        try:
            old = executor.loader.project_state(before).apps
            user = old.get_model('auth', 'User').objects.create(username='migration-slot')
            character = old.get_model('home', 'TbPersonagem').objects.create(
                dono_id=user.pk, nome='Contador legado')
            row = old.get_model('home', 'TbPersonagemRecurso').objects.create(
                id_personagem_id=character.pk, nome='spell-slot:1', atual=1, maximo=2)
            expected = (row.pk, character.pk, row.atual, row.maximo, row.chave)
            for _ in range(2):
                upgrade = MigrationExecutor(connection)
                upgrade.migrate(after)
                upgraded = upgrade.loader.project_state(after).apps
                resource = upgraded.get_model('home', 'TbPersonagemRecurso').objects.get(pk=row.pk)
                self.assertEqual((resource.pk, resource.id_personagem_id, resource.atual,
                                  resource.maximo, resource.chave), expected)
                self.assertEqual(resource.versao, 0)
                self.assertEqual(upgraded.get_model('home', 'TbOperacaoRecurso').objects.count(), 0)
        finally:
            MigrationExecutor(connection).migrate(head)
