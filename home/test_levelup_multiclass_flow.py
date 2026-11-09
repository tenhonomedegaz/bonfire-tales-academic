"""Prospective multiclass choices use the target class without saving a level."""
from django.urls import reverse

from .models import TbClasse, TbPersonagem, TbPersonagemClasse
from .test_criador import _CriadorBase


class MulticlassFlowTests(_CriadorBase):
    def setUp(self):
        self.user = self._novo_usuario('multiclass-flow')
        self.client.force_login(self.user)
        self.fighter = TbClasse.objects.get(slug='guerreiro')
        self.mage = TbClasse.objects.get(slug='mago')
        self.person = TbPersonagem.objects.create(
            dono=self.user, nome='Multiclass flow', nivel=3, aventuras=130,
            forca=15, destreza=15, inteligencia=15, sabedoria=15, constituicao=14)
        TbPersonagemClasse.objects.create(
            id_personagem=self.person, id_classe=self.fighter, nivel=3, principal=True)
        self.url = reverse('personagem_subir_nivel', args=[self.person.pk])

    def test_new_class_choices_are_rendered_without_saving_the_multiclass(self):
        response = self.client.get(self.url, {'multiclasse': self.mage.pk})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['classe_id'], self.mage.pk)
        self.assertEqual(response.context['nivel_atual'], 3)
        self.assertEqual(response.context['nivel_alvo'], 4)
        self.assertEqual(response.context['ganhos']['classe'], self.mage.nome)
        self.assertEqual(response.context['nivel_classe_alvo'], 1)
        spells = response.context['pend_magias']
        self.assertTrue(spells and (spells['cantrips_pend'] or spells['known_pend']))
        self.assertContains(response, 'sn-multiclass')
        self.assertNotContains(response, 'As escolhas da nova classe são feitas depois')
        self.person.refresh_from_db()
        self.assertEqual(self.person.nivel, 3)
        self.assertFalse(self.person.classes.filter(id_classe=self.mage).exists())

        actions = [dict(tipo='adicionar_classe', payload={'classe': self.mage.pk}),
                   dict(tipo='aprender_magias', payload={
                       'classe': self.mage.pk,
                       'truques': [m['slug'] for m in spells['lista_truques'][:spells['cantrips_pend']]],
                       'magias': [m['slug'] for m in spells['lista_magias'][:spells['known_pend']]],
                   })]
        preview = self.client.post(reverse('personagem_levelup_preview', args=[self.person.pk]),
                                   {'acoes': actions}, content_type='application/json')
        self.assertEqual(preview.status_code, 200)
        self.assertEqual(preview.json()['erros'], [])
        self.assertEqual(preview.json()['preview']['nivel'], 4)
        self.assertFalse(self.person.classes.filter(id_classe=self.mage).exists())
        result = self.client.post(reverse('personagem_levelup_aplicar', args=[self.person.pk]),
                                  {'acoes': actions, 'request_id': 'multiclass-test'},
                                  content_type='application/json')
        self.assertEqual(result.status_code, 200, result.content)
        self.person.refresh_from_db()
        self.assertEqual(self.person.nivel, 4)
        self.assertEqual(self.person.classes.get(id_classe=self.mage).nivel, 1)
        self.assertEqual(self.person.magias.filter(origem=self.mage.nome).count(),
                         spells['cantrips_pend'] + spells['known_pend'])
        reopened = self.client.get(self.url, {'classe': self.mage.pk})
        self.assertEqual(reopened.context['nivel_classe_alvo'], 2)
        self.assertContains(reopened, 'Guerreiro Nv 3')
        self.assertContains(reopened, 'Mago Nv 2')

    def test_invalid_or_existing_class_cannot_be_added_through_page_parameters(self):
        for class_id in (self.fighter.pk, 999999, 'invalid'):
            self.assertEqual(self.client.get(self.url, {'multiclasse': class_id}).status_code, 400)
        self.assertEqual(self.person.classes.count(), 1)

    def test_existing_secondary_class_advances_its_own_level_not_total_level(self):
        secondary = TbPersonagemClasse.objects.create(
            id_personagem=self.person, id_classe=self.mage, nivel=1)
        self.person.nivel = 4
        self.person.save(update_fields=['nivel'])
        response = self.client.get(self.url, {'classe': self.mage.pk})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['classe_id'], self.mage.pk)
        self.assertEqual(response.context['nivel_alvo'], 5)
        self.assertEqual(response.context['ganhos']['classe'], self.mage.nome)
        self.assertEqual(response.context['nivel_classe_alvo'], 2)
        secondary.refresh_from_db()
        self.assertEqual(secondary.nivel, 1)
