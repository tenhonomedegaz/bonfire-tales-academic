import json
import uuid
from io import StringIO

from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from .hunter_catalog import compose_choice_revision, compose_order_revision
from .hunter_mark import command, panel
from .hunter_exorcist import command as reaper_command, panel as reaper_panel
from .models import TbPersonagem


class HunterMortuaryTests(TestCase):
    def setUp(self):
        from .test_hunter_mark import HunterMarkTests
        from .hunter_rework import catalog
        HunterMarkTests.setUp(self)
        self.data['spellcasting_progression'] = catalog()['spellcasting_progression']
        self.bind(self.data)
        self.new = compose_choice_revision(self.ruleset, class_id=self.cl.pk,
            feature_ids=self.features, mark_feature_id=self.mark_feature.pk)
        output = StringIO()
        call_command('prepare_hunter_orders', apply=True, stdout=output)
        orders = json.loads(output.getvalue())['order_ids']
        self.profile.ruleset = compose_order_revision(self.new, class_id=self.cl.pk,
                                                       order_ids=orders)
        self.profile.save(update_fields=['ruleset'])
        self.pc.id_subclasse_id = orders['ordem-dos-exorcistas']
        self.pc.save(update_fields=['id_subclasse'])
        self.profile.refresh_from_db()

    def post_mark(self, event, **fields):
        self.profile.refresh_from_db()
        data = dict(action='mark', mark_event=event, operation_id=str(uuid.uuid4()),
                    version=self.profile.version, confirmed='1')
        data.update(fields)
        return self.client.post(self.url, data)

    @override_settings(HUNTER_CREATOR_RULESET_CHECKSUM='')
    def test_mortuary_choice_is_pinned_and_visible_in_sheet(self):
        self.assertTrue(panel(self.profile)['mortuary_eligible'])
        from .hunter_rework import prepare
        from .hunter_combat import evaluate
        prepared = prepare(level=3, ability='wis', order='ordem-dos-exorcistas', selected=[])
        self.assertEqual(evaluate(prepared, marked=True, injured=True)['mortuary_bleeding_bonus'], 2)
        self.assertEqual(evaluate(prepared, marked=True, injured=False)['mortuary_bleeding_bonus'], 0)
        self.assertContains(self.client.get(reverse('hunter_laboratory'), {
            'level': 3, 'order': 'ordem-dos-exorcistas', 'marked': '1',
            'injured': '1'}), 'Marca Mortuária dos Exorcistas')
        self.assertEqual(self.post_mark('apply', target='Espectro').status_code, 400)
        self.assertFalse(self.profile.__class__.objects.get(pk=self.profile.pk).mark)
        self.assertEqual(self.post_mark('apply', target='Espectro',
            mortuary_damage_type='radiante').status_code, 302)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.mark['mortuary_damage_type'], 'radiante')
        info = panel(self.profile)
        self.assertEqual(info['mortuary_bleeding_bonus'], 2)
        sheet = self.client.get(reverse('hunter_sheet', args=[self.person.pk]))
        self.assertContains(sheet, 'Marca Mortuária')
        self.assertContains(sheet, 'radiante')
        self.assertEqual(self.post_mark('apply', target='Outra',
            mortuary_damage_type='frio').status_code, 302)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.mark['mortuary_damage_type'], 'frio')
        self.assertEqual(self.post_mark('dead').status_code, 302)
        self.profile.refresh_from_db()
        self.assertIsNone(panel(self.profile)['mortuary_damage_type'])

    def test_replay_rejects_modified_choice_and_legacy_cannot_select_it(self):
        op = uuid.uuid4()
        args = dict(character_id=self.person.pk, owner_id=self.user.pk,
                    operation_id=op, expected_version=self.profile.version,
                    action='apply', target='Alvo', confirmed=True,
                    mortuary_damage_type='frio')
        first = command(**args)
        self.assertEqual(first['mortuary_damage_type'], 'frio')
        self.assertEqual(command(**args), first)
        with self.assertRaises(ValueError):
            command(**dict(args, mortuary_damage_type='radiante'))
        self.profile.refresh_from_db()
        self.pc.id_subclasse = self.subs['ordem-do-enxame']
        self.pc.save(update_fields=['id_subclasse'])
        self.profile.refresh_from_db()
        self.assertFalse(panel(self.profile)['mortuary_eligible'])
        with self.assertRaises(ValueError):
            command(**dict(args, operation_id=uuid.uuid4(),
                           expected_version=self.profile.version))

    def reaper(self, action, *, operation_id=None, version=None, **changes):
        self.profile.refresh_from_db()
        args = dict(character_id=self.person.pk, owner_id=self.user.pk,
                    operation_id=operation_id or uuid.uuid4(),
                    expected_version=self.profile.version if version is None else version,
                    action=action, confirmed=True, mode='', slot_level=0,
                    slot_version='', seconds=0)
        args.update(changes)
        return reaper_command(**args)

    def test_reaper_form_http_replay_duration_and_rest(self):
        self.pc.nivel = 6
        self.pc.save(update_fields=['nivel'])
        self.profile.refresh_from_db()
        self.assertTrue(reaper_panel(self.profile)['free_ready'])
        op = str(uuid.uuid4())
        response = self.client.post(self.url, dict(action='reaper_form',
            reaper_event='activate', mode='free', operation_id=op,
            version=self.profile.version, confirmed='1'))
        self.assertEqual(response.status_code, 302)
        self.profile.refresh_from_db()
        self.assertTrue(self.profile.exorcist['active'])
        self.assertEqual(self.reaper('activate', operation_id=op, version=0,
                                     mode='free')['remaining_seconds'], 60)
        with self.assertRaises(ValueError):
            self.reaper('activate', operation_id=op, version=0, mode='secrets')
        with self.assertRaises(ValueError):
            self.reaper('activate', mode='free', version=0)
        self.assertContains(self.client.get(reverse('hunter_sheet', args=[self.person.pk])),
                            'Forma do Ceifador')
        self.assertEqual(self.reaper('elapsed', seconds=30)['remaining_seconds'], 30)
        self.profile.refresh_from_db()
        self.assertFalse(self.reaper('elapsed', seconds=30)['active'])
        with self.assertRaises(ValueError):
            self.reaper('activate', mode='free')
        self.client.post(reverse('personagem_descansar', args=[self.person.pk]),
                         {'tipo': 'curto', 'next': self.url})
        self.profile.refresh_from_db()
        self.assertFalse(reaper_panel(self.profile)['free_ready'])
        self.client.post(reverse('personagem_descansar', args=[self.person.pk]),
                         {'tipo': 'longo', 'next': self.url})
        self.profile.refresh_from_db()
        self.assertTrue(reaper_panel(self.profile)['free_ready'])

    def test_reaper_paid_paths_and_order_gate(self):
        self.pc.nivel = 14
        self.pc.save(update_fields=['nivel'])
        self.profile.refresh_from_db()
        current = reaper_panel(self.profile)
        self.assertTrue(current['immortal'])
        with self.assertRaises(TbPersonagem.DoesNotExist):
            self.reaper('activate', mode='secrets', owner_id=self.user.pk + 500)
        with self.assertRaises(ValueError):
            self.reaper('activate', mode='secrets', confirmed=False)
        self.profile.refresh_from_db()
        self.assertFalse(self.profile.exorcist)
        self.reaper('activate', mode='secrets')
        resource = self.person.recursos.get(chave=f'hunter:{self.profile.pk}:secrets')
        self.assertEqual(resource.maximo - resource.atual, 2)
        self.profile.refresh_from_db()
        self.reaper('dismiss')
        self.profile.refresh_from_db()
        current = reaper_panel(self.profile)
        self.assertTrue(current['slot_options'])
        slot = next(s for s in current['slot_options'] if s['atual'])
        self.reaper('activate', mode='slot', slot_level=slot['nivel'],
                    slot_version=slot['version'])
        self.person.refresh_from_db()
        from .resource_engine import canonical_key
        slot_resource = self.person.recursos.get(
            chave=canonical_key(f'spell-slot:{slot["nivel"]}'))
        self.assertEqual(slot_resource.maximo - slot_resource.atual, 1)
        self.profile.refresh_from_db()
        self.reaper('dismiss')
        self.pc.id_subclasse = self.subs['ordem-do-enxame']
        self.pc.save(update_fields=['id_subclasse'])
        self.profile.refresh_from_db()
        self.assertIsNone(reaper_panel(self.profile))
        with self.assertRaises(ValueError):
            self.reaper('activate', mode='free')
