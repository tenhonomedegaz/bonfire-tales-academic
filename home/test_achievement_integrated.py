"""Aceite integrado dos marcos automáticos já sustentados por fatos do site."""
import json

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.urls import reverse
from django.utils import timezone

from home.models import (TbClasse, TbConquista, TbCosmetico, TbCronica,
                         TbConquistaNotificacao, TbEventoConquista, TbItemMundano, TbPersonagem,
                         TbPersonagemAventura, TbTransacao, TbUsuarioConquista,
                         TbUsuarioCosmetico)
from home.test_criador import _CriadorBase
from home.views import _cronica_pending_snapshot, _preco_em_pc


class AchievementIntegratedTests(_CriadorBase):
    def test_admin_reprocesses_only_selected_initial_milestones(self):
        owner = self._novo_usuario('initial-milestones-owner')
        created = self._post_criar(owner, self._payload('guerreiro'))
        self.assertTrue(created.json()['ok'], created.content)
        reviewer = self._novo_usuario('initial-milestones-reviewer', staff=True)
        published_at = timezone.now()
        story = TbCronica.objects.create(
            titulo='Crônica histórica', slug='cronica-historica-admin',
            conteudo_markdown='Uma crônica aprovada.', autor=owner,
            status='aprovada', revisado_por=reviewer,
            data_revisao=published_at, data_publicacao=published_at)
        definitions = {
            'characters_created': {'schema_version': 1, 'metric': 'characters_created',
                                   'scope': 'account', 'operator': 'gte', 'target': 1},
            'class_started': {'schema_version': 1, 'metric': 'class_started',
                              'scope': 'account', 'filters': {'class_slug': 'guerreiro'},
                              'operator': 'gte', 'target': 1},
            'stories_published': {'schema_version': 1, 'metric': 'stories_published',
                                  'scope': 'account', 'operator': 'gte', 'target': 1},
        }
        rules = {metric: TbConquista.objects.create(
            slug=f'initial-admin-{metric}', nome=f'Marco {metric}',
            criterio='automatico', criterio_json=definition)
            for metric, definition in definitions.items()}
        manual = TbConquista.objects.create(slug='initial-admin-manual',
                                             nome='Marco manual', criterio='manual')
        inactive = TbConquista.objects.create(
            slug='initial-admin-inactive', nome='Marco inativo', ativo=False,
            criterio='automatico', criterio_json=definitions['characters_created'])
        admin_user = get_user_model().objects.create_superuser(
            'initial-milestones-admin', 'milestones@example.invalid', 'x')
        self.client.force_login(admin_user)
        url = reverse('admin:home_tbconquista_changelist')

        def reprocess(*selected):
            response = self.client.post(url, {
                'action': 'reprocessar_marcos_iniciais', 'select_across': '0',
                '_selected_action': [rule.pk for rule in selected],
            })
            self.assertEqual(response.status_code, 302)

        reprocess(manual)
        reprocess(inactive)
        self.assertFalse(TbUsuarioConquista.objects.filter(user=owner).exists())
        expected = set()
        for metric in ('class_started', 'characters_created', 'stories_published'):
            reprocess(rules[metric])
            expected.add(metric)
            self.assertEqual(set(TbUsuarioConquista.objects.filter(user=owner)
                                 .values_list('conquista__criterio_json__metric', flat=True)),
                             expected)
        reprocess(*rules.values())
        grants = TbUsuarioConquista.objects.filter(user=owner)
        self.assertEqual(grants.count(), 3)
        self.assertEqual(TbConquistaNotificacao.objects.filter(concessao__user=owner).count(), 3)
        self.assertEqual(TbEventoConquista.objects.filter(
            conta=owner, tipo='story_published', agregado_id=story.pk).count(), 1)
        self.client.force_login(owner)
        profile = self.client.get(reverse('profile'))
        inbox = self.client.get(reverse('conquista_notificacoes'))
        for rule in rules.values():
            self.assertContains(profile, rule.nome)
            self.assertContains(inbox, rule.nome)

    def test_real_events_award_and_revoke_independently_with_shared_reward(self):
        owner = self._novo_usuario('achievement-integrated-owner')
        staff = self._novo_usuario('achievement-integrated-staff', staff=True)
        staff.user_permissions.add(Permission.objects.get(
            codename='change_tbcronica', content_type__app_label='home'))
        reward = TbCosmetico.objects.create(
            slug='integrated-achievement-badge', nome='Badge integrado',
            tipo='badge', origem='conquista')
        item = next(i for i in TbItemMundano.objects.order_by('nome')
                    if _preco_em_pc(i.preco) is not None)
        rules = {
            'character': {'schema_version': 1, 'metric': 'characters_created',
                          'scope': 'account', 'operator': 'gte', 'target': 1},
            'class': {'schema_version': 1, 'metric': 'class_started',
                      'scope': 'account', 'filters': {'class_slug': 'guerreiro'},
                      'operator': 'gte', 'target': 1},
            'adventure': {'schema_version': 1, 'metric': 'adventures_played',
                          'scope': 'account', 'aggregate': 'sum',
                          'filters': {'valid': True, 'origin': 'played_session'},
                          'operator': 'gte', 'target': 2},
            'purchase': {'schema_version': 1, 'metric': 'items_purchased',
                         'scope': 'account', 'operator': 'gte', 'target': 1},
            'units': {'schema_version': 1, 'metric': 'items_purchased_units',
                      'scope': 'account', 'aggregate': 'sum',
                      'filters': {'items': [{'catalog': 'mundano', 'id': item.pk}]},
                      'operator': 'gte', 'target': 2},
            'story': {'schema_version': 1, 'metric': 'stories_published',
                      'scope': 'account', 'operator': 'gte', 'target': 1},
        }
        for key, definition in rules.items():
            rule = TbConquista(
                slug=f'integrated-{key}', nome=f'Marco {key}', criterio='automatico',
                criterio_json=definition, recompensa=reward)
            rule.full_clean()
            rule.save()

        created = self._post_criar(owner, self._payload('guerreiro'))
        self.assertTrue(created.json()['ok'], created.content)
        character = TbPersonagem.objects.get(pk=created.json()['id'])
        character.carteira_pc = 1_000_000
        character.save(update_fields=['carteira_pc'])
        self.assertEqual(TbUsuarioConquista.objects.filter(
            user=owner, revogada_em__isnull=True).count(), 2)

        self.client.force_login(staff)
        launched = self.client.post(reverse('personagem_registrar_aventuras',
                                            args=[character.pk]), {
            'nome_aventura': 'Mesa integrada', 'aventuras': 2,
            'mestre': staff.pk, 'data_missao': '2026-09-27',
        })
        self.assertEqual(launched.status_code, 302)
        ledger = TbPersonagemAventura.objects.get(id_personagem=character, origem='mesa')

        self.client.force_login(owner)
        bought = self.client.post(reverse('personagem_comprar_item', args=[character.pk]),
                                  {'item': item.slug, 'qtd': 2},
                                  HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertTrue(bought.json()['ok'], bought.content)
        purchase = TbTransacao.objects.filter(tipo='compra').latest('pk')

        story = TbCronica.objects.create(
            titulo='Crônica integrada', slug='cronica-integrada',
            conteudo_markdown='História publicada após revisão.', autor=owner)
        self.client.force_login(staff)
        published = self.client.post(reverse('cronica_review_action', args=[story.pk]),
            data=json.dumps({'action': 'aprovar',
                             'expected_snapshot': _cronica_pending_snapshot(story)}),
            content_type='application/json')
        self.assertEqual(published.status_code, 200, published.content)
        grants = TbUsuarioConquista.objects.filter(user=owner)
        self.assertEqual(grants.count(), 6)
        self.assertEqual(grants.filter(revogada_em__isnull=True).count(), 6)
        self.assertEqual(TbEventoConquista.objects.filter(conta=owner).count(), 4)

        self.client.force_login(owner)
        profile = self.client.get(reverse('profile'))
        self.assertEqual(profile.status_code, 200)
        for key in rules:
            self.assertContains(profile, f'Marco {key}')
        inbox = self.client.get(reverse('conquista_notificacoes'))
        self.assertContains(inbox, 'Marco story')
        refunded = self.client.post(reverse('personagem_reembolsar_compra',
                                            args=[character.pk, purchase.pk]))
        self.assertEqual(refunded.status_code, 302)
        self.assertEqual(set(grants.filter(revogada_em__isnull=True).values_list(
            'conquista__slug', flat=True)),
            {'integrated-character', 'integrated-class', 'integrated-adventure',
             'integrated-story'})

        self.client.force_login(staff)
        reversed_adventure = self.client.post(reverse('personagem_reverter_aventura',
            args=[character.pk, ledger.pk]))
        self.assertEqual(reversed_adventure.status_code, 302)
        self.assertEqual(set(grants.filter(revogada_em__isnull=True).values_list(
            'conquista__slug', flat=True)),
            {'integrated-character', 'integrated-class', 'integrated-story'})
        self.assertTrue(TbUsuarioCosmetico.objects.filter(
            user=owner, cosmetico=reward, suspenso_em__isnull=True).exists())
