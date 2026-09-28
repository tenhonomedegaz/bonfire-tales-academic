import hashlib
import json
import uuid
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from .hunter_catalog import compose_choice_revision
from .hunter_mark import command, panel
from .models import TbClassehabilidade, TbMagia, TbOperacaoRecurso, TbPersonagemCacador
from .versioned_classes import VersionedClassCatalog


class HunterMarkTests(TestCase):
    def setUp(self):
        from .test_hunter_spells import HunterSpellGrantTests
        self.bind = HunterSpellGrantTests.bind.__get__(self)
        HunterSpellGrantTests.setUp(self)
        self.features = {key: TbClassehabilidade.objects.create(id_classe=self.cl,
            nome='Old ' + key, niveladquirido=1,
            tags_json=['ca:+20']).pk for key in ('preparation', 'expertise')}
        self.mark_feature = TbClassehabilidade.objects.create(id_classe=self.cl,
            nome='Old mark', niveladquirido=1, tags_json=['ca:+40'])
        TbMagia.objects.filter(nome_ingles="Hunter's Mark").update(
            slug='marca-do-cacador', duracao='1 hora')
        self.bind(self.data)
        self.old = self.ruleset
        self.new = compose_choice_revision(self.old, class_id=self.cl.pk,
            feature_ids=self.features, mark_feature_id=self.mark_feature.pk)

    def activate(self):
        self.profile.ruleset = self.new
        self.profile.save(update_fields=['ruleset'])

    def post_mark(self, event, *, operation_id=None, version=None, **fields):
        self.profile.refresh_from_db()
        return self.client.post(self.url, dict(action='mark', mark_event=event,
            operation_id=operation_id or str(uuid.uuid4()),
            version=self.profile.version if version is None else version,
            confirmed='1', **fields))

    def test_exterminator_anticipation_and_inquisition_use_mark_receipts(self):
        self.activate()
        self.pc.nivel = 3
        self.pc.id_subclasse = self.subs['ordem-dos-exterminadores']
        self.pc.save(update_fields=['nivel', 'id_subclasse'])
        self.profile.refresh_from_db()
        self.assertTrue(panel(self.profile)['anticipation_eligible'])
        payload = dict(anticipate='1', target='Quimera', seconds='600',
            clue=['sangue', 'pegadas', 'testemunha'], target_type='Monstruosidade',
            same_plane='1', distance_miles='4.5')
        for invalid in (dict(clue=['sangue', 'SANGUE', 'testemunha']),
                        dict(seconds='599'), dict(distance_miles='5.1'),
                        dict(same_plane='')):
            self.assertEqual(self.post_mark('apply', **dict(payload, **invalid)).status_code, 400)
        self.profile.refresh_from_db()
        self.assertEqual((self.profile.mark, self.profile.version), ({}, 0))
        op = str(uuid.uuid4())
        self.assertEqual(self.post_mark('apply', operation_id=op, **payload).status_code, 302)
        self.profile.refresh_from_db()
        self.assertTrue(self.profile.mark['anticipated'])
        self.assertEqual(self.profile.mark['target_type'], 'Monstruosidade')
        self.assertEqual(self.post_mark('apply', operation_id=op, version=0,
                                        **payload).status_code, 302)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.version, 1)
        self.assertEqual(self.post_mark('inquisition', immunities='fogo',
            resistances='frio', vulnerabilities='radiante',
            condition_immunities='enfeitiçado').status_code, 302)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.mark['defenses']['resistances'], 'frio')
        self.assertContains(self.client.get(reverse('hunter_sheet', args=[self.person.pk])),
                            'Marca Antecipada')
        self.assertEqual(TbOperacaoRecurso.objects.count(), 2)
        self.pc.id_subclasse = self.subs['ordem-do-enxame']
        self.pc.save(update_fields=['id_subclasse'])
        self.profile.refresh_from_db()
        with self.assertRaises(ValueError):
            command(character_id=self.person.pk, owner_id=self.user.pk,
                operation_id=uuid.uuid4(), expected_version=self.profile.version,
                action='apply', target='Outro', confirmed=True, anticipate=True,
                seconds=600, clues=['a', 'b', 'c'], target_type='Fera',
                same_plane=True, distance_miles='1')

    def test_exterminator_protective_choice_is_persistent_and_conditional(self):
        from .hunter_exterminator import protective_state, choose_protective
        self.activate()
        self.pc.nivel = 6
        self.pc.id_subclasse = self.subs['ordem-dos-exterminadores']
        self.pc.save(update_fields=['nivel', 'id_subclasse'])
        self.profile.refresh_from_db()
        self.assertTrue(protective_state(self.profile)['pending'])
        self.assertContains(self.client.get(self.url), 'Contramedidas Protetivas')
        self.assertEqual(self.client.post(self.url, dict(action='protective_choice',
            version=self.profile.version, ability='wis')).status_code, 302)
        self.profile.refresh_from_db()
        self.assertEqual(protective_state(self.profile)['ability'], 'wis')
        self.assertContains(self.client.get(reverse('hunter_sheet', args=[self.person.pk])),
                            'Sabedoria escolhida')
        self.assertEqual(self.person.escolhas.filter(tipo='hunter-protective').count(), 1)
        with self.assertRaises(ValueError):
            choose_protective(character_id=self.person.pk, owner_id=self.user.pk,
                ability='int', expected_version=self.profile.version)
        with self.assertRaises(ValueError):
            choose_protective(character_id=self.person.pk, owner_id=self.user.pk,
                ability='wis', expected_version=self.profile.version - 1)
        self.pc.id_subclasse = self.subs['ordem-do-enxame']
        self.pc.save(update_fields=['id_subclasse'])
        self.profile.refresh_from_db()
        self.assertIsNone(protective_state(self.profile))

    def test_mark_replaces_target_replays_and_ends_on_declared_events(self):
        self.assertIsNone(panel(self.profile))
        self.activate()
        info = panel(self.profile)
        self.assertEqual((info['damage'], info['dispel_circle'], info['duration_seconds']),
                         ('1d6', 1, 3600))
        self.assertContains(self.client.get(self.url), 'Marcar ou substituir a presa')
        first = str(uuid.uuid4())
        self.assertEqual(self.post_mark('apply', operation_id=first, target='Dragão').status_code, 302)
        old_fingerprint = hashlib.sha256(json.dumps(
            ['hunter-mark', self.user.pk, 0, 'apply', 'Dragão', 0, True],
            ensure_ascii=False).encode()).hexdigest()
        self.assertEqual(TbOperacaoRecurso.objects.get(operation_id=first).fingerprint,
                         old_fingerprint)
        self.profile.refresh_from_db()
        self.assertEqual((self.profile.mark['target'], self.profile.mark['remaining_seconds']),
                         ('Dragão', 3600))
        self.assertEqual(self.post_mark('apply', operation_id=first, version=0,
                                        target='Dragão').status_code, 302)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.version, 1)
        self.assertEqual(self.post_mark('apply', operation_id=first, version=0,
                                        target='Outra').status_code, 400)
        self.assertEqual(self.post_mark('apply', target='Gigante').status_code, 302)
        self.profile.refresh_from_db()
        self.assertEqual((self.profile.mark['target'], self.profile.mark['active']), ('Gigante', True))
        self.assertEqual(self.post_mark('elapsed', seconds='3599').status_code, 302)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.mark['remaining_seconds'], 1)
        self.assertEqual(self.post_mark('elapsed', seconds='1').status_code, 302)
        self.profile.refresh_from_db()
        self.assertEqual((self.profile.mark['active'], self.profile.mark['reason']), (False, 'expired'))
        self.assertEqual(self.post_mark('apply', target='Besta').status_code, 302)
        self.assertEqual(self.post_mark('dead').status_code, 302)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.mark['reason'], 'dead')
        self.assertEqual(TbOperacaoRecurso.objects.count(), 6)
        self.assertEqual(self.person.recursos.count(), 0)

    def test_incapacitation_is_cumulative_until_recovery_and_level_scales(self):
        self.activate()
        self.pc.nivel = 1
        self.pc.id_subclasse = None
        self.pc.save()
        self.assertEqual(panel(self.profile)['dispel_circle'], 0)
        self.assertEqual(self.post_mark('apply', target='Alvo').status_code, 302)
        self.assertEqual(self.post_mark('incapacitated', seconds='40').status_code, 302)
        self.assertEqual(self.post_mark('incapacitated', seconds='20').status_code, 302)
        self.profile.refresh_from_db()
        self.assertTrue(self.profile.mark['active'])
        self.assertEqual(self.post_mark('recovered').status_code, 302)
        self.assertEqual(self.post_mark('incapacitated', seconds='60').status_code, 302)
        self.profile.refresh_from_db()
        self.assertTrue(self.profile.mark['active'])
        self.assertEqual(self.post_mark('incapacitated', seconds='1').status_code, 302)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.mark['reason'], 'incapacitated')
        for level, die in ((5, '1d8'), (11, '1d10'), (17, '1d12'), (20, '1d12')):
            self.pc.nivel = level
            self.pc.id_subclasse = self.sub
            self.pc.save()
            self.profile.refresh_from_db()
            self.assertEqual(panel(self.profile)['damage'], die)
        self.assertEqual(panel(self.profile)['dispel_circle'], 9)
        self.assertTrue(panel(self.profile)['during_attack'])

    def test_linked_sheet_reads_mark_without_writing(self):
        self.activate()
        self.assertEqual(self.post_mark('apply', target='Besta').status_code, 302)
        url = reverse('hunter_sheet', args=[self.person.pk])
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(url)
        self.assertContains(response, 'Presa marcada: Besta')
        self.assertContains(response, 'Registrar evento da Marca')
        self.assertFalse([q['sql'] for q in queries if q['sql'].lstrip().upper().startswith(
            ('INSERT ', 'UPDATE ', 'DELETE '))])
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_permissions_validation_rollback_and_legacy_preservation(self):
        self.activate()
        self.assertEqual(TbPersonagemCacador.objects.get(pk=self.profile.pk).mark, {})
        for fields in (dict(target=''), dict(target='X' * 161)):
            self.assertEqual(self.post_mark('apply', **fields).status_code, 400)
        self.assertEqual(self.client.post(self.url, dict(action='mark', mark_event='apply',
            target='Alvo', operation_id=str(uuid.uuid4()), version=0)).status_code, 400)
        self.assertEqual(self.post_mark('apply', target='Alvo', version=1).status_code, 400)
        self.assertEqual(self.post_mark('elapsed', seconds='1').status_code, 400)
        self.client.force_login(self.other)
        self.assertEqual(self.post_mark('apply', target='Alvo').status_code, 404)
        self.client.force_login(self.user)
        with patch('home.hunter_mark.TbOperacaoRecurso.objects.create', side_effect=RuntimeError('receipt')):
            with self.assertRaises(RuntimeError):
                command(character_id=self.person.pk, owner_id=self.user.pk,
                    operation_id=uuid.uuid4(), expected_version=0,
                    action='apply', target='Alvo', confirmed=True)
        self.profile.refresh_from_db()
        self.assertEqual((self.profile.mark, self.profile.version), ({}, 0))
        old = VersionedClassCatalog(self.old, self.cl.pk)
        new = VersionedClassCatalog(self.new, self.cl.pk)
        self.assertTrue(next(row for row in old.collections[TbClassehabilidade]
                             if row.pk == self.mark_feature.pk).tags_json)
        self.assertEqual(next(row for row in new.collections[TbClassehabilidade]
                              if row.pk == self.mark_feature.pk).tags_json, [])

    def test_command_dry_run_and_mapping_fail_closed(self):
        import json
        from .models import TbRuleset
        count = TbRuleset.objects.count()
        output = StringIO()
        call_command('compose_hunter_choices', ruleset=self.old.pk, class_id=self.cl.pk,
            preparation_id=self.features['preparation'], expertise_id=self.features['expertise'],
            mark_feature_id=self.mark_feature.pk, stdout=output)
        self.assertEqual(json.loads(output.getvalue())['checksum'], self.new.checksum)
        self.assertEqual(TbRuleset.objects.count(), count)
        self.assertEqual(compose_choice_revision(self.new, class_id=self.cl.pk,
            feature_ids=self.features, mark_feature_id=self.mark_feature.pk).pk, self.new.pk)
        with self.assertRaises(ValueError):
            compose_choice_revision(self.old, class_id=self.cl.pk,
                feature_ids=self.features, mark_feature_id=self.features['preparation'])
        with self.assertRaises(ValueError):
            compose_choice_revision(self.old, class_id=self.cl.pk,
                feature_ids=self.features, mark_feature_id=999999)
