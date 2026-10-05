from io import StringIO

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone

from home.conquista_admin_form import ConquistaAdminForm
from home.conquistas import registrar_fato_aventura
from home.models import (TbClasse, TbConquista, TbCosmetico, TbEventoConquista,
                         TbPersonagem, TbPersonagemAventura, TbPersonagemClasse,
                         TbUsuarioConquista, TbUsuarioCosmetico)
from home.test_criador import _CriadorBase


class AdventuresAchievementTests(_CriadorBase):
    def setUp(self):
        super().setUp()
        self.owner = self._novo_usuario('adventures-achievement-owner')
        self.staff = self._novo_usuario('adventures-achievement-staff', staff=True)
        self.character = TbPersonagem.objects.create(
            dono=self.owner, nome='Aventureiro', nivel=1)
        TbPersonagemClasse.objects.create(
            id_personagem=self.character,
            id_classe=TbClasse.objects.get(slug='guerreiro'), nivel=1, principal=True)
        self.badge = TbCosmetico.objects.create(
            slug='badge-aventuras-qa', nome='Mesas verificadas QA',
            tipo='badge', origem='conquista')
        self.definition = {
            'schema_version': 1, 'metric': 'adventures_played',
            'scope': 'account', 'aggregate': 'sum',
            'filters': {'valid': True, 'origin': 'played_session'},
            'operator': 'gte', 'target': 3,
        }
        self.rule = TbConquista(
            slug='aventuras-verificadas-qa', nome='Aventuras verificadas QA',
            criterio='automatico', criterio_json=self.definition,
            recompensa=self.badge)
        self.rule.full_clean()
        self.rule.save()

    def launch(self, quantity):
        self.client.force_login(self.staff)
        return self.client.post(
            reverse('personagem_registrar_aventuras', args=[self.character.pk]), {
                'nome_aventura': 'Mesa verificada QA', 'aventuras': quantity,
                'mestre': self.staff.pk, 'data_missao': '2026-09-27',
            })

    def test_staff_ledger_counts_units_once_and_reversal_removes_support(self):
        self.definition = {**self.definition, 'operator': 'gt', 'target': 2}
        self.rule.criterio_json = self.definition
        self.rule.full_clean()
        self.rule.save(update_fields=['criterio_json'])
        community = TbPersonagemAventura.objects.create(
            id_personagem=self.character, nome_aventura='Recompensa social QA',
            origem='recompensa_comunidade', qtd_aventuras=10)
        with self.assertRaises(ValueError):
            registrar_fato_aventura(community)
        self.assertEqual(self.launch(2).status_code, 302)
        self.assertFalse(TbUsuarioConquista.objects.filter(
            user=self.owner, conquista=self.rule).exists())
        self.assertEqual(self.launch(1).status_code, 302)
        grant = TbUsuarioConquista.objects.get(user=self.owner, conquista=self.rule)
        self.assertIsNone(grant.revogada_em)
        self.assertEqual(grant.evidencia_json['total'], 3)
        self.assertEqual(len(grant.evidencia_json['lancamento_ids']), 2)
        self.assertEqual(grant.definicao_json, self.definition)
        self.assertEqual(TbUsuarioCosmetico.objects.filter(
            user=self.owner, cosmetico=self.badge, suspenso_em__isnull=True).count(), 1)

        ledger = TbPersonagemAventura.objects.filter(origem='mesa').order_by('pk').last()
        recorded = TbEventoConquista.objects.filter(tipo='adventure_recorded').count()
        registrar_fato_aventura(ledger)
        self.assertEqual(TbEventoConquista.objects.filter(
            tipo='adventure_recorded').count(), recorded)
        self.assertEqual(TbUsuarioConquista.objects.filter(
            user=self.owner, conquista=self.rule, revogada_em__isnull=True).count(), 1)

        self.client.force_login(self.staff)
        self.assertEqual(self.client.post(reverse(
            'personagem_reverter_aventura', args=[self.character.pk, ledger.pk]
        )).status_code, 302)
        grant.refresh_from_db()
        self.assertIsNotNone(grant.revogada_em)
        self.assertTrue(TbUsuarioCosmetico.objects.filter(
            user=self.owner, cosmetico=self.badge,
            suspenso_em__isnull=False).exists())

    def test_admin_requires_explicit_comparator_and_threshold(self):
        admin = get_user_model().objects.create_superuser(
            'adventures-rule-admin', 'adventures-rule@example.invalid', 'x')
        self.client.force_login(admin)
        self.assertContains(self.client.get(reverse('admin:home_tbconquista_add')),
                            'Aventuras de mesa comprovadas')
        data = {'slug': 'adventures-assisted-qa', 'nome': 'Aventuras assistidas QA',
                'criterio': 'automatico', 'criterio_json': '{}', 'ativo': 'on',
                'ordem': '0',
                'metrica_assistida': 'adventures_played',
                'operador_unidades': 'gt', 'alvo_unidades': '3'}
        form = ConquistaAdminForm(data=data)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.save().criterio_json,
                         {**self.definition, 'operator': 'gt'})
        missing = ConquistaAdminForm(data={**data, 'slug': 'adventures-missing-qa',
                                          'alvo_unidades': ''})
        self.assertIn('alvo_unidades', missing.errors)
        invalid = TbConquista(slug='adventures-invalid-qa', nome='Inválida QA',
                              criterio='automatico', criterio_json={
                                  **self.definition, 'filters': {'valid': True}})
        with self.assertRaises(ValidationError):
            invalid.full_clean()

    def test_owner_sees_verified_progress_without_exposing_it_publicly(self):
        self.assertEqual(self.launch(2).status_code, 302)
        self.client.force_login(self.owner)
        editor = self.client.get(reverse('profile'))
        self.assertContains(editor, '2 comprovadas')
        self.assertContains(editor, 'meta: pelo menos 3')

        url = reverse('public_profile', args=[self.owner.username])
        self.assertContains(self.client.get(url), '2 comprovadas')
        self.client.logout()
        self.assertNotContains(self.client.get(url), '2 comprovadas')
        self.client.force_login(self.staff)
        self.assertContains(self.client.get(url), '2 comprovadas')

    def test_legacy_explicit_ledger_can_be_previewed_and_replayed_once(self):
        ledger = TbPersonagemAventura.objects.create(
            id_personagem=self.character, nome_aventura='Mesa antiga QA',
            origem='mesa', qtd_aventuras=3)
        output = StringIO()
        call_command('reprocessar_aventuras_jogadas', user_id=self.owner.pk,
                     stdout=output)
        self.assertIn('fatos_novos=1', output.getvalue())
        self.assertFalse(TbEventoConquista.objects.exists())
        self.assertFalse(TbUsuarioConquista.objects.filter(
            user=self.owner, conquista=self.rule).exists())

        output = StringIO()
        call_command('reprocessar_aventuras_jogadas', apply=True,
                     user_id=self.owner.pk, stdout=output)
        self.assertIn('fatos_novos=1', output.getvalue())
        self.assertEqual(TbEventoConquista.objects.filter(
            agregado_id=ledger.pk, tipo='adventure_recorded').count(), 1)
        self.assertEqual(TbUsuarioConquista.objects.get(
            user=self.owner, conquista=self.rule).evidencia_json['total'], 3)

        output = StringIO()
        call_command('reprocessar_aventuras_jogadas', apply=True,
                     user_id=self.owner.pk, stdout=output)
        self.assertIn('fatos_novos=0', output.getvalue())
        self.assertEqual(TbUsuarioConquista.objects.filter(
            user=self.owner, conquista=self.rule).count(), 1)

    def test_replay_revokes_stale_grant_without_active_ledger(self):
        self.assertEqual(self.launch(3).status_code, 302)
        grant = TbUsuarioConquista.objects.get(user=self.owner, conquista=self.rule)
        ledger = TbPersonagemAventura.objects.get(origem='mesa')
        ledger.revertido = True
        ledger.revertido_em = timezone.now()
        ledger.save(update_fields=['revertido', 'revertido_em'])

        output = StringIO()
        call_command('reprocessar_aventuras_jogadas', user_id=self.owner.pk,
                     stdout=output)
        self.assertIn('lancamentos=0 fatos_novos=0 contas=1', output.getvalue())
        grant.refresh_from_db()
        self.assertIsNone(grant.revogada_em)

        output = StringIO()
        call_command('reprocessar_aventuras_jogadas', apply=True,
                     user_id=self.owner.pk, stdout=output)
        self.assertIn('lancamentos=0 fatos_novos=0 contas=1', output.getvalue())
        grant.refresh_from_db()
        self.assertIsNotNone(grant.revogada_em)
        self.assertTrue(TbUsuarioCosmetico.objects.filter(
            user=self.owner, cosmetico=self.badge,
            suspenso_em__isnull=False).exists())

        call_command('reprocessar_aventuras_jogadas', apply=True,
                     user_id=self.owner.pk, stdout=StringIO())
        self.assertEqual(TbUsuarioConquista.objects.filter(
            user=self.owner, conquista=self.rule).count(), 1)
