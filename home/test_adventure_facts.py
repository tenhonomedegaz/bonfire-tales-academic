from datetime import date

from django.contrib.auth import get_user_model
from django.urls import reverse

from home.conquistas import registrar_fato_aventura
from home.models import TbClasse, TbEventoConquista, TbPersonagem, TbPersonagemClasse
from home.test_criador import _CriadorBase
from home.views import aplicar_aventuras


class AdventureFactTests(_CriadorBase):
    def setUp(self):
        self.owner = self._novo_usuario('adventure-fact-owner')
        self.staff = self._novo_usuario('adventure-fact-staff', staff=True)
        self.character = TbPersonagem.objects.create(dono=self.owner, nome='Aventureiro', nivel=1)
        TbPersonagemClasse.objects.create(id_personagem=self.character,
            id_classe=TbClasse.objects.get(slug='guerreiro'), nivel=1, principal=True)

    def launch(self, quantity=3):
        self.client.force_login(self.staff)
        return self.client.post(reverse('personagem_registrar_aventuras', args=[self.character.pk]), {
            'nome_aventura': 'Mesa registrada', 'aventuras': quantity,
            'mestre': self.staff.pk, 'data_missao': '2026-09-27',
        })

    def test_launch_and_reversal_are_distinct_idempotent_facts(self):
        self.assertEqual(self.launch().status_code, 302)
        ledger = self.character.aventuras_ledger.get()
        recorded = TbEventoConquista.objects.get(tipo='adventure_recorded')
        self.assertEqual(recorded.conta_id, self.owner.pk)
        self.assertEqual(recorded.origem, 'site_ledger')
        self.assertEqual(recorded.payload_json, {
            'ledger_id': ledger.pk, 'quantidade': 3,
            'mestre_id': self.staff.pk, 'data_missao': date(2026, 9, 27).isoformat(),
        })
        self.assertEqual(registrar_fato_aventura(ledger).pk, recorded.pk)
        ledger.data_missao = date(2026, 9, 28)
        ledger.save(update_fields=['data_missao'])
        self.assertEqual(registrar_fato_aventura(ledger).pk, recorded.pk)
        self.assertEqual(recorded.payload_json['data_missao'], '2026-09-27')
        auditor = get_user_model().objects.create_superuser(
            'adventure-fact-auditor', 'auditor@example.invalid', 'x')
        self.client.force_login(auditor)
        audit = self.client.get(reverse('admin:home_tbeventoconquista_change', args=[recorded.pk]))
        self.assertContains(audit, recorded.chave_origem)
        self.assertContains(audit, 'quantidade')
        self.client.force_login(self.staff)

        url = reverse('personagem_reverter_aventura', args=[self.character.pk, ledger.pk])
        self.assertEqual(self.client.post(url).status_code, 302)
        reversed_fact = TbEventoConquista.objects.get(tipo='adventure_reverted')
        self.assertEqual(reversed_fact.payload_json['quantidade'], 3)
        self.assertEqual(reversed_fact.agregado_id, ledger.pk)
        self.assertEqual(TbEventoConquista.objects.count(), 2)
        self.assertEqual(self.client.post(url).status_code, 302)
        self.assertEqual(TbEventoConquista.objects.count(), 2)

    def test_failed_reversal_and_unledgered_balance_create_no_fact(self):
        self.assertEqual(self.launch(quantity=1).status_code, 302)
        ledger = self.character.aventuras_ledger.get()
        self.character.refresh_from_db()
        self.character.carteira_pc = 0
        self.character.save(update_fields=['carteira_pc'])
        response = self.client.post(reverse('personagem_reverter_aventura',
                                            args=[self.character.pk, ledger.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(TbEventoConquista.objects.filter(tipo='adventure_reverted').exists())
        self.assertEqual(TbEventoConquista.objects.filter(tipo='adventure_recorded').count(), 1)
        aplicar_aventuras(self.character, 2, registrar_ledger=False)
        self.assertEqual(TbEventoConquista.objects.count(), 1)

    def test_only_staff_launches_new_fact(self):
        self.client.force_login(self.owner)
        response = self.client.post(reverse('personagem_registrar_aventuras',
                                            args=[self.character.pk]), {
            'nome_aventura': 'Não autorizada', 'aventuras': 2,
            'mestre': self.staff.pk,
        })
        self.assertEqual(response.status_code, 404)
        self.assertFalse(TbEventoConquista.objects.exists())
