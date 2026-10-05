"""Aceite local da progressão de nível baseada em revisão canônica."""
from django.contrib.auth import get_user_model
from django.urls import reverse

from home.character_history import capture_build, register_revision
from home.conquistas import conceder_conquista, registrar_fato_level_up
from home.models import (TbConquista, TbConquistaNotificacao, TbCosmetico,
                         TbPersonagem, TbEventoConquista, TbUsuarioConquista,
                         UserProfile)
from home.test_criador import _CriadorBase


class LevelAchievementTests(_CriadorBase):
    def test_private_level_milestone_and_rewards_follow_character_visibility(self):
        owner = self._novo_usuario('level-private-owner')
        badge = TbCosmetico.objects.create(
            slug='level-private-badge', nome='Badge de nivel privado QA',
            tipo='badge', origem='conquista')
        frame = TbCosmetico.objects.create(
            slug='level-private-frame', nome='Moldura de nivel privado QA',
            tipo='moldura', origem='conquista', escopo='perfil',
            css_class='frame-level-private-qa')
        definition = {'schema_version': 1, 'metric': 'character_level',
                      'scope': 'account', 'filters': {'class_slug': 'guerreiro'},
                      'operator': 'gte', 'target': 2}
        badge_rule = TbConquista.objects.create(
            slug='level-private-badge-rule', nome='Marco privado de guerreiro QA',
            criterio='automatico', criterio_json=definition, recompensa=badge)
        TbConquista.objects.create(
            slug='level-private-frame-rule', nome='Marco de moldura privada QA',
            criterio='automatico', criterio_json=definition, recompensa=frame)
        created = self._post_criar(owner, self._payload('guerreiro'))
        self.assertTrue(created.json()['ok'], created.content)
        character = TbPersonagem.objects.get(pk=created.json()['id'])
        snapshot = capture_build(character)
        primary = character.classes.get(principal=True)
        primary.nivel = 2
        primary.save(update_fields=['nivel'])
        character.nivel = 2
        character.save(update_fields=['nivel', 'atualizado_em'])
        register_revision(character, tipo='level_up', snapshot=snapshot, user=owner,
                          nivel_antes=1, nivel_depois=2)
        self.assertEqual(TbUsuarioConquista.objects.filter(
            user=owner, revogada_em__isnull=True,
            conquista__criterio_json__metric='character_level').count(), 2)
        profile = UserProfile.objects.get(user=owner)
        profile.avatar_frame = frame.slug
        profile.save(update_fields=['avatar_frame'])
        url = reverse('public_profile', args=[owner.username])

        self.client.logout()
        visitor = self.client.get(url)
        for private_text in (badge_rule.nome, badge.nome, frame.slug, frame.css_class):
            self.assertNotContains(visitor, private_text)
        self.client.force_login(owner)
        own_page = self.client.get(url)
        self.assertContains(own_page, badge_rule.nome)
        self.assertContains(own_page, frame.css_class)
        moderator = get_user_model().objects.create_superuser(
            'level-private-moderator', 'level-private-moderator@example.invalid', 'x')
        self.client.force_login(moderator)
        self.assertContains(self.client.get(url), badge_rule.nome)
        self.client.logout()

        character.publico = True
        character.save(update_fields=['publico'])
        public_page = self.client.get(url)
        self.assertContains(public_page, badge_rule.nome)
        self.assertContains(public_page, badge.nome)
        self.assertContains(public_page, frame.css_class)
        character.arquivado = True
        character.save(update_fields=['arquivado'])
        archived_page = self.client.get(url)
        for private_text in (badge_rule.nome, badge.nome, frame.slug, frame.css_class):
            self.assertNotContains(archived_page, private_text)

        independent = TbConquista.objects.create(
            slug='level-badge-independent-qa', nome='Conquista publica independente QA',
            criterio='manual', recompensa=badge)
        conceder_conquista(owner, independent)
        shared_page = self.client.get(url)
        self.assertNotContains(shared_page, badge_rule.nome)
        self.assertContains(shared_page, badge.nome)
        self.assertNotContains(shared_page, frame.css_class)

    def test_replay_de_nivel_antigo_preserva_marco_atual_sem_duplicar_aviso(self):
        owner = self._novo_usuario('level-replay-owner')
        rule = TbConquista.objects.create(
            slug='level-three-replay-test', nome='Marco fictício de nível 3',
            criterio='automatico', criterio_json={
                'schema_version': 1, 'metric': 'character_level',
                'scope': 'account', 'filters': {'class_slug': 'guerreiro'},
                'operator': 'gte', 'target': 3})
        created = self._post_criar(owner, self._payload('guerreiro'))
        self.assertTrue(created.json()['ok'], created.content)
        character = TbPersonagem.objects.get(pk=created.json()['id'])
        revisions = []
        for level in (2, 3):
            snapshot = capture_build(character)
            primary = character.classes.get(principal=True)
            primary.nivel = level
            primary.save(update_fields=['nivel'])
            character.nivel = level
            character.save(update_fields=['nivel', 'atualizado_em'])
            revisions.append(register_revision(
                character, tipo='level_up', snapshot=snapshot, user=owner,
                nivel_antes=level - 1, nivel_depois=level))

        first_event = TbEventoConquista.objects.get(
            tipo='character_level_up', agregado_id=revisions[0].pk)
        self.assertEqual(registrar_fato_level_up(revisions[0]).pk, first_event.pk)
        self.assertEqual(first_event.payload_json['level_after'], 2)
        grant = TbUsuarioConquista.objects.get(user=owner, conquista=rule)
        self.assertIsNone(grant.revogada_em)
        self.assertEqual(grant.evidencia_json['agregado_id'], revisions[1].pk)
        self.assertEqual(TbConquistaNotificacao.objects.filter(
            concessao__user=owner, concessao__conquista=rule).count(), 1)

    def test_level_rule_grants_once_and_reversal_removes_private_progress(self):
        owner = self._novo_usuario('level-achievement-owner')
        other = self._novo_usuario('level-achievement-other')
        rule = TbConquista.objects.create(
            slug='level-two-test', nome='Marco fictício de nível 2',
            criterio='automatico', criterio_json={
                'schema_version': 1, 'metric': 'character_level',
                'scope': 'account', 'filters': {'class_slug': 'guerreiro'},
                'operator': 'gte', 'target': 2})
        created = self._post_criar(owner, self._payload('guerreiro'))
        self.assertTrue(created.json()['ok'], created.content)
        character = TbPersonagem.objects.get(pk=created.json()['id'])
        self.client.force_login(owner)
        self.assertContains(self.client.get(reverse('profile')),
                            'Nível atual comprovado: 0')

        snapshot = capture_build(character)
        primary = character.classes.get(principal=True)
        primary.nivel = 2
        primary.save(update_fields=['nivel'])
        character.nivel = 2
        character.save(update_fields=['nivel', 'atualizado_em'])
        revision = register_revision(
            character, tipo='level_up', snapshot=snapshot, user=owner,
            nivel_antes=1, nivel_depois=2)
        self.assertEqual(TbUsuarioConquista.objects.filter(
            user=owner, conquista=rule, revogada_em__isnull=True).count(), 1)
        self.assertEqual(TbConquistaNotificacao.objects.filter(
            concessao__user=owner, concessao__conquista=rule).count(), 1)
        self.assertContains(self.client.get(reverse('profile')),
                            'Nível atual comprovado: 2')
        self.assertContains(self.client.get(reverse('conquista_notificacoes')),
                            rule.nome)
        registrar_fato_level_up(revision)
        self.assertEqual(TbConquistaNotificacao.objects.filter(
            concessao__user=owner, concessao__conquista=rule).count(), 1)

        later_rule = TbConquista.objects.create(
            slug='level-two-later', nome='Marco retroativo fictício',
            criterio='automatico', criterio_json=rule.criterio_json)
        admin_url = reverse('admin:home_tbconquista_changelist')
        action = {'action': 'reprocessar_nivel',
                  '_selected_action': [str(later_rule.pk)]}
        self.assertNotEqual(self.client.post(admin_url, action).status_code, 200)
        self.assertFalse(TbUsuarioConquista.objects.filter(
            user=owner, conquista=later_rule).exists())
        staff = get_user_model().objects.create_superuser(
            'level-achievement-admin', 'level-admin@example.invalid', 'x')
        self.client.force_login(staff)
        self.assertEqual(self.client.post(admin_url, action).status_code, 302)
        self.assertTrue(TbUsuarioConquista.objects.filter(
            user=owner, conquista=later_rule, revogada_em__isnull=True).exists())

        self.client.force_login(other)
        denied = self.client.post(reverse('personagem_reverter_revisao',
                                          args=[character.pk, revision.pk]))
        self.assertNotEqual(denied.status_code, 302)
        self.assertNotContains(self.client.get(reverse('conquista_notificacoes')),
                               rule.nome)
        self.client.force_login(owner)
        reversed_response = self.client.post(reverse('personagem_reverter_revisao',
                                                    args=[character.pk, revision.pk]))
        self.assertEqual(reversed_response.status_code, 302)
        grant = TbUsuarioConquista.objects.get(user=owner, conquista=rule)
        self.assertIsNotNone(grant.revogada_em)
        self.assertIsNotNone(TbUsuarioConquista.objects.get(
            user=owner, conquista=later_rule).revogada_em)
        self.assertNotContains(self.client.get(reverse('conquista_notificacoes')),
                               rule.nome)
