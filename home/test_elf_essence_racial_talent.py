"""Base-race talent eligibility must not require an optional lineage."""
from django.db import transaction
from . import views
from .models import TbEssencia, TbPersonagem, TbRaca, TbTracoracial
from .racial_prerequisites import prerequisite_filter
from .test_criador import _CriadorBase


class ElfEssenceRacialTalentTests(_CriadorBase):
    def test_base_elf_talent_accepts_essence_in_initial_creator_and_levelup(self):
        user = self._novo_usuario('elf-essence-racial', staff=True)
        talent = TbTracoracial.objects.get(pk=2081)
        self.assertEqual(talent.pre_requisito, 'Elfo, Nível 1+.')
        payload = self._payload('guerreiro', raca_slug='elfo', essencia_slug='nephilim')
        payload['talento_raca'] = talent.nome
        payload.setdefault('escolhas_raca', {})['menus'] = [
            {'tipo': 'polo', 'fonte': 'Sangue Planar', 'valores': ['celestial']},
            {'tipo': 'energia', 'fonte': 'Sangue Planar', 'valores': ['lumen']},
            {'tipo': 'elemento', 'fonte': 'Sangue Planar', 'valores': ['fogo']},
        ]
        resolved, errors = views._criador_resolver(payload)
        self.assertFalse(errors, errors)
        with transaction.atomic():
            temporary = views._criador_persistir(user, payload, resolved)
            payload['magias_concedidas'] = [{
                'fonte': group['fonte'], 'slot': group['slot'],
                'magias': [option['slug'] for option in group['opcoes'][:group['qtd']]],
            } for group in temporary._criador_spell_groups]
            transaction.set_rollback(True)
        response = self._post_criar(user, payload)
        self.assertEqual(response.status_code, 200, response.content[:800])
        person = TbPersonagem.objects.get(dono=user)
        self.assertIsNone(person.id_linhagem_id)
        self.assertEqual(person.id_essencia.slug, 'nephilim')
        self.assertTrue(person.talentos.filter(nome=talent.nome, categoria='racial').exists())
        person.talentos.filter(nome=talent.nome, categoria='racial').delete()
        person.nivel = 5
        person.save(update_fields=['nivel'])
        self.assertIn(talent.nome, {option['nome'] for block in views._pendencias_talento_racial(person)
                                  for option in block['opcoes']})

    def test_lineage_specific_talent_and_unrelated_race_remain_restricted(self):
        user = self._novo_usuario('elf-essence-restrictions')
        person = TbPersonagem.objects.create(nome='Eligibility', dono=user, nivel=9,
            id_raca=TbRaca.objects.get(slug='elfo'), id_essencia=TbEssencia.objects.get(slug='nephilim'))
        accepts = prerequisite_filter(person)
        self.assertTrue(accepts(TbTracoracial.objects.get(pk=2081), 1))
        specific = TbTracoracial.objects.get(nome='Vigília Selênica')
        self.assertFalse(accepts(specific, 9))
        available = views._talentos_raciais_criador(TbRaca.objects.get(slug='anao'),
                                                  essencia=person.id_essencia)
        self.assertNotIn('Mente Velada', {row.nome for row in available})
