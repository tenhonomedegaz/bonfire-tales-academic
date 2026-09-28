import uuid
from django.test import TestCase
from django.urls import reverse
from .models import TbRecursoclasse


class HunterPinnedSlotTests(TestCase):
    def setUp(self):
        from .test_hunter_spell_preparation import HunterSpellPreparationTests
        from .test_hunter_spells import HunterSpellGrantTests
        self.bind=HunterSpellGrantTests.bind.__get__(self)
        HunterSpellPreparationTests.setUp(self)
        self.table=TbRecursoclasse.objects.create(id_classe=self.cl,nome='First circle',
            slug='1o',tipo='table-only',valores_json={'1':'2','3':'4'})
        self.bind(self.data)
        self.sheet_url=reverse('hunter_sheet',args=[self.person.pk])
        self.use_url=reverse('personagem_usar_slot_magia',args=[self.person.pk])

    def test_sheet_spend_replay_stale_and_rest_use_frozen_total(self):
        response=self.client.get(self.sheet_url)
        self.assertContains(response,'Gastar espaço de nível 1')
        slot=next(s for s in response.context['spell_slots'] if s['nivel']==1)
        self.assertEqual(slot['total'],4)
        self.table.valores_json={'1':'99'};self.table.save()
        self.cl.tags_json=[];self.cl.save()
        command={'nivel':1,'acao':'gastar','operation_id':slot['gastar_operation_id'],
            'expected_version':slot['version'],'next':self.sheet_url}
        response=self.client.post(self.use_url,command,HTTP_ACCEPT='application/json')
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json()['slot']['atual'],3)
        replay=self.client.post(self.use_url,command,HTTP_ACCEPT='application/json')
        self.assertTrue(replay.json()['replayed'])
        self.assertEqual(replay.json()['slot']['atual'],3)
        command['operation_id']=str(uuid.uuid4())
        self.assertEqual(self.client.post(self.use_url,command,HTTP_ACCEPT='application/json').status_code,409)
        self.client.post(reverse('personagem_descansar',args=[self.person.pk]),{'tipo':'longo'})
        slot=next(s for s in self.client.get(self.sheet_url).context['spell_slots'] if s['nivel']==1)
        self.assertEqual((slot['atual'],slot['total']),(4,4))
        self.person.publico=True;self.person.save();self.client.force_login(self.other)
        self.assertNotContains(self.client.get(self.sheet_url),'Gastar espaço')
        self.assertEqual(self.client.post(self.use_url,command).status_code,404)
