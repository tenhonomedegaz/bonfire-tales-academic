"""Real sheet receipt for temporary HP granted by active tags."""

import uuid

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from home.epic_talent_catalog import epic_candidates
from home.models import TbPersonagem, TbPersonagemTalento, TbTalento
from home.temporary_hp import receive_tagged_temporary_hp, temporary_hp_bonus


class EpicTemporaryHpViewTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.owner = user_model.objects.create_user(username='temp-hp-owner')
        self.other = user_model.objects.create_user(username='temp-hp-other')
        self.person = TbPersonagem.objects.create(
            dono=self.owner, nome='Saúde', pv_maximo=40, pv_atual=20)
        talent = TbTalento.objects.create(
            nome='Saúde Abundante parcial', slug='saude-abundante-parcial',
            tipo='geral', tags_json=next(row['tags_json'] for row in
                epic_candidates() if row['slug'] == 'dadiva-da-saude-abundante'))
        self.grant = TbPersonagemTalento.objects.create(
            id_personagem=self.person, id_talento=talent,
            nome=talent.nome, detalhes='talent_attr:CON')
        self.url = reverse('personagem_receber_pv_temporarios', args=[self.person.pk])
        self.sheet = reverse('ficha_detail', args=[self.person.pk])

    def payload(self, operation_id=None, amount='7'):
        return {'operation_id': str(operation_id or uuid.uuid4()),
                'amount': amount, 'confirmed': 'on'}

    def test_owner_receives_bonus_replacement_replay_and_source_removal(self):
        self.client.force_login(self.owner)
        self.assertEqual(temporary_hp_bonus(self.person), 5)
        self.assertContains(self.client.get(self.sheet), 'Receber PV temporários')
        first = self.payload()
        self.assertEqual(self.client.post(self.url, first).status_code, 302)
        self.person.refresh_from_db()
        self.assertEqual(self.person.pv_temporario, 12)
        self.assertEqual(self.client.post(self.url, first).status_code, 302)
        self.person.refresh_from_db()
        self.assertEqual(self.person.pv_temporario, 12)
        self.assertEqual(self.client.post(self.url, self.payload(amount='3')).status_code, 302)
        self.person.refresh_from_db()
        self.assertEqual(self.person.pv_temporario, 12)
        self.grant.delete()
        self.assertNotContains(self.client.get(self.sheet), 'Registrar PV temporários')
        self.assertEqual(self.client.post(self.url, self.payload()).status_code, 400)

    def test_choice_owner_gate_validation_and_other_tag_coexistence(self):
        data = self.payload()
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(self.url, data).status_code, 404)
        self.client.force_login(self.owner)
        self.grant.detalhes = ''
        self.grant.save(update_fields=['detalhes'])
        self.assertEqual(temporary_hp_bonus(self.person), 0)
        self.assertEqual(self.client.post(self.url, data).status_code, 400)
        self.grant.detalhes = 'talent_attr:CON'
        self.grant.save(update_fields=['detalhes'])
        other = TbTalento.objects.create(
            nome='Outra proteção', slug='outra-protecao-temp',
            tipo='geral', tags_json=['always_active{temp_hp:+2}'])
        TbPersonagemTalento.objects.create(
            id_personagem=self.person, id_talento=other, nome=other.nome)
        self.assertEqual(temporary_hp_bonus(self.person), 7)
        result = receive_tagged_temporary_hp(
            self.person, operation_id=uuid.uuid4(), amount=10, confirmed=True)
        self.assertEqual((result['received'], result['after']), (17, 17))
        self.assertEqual(self.client.post(self.url, self.payload(amount='0')).status_code, 400)
        self.assertEqual(self.client.post(self.url, self.payload(amount='100001')).status_code, 400)
        self.assertEqual(self.client.post(self.url, {
            **data, 'confirmed': ''}).status_code, 400)
