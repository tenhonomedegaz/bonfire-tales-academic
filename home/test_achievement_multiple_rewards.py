"""Fluxo de prêmios múltiplos, preservando o prêmio legado e direitos adquiridos."""
import json

from django.contrib.auth import get_user_model
from django.core import serializers
from django.test import TestCase
from django.urls import reverse

from home.conquistas import (avaliar_nivel_personagem, conceder_conquista,
                             revogar_conquista_manual,
                             visibilidade_conquistas_de_personagem)
from home.deploy_sync import sincronizar_conteudo
from home.models import (TbConquista, TbConquistaNotificacao, TbCosmetico,
                         TbPersonagem, TbUsuarioConquista, TbUsuarioCosmetico)


class MultipleAchievementRewardsTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user('multi-reward-owner')
        self.staff = get_user_model().objects.create_superuser(
            'multi-reward-staff', 'multi@example.invalid', 'x')
        self.first = TbCosmetico.objects.create(
            slug='multi-first', nome='Primeiro prêmio', tipo='badge', origem='conquista')
        self.extra = TbCosmetico.objects.create(
            slug='multi-extra', nome='Prêmio extra', tipo='badge', origem='conquista')

    def test_admin_configures_and_grants_both_rewards_once(self):
        self.client.force_login(self.staff)
        url = reverse('admin:home_tbconquista_add')
        self.assertContains(self.client.get(url), 'recompensas_extras')
        response = self.client.post(url, {
            'nome': 'Conquista dupla', 'slug': 'multi-reward-admin',
            'descricao': '', 'icone_url': '', 'secreta': '', 'ativo': 'on',
            'ordem': '0', 'criterio': 'manual', 'criterio_json': '{}',
            'recompensa': self.first.pk, 'recompensas_extras': [self.first.pk, self.extra.pk],
            '_save': 'Salvar',
        })
        self.assertEqual(response.status_code, 302, response.content[:1000])
        rule = TbConquista.objects.get(slug='multi-reward-admin')
        self.assertEqual(set(rule.recompensas_extras.values_list('pk', flat=True)),
                         {self.first.pk, self.extra.pk})
        self.assertTrue(conceder_conquista(self.owner, rule, por=self.staff))
        self.assertFalse(conceder_conquista(self.owner, rule, por=self.staff))
        self.assertEqual(set(TbUsuarioCosmetico.objects.filter(user=self.owner).values_list(
            'cosmetico_id', flat=True)), {self.first.pk, self.extra.pk})
        self.assertEqual(TbConquistaNotificacao.objects.filter(concessao__user=self.owner).count(), 1)
        self.assertContains(self.client.get(reverse('admin:home_tbconquista_change',
                                                     args=[rule.pk])), 'Prêmio extra')

    def test_revocation_keeps_shared_extra_and_restores_on_regrant(self):
        first_rule = TbConquista.objects.create(
            slug='multi-first-rule', nome='Conquista dupla', recompensa=self.first)
        first_rule.recompensas_extras.add(self.extra)
        second_rule = TbConquista.objects.create(
            slug='multi-second-rule', nome='Outra conquista', recompensa=self.extra)
        conceder_conquista(self.owner, first_rule, por=self.staff)
        conceder_conquista(self.owner, second_rule, por=self.staff)
        first_grant = TbUsuarioConquista.objects.get(user=self.owner, conquista=first_rule)
        second_grant = TbUsuarioConquista.objects.get(user=self.owner, conquista=second_rule)
        self.assertTrue(revogar_conquista_manual(first_grant))
        self.assertIsNotNone(TbUsuarioCosmetico.objects.get(
            user=self.owner, cosmetico=self.first).suspenso_em)
        self.assertIsNone(TbUsuarioCosmetico.objects.get(
            user=self.owner, cosmetico=self.extra).suspenso_em)
        self.assertTrue(revogar_conquista_manual(second_grant))
        self.assertIsNotNone(TbUsuarioCosmetico.objects.get(
            user=self.owner, cosmetico=self.extra).suspenso_em)
        self.assertTrue(conceder_conquista(self.owner, first_rule, por=self.staff))
        self.assertEqual(TbUsuarioCosmetico.objects.filter(
            user=self.owner, suspenso_em__isnull=True).count(), 2)
        self.assertEqual(TbConquistaNotificacao.objects.filter(concessao__user=self.owner).count(), 2)

    def test_private_source_hides_extra_until_public_or_independent_grant(self):
        rule = TbConquista.objects.create(
            slug='multi-private-rule', nome='Marco de classe', recompensa=self.first,
            criterio='automatico', criterio_json={
                'schema_version': 1, 'metric': 'class_started', 'scope': 'account',
                'filters': {'class_slug': 'guerreiro'}, 'operator': 'gte', 'target': 1})
        rule.recompensas_extras.add(self.extra)
        character = TbPersonagem.objects.create(dono=self.owner, nome='Personagem privado')
        conceder_conquista(self.owner, rule)
        TbUsuarioConquista.objects.filter(user=self.owner, conquista=rule).update(
            evidencia_json={'personagem_id': character.pk})
        public, hidden = visibilidade_conquistas_de_personagem([self.owner])
        self.assertNotIn(rule.pk, public[self.owner.pk])
        self.assertEqual(hidden[self.owner.pk], {self.first.slug, self.extra.slug})
        profile_url = reverse('public_profile', args=[self.owner.username])
        self.assertNotContains(self.client.get(profile_url), self.first.nome)
        self.assertNotContains(self.client.get(profile_url), self.extra.nome)
        independent = TbConquista.objects.create(slug='multi-independent', nome='Independente')
        independent.recompensas_extras.add(self.extra)
        conceder_conquista(self.owner, independent, por=self.staff)
        self.assertEqual(visibilidade_conquistas_de_personagem([self.owner])[1][self.owner.pk],
                         {self.first.slug})
        self.assertContains(self.client.get(profile_url), self.extra.nome)
        self.assertNotContains(self.client.get(profile_url), self.first.nome)
        character.publico = True
        character.save(update_fields=['publico'])
        public, hidden = visibilidade_conquistas_de_personagem([self.owner])
        self.assertIn(rule.pk, public[self.owner.pk])
        self.assertEqual(hidden[self.owner.pk], set())
        self.assertContains(self.client.get(profile_url), self.first.nome)

    def test_automatic_reassessment_suspends_every_unproven_reward(self):
        rule = TbConquista.objects.create(
            slug='multi-auto-level', nome='Nível não comprovado',
            criterio='automatico', recompensa=self.first,
            criterio_json={'schema_version': 1, 'metric': 'character_level',
                           'scope': 'account', 'filters': {'class_slug': 'guerreiro'},
                           'operator': 'gte', 'target': 2})
        rule.recompensas_extras.add(self.extra)
        self.assertTrue(conceder_conquista(self.owner, rule))
        avaliar_nivel_personagem(self.owner)
        self.assertIsNotNone(TbUsuarioConquista.objects.get(
            user=self.owner, conquista=rule).revogada_em)
        self.assertEqual(TbUsuarioCosmetico.objects.filter(
            user=self.owner, suspenso_em__isnull=False).count(), 2)

    def test_animated_frame_cannot_be_configured_or_granted_as_extra(self):
        frame = TbCosmetico.objects.create(
            slug='multi-animated-frame', nome='Moldura animada',
            tipo='moldura', animado=True, origem='colaborador')
        self.client.force_login(self.staff)
        response = self.client.post(reverse('admin:home_tbconquista_add'), {
            'nome': 'Prêmio inválido', 'slug': 'multi-invalid-frame',
            'descricao': '', 'icone_url': '', 'ativo': 'on', 'ordem': '0',
            'criterio': 'manual', 'criterio_json': '{}',
            'recompensa': self.first.pk, 'recompensas_extras': [frame.pk],
            '_save': 'Salvar',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Molduras animadas são exclusivas')
        self.assertFalse(TbConquista.objects.filter(slug='multi-invalid-frame').exists())
        rule = TbConquista.objects.create(slug='multi-invalid-direct', nome='Inválida')
        rule.recompensas_extras.add(frame)
        with self.assertRaisesRegex(ValueError, 'Molduras animadas'):
            conceder_conquista(self.owner, rule)
        self.assertFalse(TbUsuarioConquista.objects.filter(user=self.owner).exists())

    def test_content_sync_remaps_extra_rewards_and_preserves_legacy_fixture(self):
        rule = TbConquista.objects.create(
            slug='multi-sync-rule', nome='Antigo', recompensa=self.first)
        rule.recompensas_extras.add(self.first)
        fixture = json.loads(serializers.serialize('json', [self.first, self.extra, rule]))
        source_ids = {row['fields']['slug']: row['pk'] for row in fixture}
        for row in fixture:
            row['pk'] += 100000
            if row['model'] == 'home.tbconquista':
                row['fields']['recompensa'] = source_ids[self.first.slug] + 100000
                row['fields']['recompensas_extras'] = [source_ids[self.extra.slug] + 100000]
                row['fields']['nome'] = 'Atualizado'
        report = sincronizar_conteudo(json.dumps(fixture))
        rule.refresh_from_db()
        self.assertTrue(report['mem_ok'])
        self.assertEqual(rule.nome, 'Atualizado')
        self.assertEqual(rule.recompensa_id, self.first.pk)
        self.assertEqual(set(rule.recompensas_extras.values_list('pk', flat=True)), {self.extra.pk})
        # Fixture anterior à relação extra não deve apagar direitos configurados.
        for row in fixture:
            if row['model'] == 'home.tbconquista':
                del row['fields']['recompensas_extras']
        sincronizar_conteudo(json.dumps(fixture))
        self.assertEqual(set(rule.recompensas_extras.values_list('pk', flat=True)), {self.extra.pk})
        for row in fixture:
            if row['model'] == 'home.tbconquista':
                row['fields']['nome'] = 'Não deve persistir'
                row['fields']['recompensas_extras'] = [9999999]
        with self.assertRaisesRegex(ValueError, 'Recompensa extra ausente'):
            sincronizar_conteudo(json.dumps(fixture))
        rule.refresh_from_db()
        self.assertEqual(rule.nome, 'Atualizado')
        self.assertEqual(set(rule.recompensas_extras.values_list('pk', flat=True)), {self.extra.pk})
