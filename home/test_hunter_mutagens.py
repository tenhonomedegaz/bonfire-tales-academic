import uuid
from django.test import TestCase
from django.urls import reverse
from .hunter_mutagens import command, panel


class HunterMutagenTests(TestCase):
    def setUp(self):
        from .test_hunter_mortuary import HunterMortuaryTests
        import json
        from io import StringIO
        from django.core.management import call_command
        HunterMortuaryTests.setUp(self)
        output = StringIO()
        call_command('prepare_hunter_orders', apply=True, stdout=output)
        self.pc.id_subclasse_id = json.loads(output.getvalue())['order_ids']['ordem-dos-mutantes']
        self.pc.save(update_fields=['id_subclasse'])
        self.profile.refresh_from_db()

    def execute(self, action, **changes):
        self.profile.refresh_from_db()
        args = dict(character_id=self.person.pk, owner_id=self.user.pk,
                    operation_id=uuid.uuid4(), expected_version=self.profile.version,
                    action=action, confirmed=True)
        args.update(changes)
        return command(**args)

    def learn(self):
        self.profile.refresh_from_db()
        info = panel(self.profile)
        choices = [row['id'] for row in info['options'][:info['known_max']]]
        self.execute('learn', selected=choices)
        return choices

    def test_cheetah_concentration_guard_and_expiring_suppression(self):
        from .models import TbMagia
        from .resource_engine import activate_state
        self.pc.nivel = 6
        self.pc.save(update_fields=['nivel'])
        self.profile.mutagens = dict(active=['guepardo-das-planicies'])
        self.profile.save(update_fields=['mutagens'])
        spell = TbMagia.objects.create(nome='Ritual concentrado de teste', slug='ritual-concentrado-teste',
            nivel=1, ritual=True, concentracao=True, duracao='Até ser dissipado')
        owned = self.person.magias.create(id_magia=spell, nome=spell.nome, nivel=1, preparada=True)
        url = reverse('oficina_conjurar_magia', args=[self.person.pk])
        post = dict(personagem=self.person.pk, magia_personagem=owned.pk, ritual='1')
        before = self.person.transacoes.count()
        response = self.client.post(url, post)
        self.assertIn('concentracao_bloqueada', response['Location'])
        self.assertEqual(self.person.transacoes.count(), before)
        self.assertFalse(self.person.estados.filter(ativo=True).exists())
        from .spell_access import set_spell_class_access
        from .models import TbClasse, TbClassehabilidade, TbPersonagemClasse
        caster_class = TbClasse.objects.create(nome='Conjurador da Oficina', slug='conjurador-oficina')
        TbClassehabilidade.objects.create(id_classe=caster_class, nome='Conjuração', niveladquirido=1,
            tags_json=['spellcasting{ability:int, slots{progression:full}, list:conjurador-oficina, mode:prepared, pool:spellbook}'])
        TbPersonagemClasse.objects.create(id_personagem=self.person, id_classe=caster_class, nivel=1)
        set_spell_class_access(spell, [caster_class], save=True)
        scroll = self.person.inventario.create(nome='Pergaminho concentrado', qtd=1,
            origem_tipo='oficina', tags_json=[
                'spell_scroll{spell:ritual_concentrado_teste, level:1}', 'consumable'])
        response = self.client.post(reverse('oficina_usar_pergaminho', args=[self.person.pk]),
            dict(personagem=self.person.pk, item=scroll.pk))
        self.assertIn('concentracao_bloqueada', response['Location'])
        scroll.refresh_from_db()
        self.assertEqual(scroll.qtd, 1)
        self.assertEqual(self.person.transacoes.count(), before)
        self.execute('suppress', formula='guepardo-das-planicies')
        response = self.client.post(url, post)
        self.assertIn('status=conjurada', response['Location'])
        self.assertTrue(self.person.estados.get(chave=f'spell:{owned.pk}').ativo)
        activate_state(self.person, 'spell:other', origin='magia:other', payload={'concentration': False})
        self.execute('elapsed', seconds=60)
        self.assertFalse(self.person.estados.get(chave=f'spell:{owned.pk}').ativo)
        self.assertTrue(self.person.estados.get(chave='spell:other').ativo)
        self.execute('purge')
        self.assertIn('status=conjurada', self.client.post(url, post)['Location'])

    def test_stigma_transfer_shape_save_end_and_receipts(self):
        from .character_engine import derive
        self.pc.nivel = 10
        self.pc.save(update_fields=['nivel'])
        self.profile.mutagens = dict(active=['salamandra-ignea', 'kraken-onisciente'])
        self.profile.mark = dict(active=True, remaining_seconds=3600, target='Presa')
        self.profile.save(update_fields=['mutagens', 'mark'])
        with self.assertRaises(ValueError):
            self.execute('stigma_transfer', formula='salamandra-ignea', target='Presa',
                         turn_key='combate:2', critical=False, attack_kind='weapon')
        op, version = uuid.uuid4(), self.profile.version
        args = dict(formula='salamandra-ignea', target='Presa', turn_key='combate:2',
                    critical=True, attack_kind='weapon', operation_id=op, expected_version=version)
        result = self.execute('stigma_transfer', **args)
        self.assertEqual(result, self.execute('stigma_transfer', **args))
        sheet = derive(self.person, ruleset=self.profile.ruleset)
        self.assertNotIn('frio', sheet.get('vulnerabilidades', []))
        self.assertIn('fogo', sheet['resistencias'])
        with self.assertRaises(ValueError):
            self.execute('stigma_end', formula='salamandra-ignea', turn_key='outro')
        self.execute('stigma_end', formula='salamandra-ignea', turn_key='combate:2')
        self.assertIn('frio', derive(self.person, ruleset=self.profile.ruleset)['vulnerabilidades'])
        with self.assertRaises(ValueError):
            self.execute('stigma_transfer', formula='salamandra-ignea', target='Presa',
                         turn_key='3', critical=True, attack_kind='unarmed')
        result = self.execute('stigma_shape', target='Presa', save_total=-10)
        self.assertFalse(result['last_stigma_shape']['allowed'])
        dc = result['last_stigma_shape']['dc']
        result = self.execute('stigma_shape', target='Presa', save_total=dc)
        self.assertTrue(result['last_stigma_shape']['allowed'])
        with self.assertRaises(ValueError):
            self.execute('stigma_shape', target='Outra', save_total=dc)
        self.profile.refresh_from_db()
        response = self.client.post(self.url, dict(action='mutagens', mutagen_event='stigma_transfer',
            version=self.profile.version, operation_id=str(uuid.uuid4()), confirmed='1',
            formula='kraken-onisciente', mutagen_target='Favorito', mutagen_turn='combate:4',
            mutagen_critical='1', mutagen_favored='1', mutagen_attack_kind='unarmed'))
        self.assertEqual(response.status_code, 302)
        self.profile.refresh_from_db()
        self.assertTrue(self.profile.mutagens['stigma_transfers']['kraken-onisciente']['active'])
        self.assertContains(self.client.get(self.url), 'Favorito')

    def test_suppression_all_formulas_and_recovery_lifecycle(self):
        from .character_engine import derive
        self.pc.nivel = 18
        self.pc.save(update_fields=['nivel'])
        self.profile.refresh_from_db()
        options = panel(self.profile)['options']
        # Every formula's derived penalties must match their suspension in Chimera,
        # while retaining the ordinary formula's active state and toxicity count.
        for row in options:
            with self.subTest(formula=row['id']):
                self.profile.mutagens = dict(active=[row['id']], harpy_seconds=3600,
                    lizard_seconds=3600, suppressed={row['id']: 60})
                self.profile.save(update_fields=['mutagens'])
                suppressed = derive(self.person, ruleset=self.profile.ruleset)
                self.profile.mutagens = dict(active=[row['id']], chimera_seconds=60)
                self.profile.save(update_fields=['mutagens'])
                chimera = derive(self.person, ruleset=self.profile.ruleset)
                for key in ('atributos', 'saves', 'pericias', 'resistencias', 'vulnerabilidades',
                            'desvantagens_impostas', 'velocidade'):
                    self.assertEqual(suppressed.get(key), chimera.get(key), key)
                self.assertIn('veneno', suppressed['imunidades'])
        self.profile.mutagens = dict(active=['salamandra-ignea', 'kraken-onisciente'])
        self.profile.save(update_fields=['mutagens'])
        op = uuid.uuid4()
        version = self.profile.version
        result = self.execute('suppress', formula='salamandra-ignea', operation_id=op, expected_version=version)
        self.assertEqual(result, self.execute('suppress', formula='salamandra-ignea', operation_id=op, expected_version=version))
        with self.assertRaises(ValueError):
            self.execute('suppress', formula='kraken-onisciente')
        self.execute('recover_suppression')
        resource = self.person.recursos.get(chave=f'hunter:{self.profile.pk}:secrets')
        self.assertEqual(resource.maximo - resource.atual, 2)
        self.execute('suppress', formula='kraken-onisciente')
        self.profile.refresh_from_db()
        self.assertEqual(len(self.profile.mutagens['suppressed']), 2)
        self.assertContains(self.client.get(self.url), 'suprimido por 60 segundos')
        self.execute('elapsed', seconds=60)
        self.assertIn('frio', derive(self.person, ruleset=self.profile.ruleset)['vulnerabilidades'])
        self.client.post(reverse('personagem_descansar', args=[self.person.pk]), {'tipo': 'curto'})
        self.profile.refresh_from_db()
        self.assertTrue(self.profile.mutagens['suppression_used'])
        self.client.post(reverse('personagem_descansar', args=[self.person.pk]), {'tipo': 'longo'})
        self.profile.refresh_from_db()
        self.assertFalse(self.profile.mutagens['suppression_used'])

    def test_transfusion_hit_mark_turn_limit_and_damage_scaling(self):
        self.pc.nivel = 18
        self.pc.save(update_fields=['nivel'])
        choices = self.learn()
        self.execute('prepare', selected=choices[:3])
        self.execute('consume', formula=choices[0])
        self.profile.refresh_from_db()
        self.profile.mark = dict(active=True, target='Presa A', remaining_seconds=3600)
        self.profile.save(update_fields=['mark'])
        version, operation = self.profile.version, uuid.uuid4()
        args = dict(target='Presa A', turn_key='sessao:combate:1', damage_type='veneno',
                    expected_version=version, operation_id=operation)
        result = self.execute('transfusion_hit', **args)
        self.assertEqual(result['last_transfusion_hit']['dice'], '1d4')
        self.assertEqual(self.execute('transfusion_hit', **args), result)
        for changes in (dict(target='Outra'), dict(damage_type='fogo'), dict(turn_key='')):
            invalid = dict(target='Presa A', turn_key='novo', damage_type='veneno')
            invalid.update(changes)
            with self.assertRaises(ValueError):
                self.execute('transfusion_hit', **invalid)
        with self.assertRaises(ValueError):
            self.execute('transfusion_hit', target='Presa A', turn_key='sessao:combate:1', damage_type='cortante')
        for formula in choices[1:3]:
            self.execute('consume', formula=formula)
        self.profile.refresh_from_db()
        response = self.client.post(self.url, dict(action='mutagens', mutagen_event='transfusion_hit',
            confirmed='1', version=self.profile.version, operation_id=str(uuid.uuid4()),
            mutagen_target='Presa A', mutagen_turn='sessao:combate:2', mutagen_damage_type='necrotico'))
        self.assertEqual(response.status_code, 302)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.mutagens['last_transfusion_hit']['dice'], '3d4')
        self.assertContains(self.client.get(reverse('hunter_sheet', args=[self.person.pk])), '3d4 de dano necrotico')
        self.profile.mark['active'] = False
        self.profile.save(update_fields=['mark'])
        with self.assertRaises(ValueError):
            self.execute('transfusion_hit', target='Presa A', turn_key='3', damage_type='veneno')
        self.profile.refresh_from_db()
        self.profile.mark['active'] = True
        self.profile.save(update_fields=['mark'])
        self.execute('purge')
        with self.assertRaises(ValueError):
            self.execute('transfusion_hit', target='Presa A', turn_key='3', damage_type='veneno')

    def test_transfusion_atomic_replacement_receipt_and_long_rest(self):
        self.pc.nivel = 14
        self.pc.save(update_fields=['nivel'])
        known = ['harpia-das-montanhas', 'lagartixa-cicatrizante',
                 'salamandra-ignea', 'yeti-boreal', 'kraken-onisciente', 'esfinge-visionaria']
        self.execute('learn', selected=known)
        self.execute('prepare', selected=known[:2])
        self.execute('consume', formula=known[0])
        self.profile.refresh_from_db()
        version = self.profile.version
        operation = uuid.uuid4()
        result = self.execute('transfuse', formula=known[1], replaced_formula=known[0],
                              operation_id=operation, expected_version=version)
        self.assertEqual(result['active'], [known[1]])
        self.assertEqual(result['prepared'], [])
        self.assertEqual(result['harpy_seconds'], 0)
        self.assertEqual(result['lizard_seconds'], 3600)
        self.assertEqual(result['transfusion_used'], 1)
        self.assertEqual(result, self.execute('transfuse', formula=known[1], replaced_formula=known[0],
                         operation_id=operation, expected_version=version))
        with self.assertRaises(ValueError):
            self.execute('transfuse', formula=known[1], replaced_formula=known[1],
                         operation_id=operation, expected_version=version)
        self.client.post(reverse('personagem_descansar', args=[self.person.pk]), {'tipo': 'curto', 'next': self.url})
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.mutagens['transfusion_used'], 1)
        self.execute('prepare', selected=known[:2])
        self.execute('consume', formula=known[0])
        self.profile.refresh_from_db()
        self.profile.mutagens['transfusion_used'] = 999
        self.profile.save(update_fields=['mutagens'])
        before = dict(self.profile.mutagens)
        with self.assertRaises(ValueError):
            self.execute('transfuse', formula=known[1], replaced_formula=known[0])
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.mutagens, before)
        self.client.post(reverse('personagem_descansar', args=[self.person.pk]), {'tipo': 'longo', 'next': self.url})
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.mutagens['transfusion_used'], 0)
        self.assertContains(self.client.get(self.url), 'Efeito a encerrar na Transfusão')
        self.execute('prepare', selected=known[:2])
        self.execute('consume', formula=known[0])
        self.profile.refresh_from_db()
        response = self.client.post(self.url, dict(action='mutagens', mutagen_event='transfuse',
            version=self.profile.version, operation_id=str(uuid.uuid4()), confirmed='1',
            formula=known[1], replaced_formula=known[0]))
        self.assertEqual(response.status_code, 302)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.mutagens['active'], [known[1]])

    def test_manticore_chaos_attack_and_save_effects_lifecycle(self):
        from .character_engine import derive
        from .hunter_mutagens import apply_checks
        self.pc.nivel = 18
        self.pc.save(update_fields=['nivel'])
        known = ['manticora-raivosa', 'quimera-do-caos', 'salamandra-ignea',
                 'yeti-boreal', 'kraken-onisciente', 'esfinge-visionaria',
                 'raptor-sombrio', 'gorgona-prateada']
        self.execute('learn', selected=known)
        baseline = derive(self.person, ruleset=self.profile.ruleset)
        self.execute('prepare', selected=known[:2])
        for formula in known[:2]:
            self.execute('consume', formula=formula)
        sheet = derive(self.person, ruleset=self.profile.ruleset)
        self.assertTrue(sheet['mutagen_bonus_attack'])
        self.assertEqual(sheet['ataques']['quantidade'], baseline['ataques']['quantidade'])
        self.assertEqual(sheet['mutagen_weapon_critical'], 19)
        self.assertTrue(sheet['mutagen_mental_save_disadvantage'])
        for attr, save in sheet['saves'].items():
            self.assertEqual(save['bonus'], baseline['saves'][attr]['bonus'])
            self.assertEqual(bool(save.get('mutagen_conditions')), attr in ('INT', 'SAB', 'CAR'))
        # Only weapon profiles gain the range; a better existing range survives.
        from copy import deepcopy
        sample = deepcopy(baseline)
        sample['ataques']['perfis'] = [dict(escopo='weapon-melee'),
            dict(escopo='weapon-ranged', critical_min=18), dict(escopo='unarmed-strike'),
            dict(escopo='off_hand')]
        apply_checks(self.person, self.profile.ruleset, sample)
        self.assertEqual(sample['ataques']['perfis'][0]['critical_min'], 19)
        self.assertEqual(sample['ataques']['perfis'][1]['critical_min'], 18)
        self.assertNotIn('critical_min', sample['ataques']['perfis'][2])
        self.assertEqual(sample['ataques']['perfis'][3]['critical_min'], 19)
        self.assertNotIn('mutagen_bonus_attack', derive(self.person))
        response = self.client.get(reverse('hunter_sheet', args=[self.person.pk]))
        self.assertContains(response, 'crítico com 19 ou 20')
        self.assertContains(response, 'ataque adicional como Ação Bônus')
        self.assertContains(response, 'Desvantagem — Manticora Raivosa')
        self.execute('purge')
        clean = derive(self.person, ruleset=self.profile.ruleset)
        self.assertEqual(clean['saves'], baseline['saves'])
        self.assertNotIn('mutagen_weapon_critical', clean)
        self.client.post(reverse('personagem_descansar', args=[self.person.pk]), {'tipo': 'longo', 'next': self.url})
        self.execute('prepare', selected=known[:2])
        self.execute('chimera', movement='voo', resistances=['fogo', 'frio'])
        sheet = derive(self.person, ruleset=self.profile.ruleset)
        self.assertTrue(sheet['mutagen_bonus_attack'])
        self.assertEqual(sheet['mutagen_weapon_critical'], 19)
        self.assertFalse(sheet.get('mutagen_mental_save_disadvantage'))
        self.assertEqual(sheet['saves'], baseline['saves'])
        self.execute('elapsed', seconds=60)
        self.assertNotIn('mutagen_bonus_attack', derive(self.person, ruleset=self.profile.ruleset))

    def test_wolf_chameleon_checks_preserve_expertise_and_optional_modifiers(self):
        from .character_engine import derive
        from .models import TbPersonagemPericia
        self.pc.nivel = 18
        self.pc.save(update_fields=['nivel'])
        self.person.inteligencia = 18
        self.person.sabedoria = 14
        self.person.save(update_fields=['inteligencia', 'sabedoria'])
        TbPersonagemPericia.objects.update_or_create(
            id_personagem=self.person, nome='Persuasão',
            defaults=dict(atributo='CAR', proficiente=True, expertise=True))
        known = ['lobo-alfa', 'camaleao-espectral', 'salamandra-ignea',
                 'yeti-boreal', 'kraken-onisciente', 'esfinge-visionaria',
                 'raptor-sombrio', 'gorgona-prateada']
        self.execute('learn', selected=known)
        baseline = derive(self.person, ruleset=self.profile.ruleset)
        legacy = derive(self.person)
        self.execute('prepare', selected=known[:2])
        for formula in known[:2]:
            self.execute('consume', formula=formula)
        sheet = derive(self.person, ruleset=self.profile.ruleset)
        rows = {row['nome']: row for row in sheet['pericias']}
        original = {row['nome']: row for row in baseline['pericias']}
        for name in ('Persuasão', 'Intimidação', 'Enganação', 'Atuação'):
            row = rows[name]
            self.assertEqual(row['bonus'], original[name]['bonus'])
            self.assertEqual(row['expertise'], original[name]['expertise'])
            self.assertEqual(row['mutagen_alternatives'], [
                dict(atributo=attr, bonus=original[name]['bonus']
                     - baseline['atributos']['CAR']['mod'] + sheet['atributos'][attr]['mod'])
                for attr in ('INT', 'SAB')])
            self.assertIn('Desvantagem', row['mutagen_conditions'][0])
        self.assertIn('audição', rows['Percepção']['mutagen_conditions'][0])
        self.assertNotIn('mutagen_alternatives', rows['Percepção'])
        self.assertEqual(sheet['saves'], baseline['saves'])
        self.assertEqual(sheet['iniciativa'], baseline['iniciativa'])
        self.assertTrue(sheet['mutagen_initiative_disadvantage'])
        self.assertEqual(derive(self.person)['pericias'], legacy['pericias'])
        response = self.client.get(reverse('hunter_sheet', args=[self.person.pk]))
        self.assertContains(response, 'Camaleão: INT')
        self.assertContains(response, 'desvantagem em Iniciativa')
        self.assertContains(response, 'também ao usar outro modificador')
        self.execute('purge')
        self.assertEqual(derive(self.person, ruleset=self.profile.ruleset)['pericias'], baseline['pericias'])
        self.client.post(reverse('personagem_descansar', args=[self.person.pk]), {'tipo': 'longo', 'next': self.url})
        self.execute('prepare', selected=known[:2])
        self.execute('chimera', movement='voo', resistances=['fogo', 'frio'])
        sheet = derive(self.person, ruleset=self.profile.ruleset)
        rows = {row['nome']: row for row in sheet['pericias']}
        self.assertNotIn('mutagen_conditions', rows['Persuasão'])
        self.assertIn('mutagen_alternatives', rows['Persuasão'])
        self.assertIn('mutagen_conditions', rows['Percepção'])
        self.assertFalse(sheet.get('mutagen_initiative_disadvantage'))
        self.execute('elapsed', seconds=60)
        self.assertEqual(derive(self.person, ruleset=self.profile.ruleset)['pericias'], baseline['pericias'])

    def test_bat_and_worm_senses_immunity_and_chimera(self):
        from .character_engine import derive
        from .hunter_mutagens import apply_defenses
        self.pc.nivel = 18
        self.pc.save(update_fields=['nivel'])
        known = ['morcego-abissal', 'vermeluz-das-cavernas', 'salamandra-ignea',
                 'yeti-boreal', 'kraken-onisciente', 'esfinge-visionaria',
                 'raptor-sombrio', 'gorgona-prateada']
        self.execute('learn', selected=known)
        baseline = derive(self.person, ruleset=self.profile.ruleset)
        self.execute('prepare', selected=known[:2])
        for formula in known[:2]:
            self.execute('consume', formula=formula)
        sheet = derive(self.person, ruleset=self.profile.ruleset)
        self.assertIn('darkvision 60ft', sheet['sentidos'])
        self.assertTrue({'Agarrado', 'Restringido'} <= {row['nome'] for row in sheet['imunidades_condicao']})
        self.assertTrue(sheet['mutagen_cannot_grapple'])
        self.assertTrue(sheet['mutagen_bright_light_disadvantage'])
        response = self.client.get(reverse('hunter_sheet', args=[self.person.pk]))
        self.assertContains(response, 'não pode Agarrar criaturas')
        self.assertContains(response, 'sob luz plena')
        existing = {'sentidos': ['darkvision 90ft', 'blindsight 30ft'],
                    'imunidades_condicao': [{'slug': 'agarrado', 'nome': 'Agarrado'}],
                    'imunidades': ['Agarrado (condição)', 'veneno']}
        apply_defenses(self.person, self.profile.ruleset, existing)
        self.assertEqual(existing['sentidos'], ['blindsight 30ft', 'darkvision 150ft'])
        self.assertEqual(existing['imunidades'].count('Agarrado (condição)'), 1)
        self.assertIn('veneno', existing['imunidades'])
        self.execute('purge')
        sheet = derive(self.person, ruleset=self.profile.ruleset)
        self.assertEqual(sheet['sentidos'], baseline['sentidos'])
        self.assertEqual(sheet['imunidades'], baseline['imunidades'])
        self.client.post(reverse('personagem_descansar', args=[self.person.pk]), {'tipo': 'longo', 'next': self.url})
        self.execute('prepare', selected=known[:2])
        self.execute('chimera', movement='voo', resistances=['fogo', 'frio'])
        sheet = derive(self.person, ruleset=self.profile.ruleset)
        self.assertIn('darkvision 60ft', sheet['sentidos'])
        self.assertIn('Agarrado (condição)', sheet['imunidades'])
        self.assertNotIn('mutagen_cannot_grapple', sheet)
        self.assertNotIn('mutagen_bright_light_disadvantage', sheet)

    def test_lizard_regeneration_external_healing_and_duration(self):
        self.pc.nivel = 7
        self.pc.save(update_fields=['nivel'])
        self.person.pv_maximo, self.person.pv_atual = 30, 1
        self.person.save(update_fields=['pv_maximo', 'pv_atual'])
        known = ['lagartixa-cicatrizante', 'guepardo-das-planicies',
                 'salamandra-ignea', 'yeti-boreal', 'kraken-onisciente']
        self.execute('learn', selected=known)
        self.execute('prepare', selected=[known[0]])
        self.execute('consume', formula=known[0])
        self.profile.refresh_from_db()
        payload = dict(action='mutagens', mutagen_event='regenerate', confirmed='1',
                       operation_id=str(uuid.uuid4()), version=self.profile.version,
                       mutagen_turn='sessao1-combate1-turno1')
        self.assertEqual(self.client.post(self.url, payload).status_code, 302)
        self.assertEqual(self.client.post(self.url, payload).status_code, 302)
        self.person.refresh_from_db()
        self.assertEqual(self.person.pv_atual, 4)
        with self.assertRaises(ValueError):
            self.execute('regenerate', turn_key=payload['mutagen_turn'])
        self.assertContains(self.client.get(self.url), 'Última cura registrada: 3 PV')
        self.execute('external_heal', healing_amount=9)
        self.person.refresh_from_db()
        self.assertEqual(self.person.pv_atual, 8)
        self.person.pv_atual = 0
        self.person.save(update_fields=['pv_atual'])
        with self.assertRaises(ValueError):
            self.execute('regenerate', turn_key='sessao1-combate1-turno2')
        self.execute('external_heal', healing_amount=100)
        self.person.refresh_from_db()
        self.assertEqual(self.person.pv_atual, 30)
        self.execute('elapsed', seconds=3600)
        with self.assertRaises(ValueError):
            self.execute('regenerate', turn_key='sessao1-combate1-turno3')
        self.execute('purge')
        with self.assertRaises(ValueError):
            self.execute('external_heal', healing_amount=8)

    def test_lizard_chimera_suppresses_healing_penalty_and_ends(self):
        self.pc.nivel = 18
        self.pc.save(update_fields=['nivel'])
        self.person.pv_maximo, self.person.pv_atual = 50, 1
        self.person.save(update_fields=['pv_maximo', 'pv_atual'])
        info = panel(self.profile)
        known = ['lagartixa-cicatrizante'] + [row['id'] for row in info['options']
            if row['id'] != 'lagartixa-cicatrizante'][:7]
        self.execute('learn', selected=known)
        self.execute('prepare', selected=[known[0]])
        self.execute('chimera', movement='voo', resistances=['fogo', 'frio'])
        self.execute('external_heal', healing_amount=9)
        self.execute('regenerate', turn_key='sessao1-combate2-turno1')
        self.person.refresh_from_db()
        self.assertEqual(self.person.pv_atual, 16)
        self.execute('elapsed', seconds=60)
        with self.assertRaises(ValueError):
            self.execute('regenerate', turn_key='sessao1-combate2-turno2')

    def test_cheetah_scaling_combination_and_chimera(self):
        import re
        from .character_engine import derive
        from .hunter_mutagens import apply_movement
        self.pc.nivel = 7
        self.pc.save(update_fields=['nivel'])
        self.person.velocidade = '30 ft'
        self.person.save(update_fields=['velocidade'])
        known = ['guepardo-das-planicies', 'carapaca-de-basilisco',
                 'salamandra-ignea', 'yeti-boreal', 'kraken-onisciente']
        self.execute('learn', selected=known)
        baseline = derive(self.person, ruleset=self.profile.ruleset)
        base_feet = int(re.search(r'(\d+)\s*ft', baseline['velocidade'])[1])
        self.execute('prepare', selected=known[:2])
        self.execute('consume', formula=known[0])
        sheet = derive(self.person, ruleset=self.profile.ruleset)
        self.assertEqual(int(re.search(r'(\d+)\s*ft', sheet['velocidade'])[1]), base_feet + 10)
        self.assertTrue(sheet['mutagen_cannot_concentrate'])
        self.assertContains(self.client.get(reverse('hunter_sheet', args=[self.person.pk])), 'não pode manter Concentração')
        self.execute('consume', formula=known[1])
        sheet = derive(self.person, ruleset=self.profile.ruleset)
        self.assertEqual(sheet['velocidade'], baseline['velocidade'])
        self.assertTrue(sheet['mutagen_cannot_dodge'])
        slow = {'velocidade': '5 ft', 'movimento_modos': {'swim': '5ft'}}
        apply_movement(self.person, self.profile.ruleset, slow)
        self.assertEqual(slow['velocidade'], '5 ft')
        self.assertEqual(slow['movimento_modos']['swim'], '5ft')
        self.pc.nivel = 15
        self.pc.save(update_fields=['nivel'])
        sheet = derive(self.person, ruleset=self.profile.ruleset)
        self.assertEqual(int(re.search(r'(\d+)\s*ft', sheet['velocidade'])[1]), base_feet + 5)
        self.execute('purge')
        self.assertNotIn('mutagen_cannot_concentrate', derive(self.person, ruleset=self.profile.ruleset))
        self.pc.nivel = 18
        self.pc.save(update_fields=['nivel'])
        self.client.post(reverse('personagem_descansar', args=[self.person.pk]), {'tipo': 'longo', 'next': self.url})
        self.execute('prepare', selected=known[:2])
        self.execute('chimera', movement='voo', resistances=['fogo', 'frio'])
        sheet = derive(self.person, ruleset=self.profile.ruleset)
        self.assertEqual(int(re.search(r'(\d+)\s*ft', sheet['velocidade'])[1]), base_feet + 15)
        self.assertEqual(sheet['movimento_modos']['fly'], 'walk')
        self.assertNotIn('mutagen_cannot_concentrate', sheet)
        self.assertNotIn('mutagen_cannot_dodge', sheet)
        self.execute('elapsed', seconds=60)
        self.assertEqual(derive(self.person, ruleset=self.profile.ruleset)['velocidade'], baseline['velocidade'])

    def test_basilisk_physical_defenses_movement_and_chimera(self):
        import re
        from .character_engine import derive
        from .hunter_mutagens import apply_movement
        self.pc.nivel = 18
        self.pc.save(update_fields=['nivel'])
        self.person.velocidade = '30 ft'
        self.person.save(update_fields=['velocidade'])
        known = ['carapaca-de-basilisco', 'harpia-das-montanhas', 'salamandra-ignea',
                 'yeti-boreal', 'kraken-onisciente', 'esfinge-visionaria',
                 'raptor-sombrio', 'gorgona-prateada']
        self.execute('learn', selected=known)
        baseline = derive(self.person, ruleset=self.profile.ruleset)
        self.execute('prepare', selected=known[:2])
        self.execute('consume', formula=known[0])
        self.execute('consume', formula=known[1])
        sheet = derive(self.person, ruleset=self.profile.ruleset)
        self.assertTrue({'cortante', 'perfurante', 'concussivo'} <= set(sheet['resistencias']))
        base_feet = int(re.search(r'(\d+)\s*ft', baseline['velocidade'])[1])
        self.assertEqual(int(re.search(r'(\d+)\s*ft', sheet['velocidade'])[1]), base_feet - 10)
        self.assertEqual(sheet['movimento_modos']['fly'], 'walk')
        self.assertTrue(sheet['mutagen_cannot_dodge'])
        self.assertContains(self.client.get(reverse('hunter_sheet', args=[self.person.pk])), 'não pode realizar a ação Esquivar')
        slow = {'velocidade': '1,5 m', 'movimento_modos': {'swim': '5ft'}}
        apply_movement(self.person, self.profile.ruleset, slow)
        self.assertEqual(slow['velocidade'], '0 m / 0 ft')
        self.assertEqual(slow['movimento_modos']['swim'], '0ft')
        self.execute('purge')
        self.assertEqual(derive(self.person, ruleset=self.profile.ruleset)['velocidade'], baseline['velocidade'])
        self.client.post(reverse('personagem_descansar', args=[self.person.pk]), {'tipo': 'longo', 'next': self.url})
        self.execute('prepare', selected=[known[0]])
        self.execute('chimera', movement='voo', resistances=['fogo', 'frio'])
        sheet = derive(self.person, ruleset=self.profile.ruleset)
        self.assertEqual(sheet['velocidade'], baseline['velocidade'])
        self.assertNotIn('mutagen_cannot_dodge', sheet)
        self.assertIn('concussivo', sheet['resistencias'])
        self.execute('elapsed', seconds=60)
        sheet = derive(self.person, ruleset=self.profile.ruleset)
        self.assertEqual(sheet['resistencias'], baseline['resistencias'])
        self.person.refresh_from_db()
        self.assertEqual(self.person.velocidade, '30 ft')

    def test_harpy_flight_duration_replay_and_purge(self):
        from .character_engine import derive
        self.pc.nivel = 11
        self.pc.save(update_fields=['nivel'])
        known = ['harpia-das-montanhas', 'salamandra-ignea', 'yeti-boreal',
                 'kraken-onisciente', 'esfinge-visionaria', 'raptor-sombrio']
        self.execute('learn', selected=known)
        self.execute('prepare', selected=known[:2])
        self.execute('consume', formula=known[0])
        self.execute('consume', formula=known[1])
        sheet = derive(self.person, ruleset=self.profile.ruleset)
        self.assertEqual(sheet['movimento_modos']['fly'], 'walk')
        self.assertTrue(sheet['mutagen_weapon_disadvantage'])
        self.assertContains(self.client.get(reverse('hunter_sheet', args=[self.person.pk])), '3600 segundos de voo')
        self.profile.refresh_from_db()
        args = dict(operation_id=uuid.uuid4(), expected_version=self.profile.version, seconds=3599)
        result = self.execute('elapsed', **args)
        self.assertEqual(result['harpy_seconds'], 1)
        self.assertEqual(self.execute('elapsed', **args), result)
        self.assertEqual(derive(self.person, ruleset=self.profile.ruleset)['movimento_modos']['fly'], 'walk')
        self.execute('elapsed', seconds=1)
        sheet = derive(self.person, ruleset=self.profile.ruleset)
        self.assertNotIn('fly', sheet.get('movimento_modos', {}))
        self.assertNotIn('mutagen_weapon_disadvantage', sheet)
        self.assertIn('fogo', sheet['resistencias'])
        self.client.post(reverse('personagem_descansar', args=[self.person.pk]), {'tipo': 'curto', 'next': self.url})
        self.execute('prepare', selected=[known[0]])
        self.execute('consume', formula=known[0])
        self.execute('purge')
        self.profile.refresh_from_db()
        self.assertEqual(panel(self.profile)['harpy_seconds'], 0)
        self.assertNotIn('fly', derive(self.person, ruleset=self.profile.ruleset).get('movimento_modos', {}))

    def test_chimera_movement_and_existing_faster_flight(self):
        from .character_engine import derive
        from .hunter_mutagens import apply_movement
        self.pc.nivel = 18
        self.pc.save(update_fields=['nivel'])
        known = ['harpia-das-montanhas', 'salamandra-ignea', 'yeti-boreal',
                 'kraken-onisciente', 'esfinge-visionaria', 'raptor-sombrio',
                 'gorgona-prateada', 'lobo-alfa']
        self.execute('learn', selected=known)
        for selected, mode in [('escalada', 'climb'), ('natacao', 'swim'), ('voo', 'fly')]:
            self.client.post(reverse('personagem_descansar', args=[self.person.pk]), {'tipo': 'longo', 'next': self.url})
            self.execute('prepare', selected=[known[0]])
            self.execute('chimera', movement=selected, resistances=['fogo', 'frio'])
            sheet = derive(self.person, ruleset=self.profile.ruleset)
            self.assertEqual(sheet['movimento_modos'][mode], 'walk')
            self.assertEqual(sheet['movimento_modos']['fly'], 'walk')
            self.assertNotIn('mutagen_weapon_disadvantage', sheet)
            faster = {'velocidade': '30 ft', 'movimento_modos': {'fly': '90ft'}}
            apply_movement(self.person, self.profile.ruleset, faster)
            self.assertEqual(faster['movimento_modos']['fly'], '90ft')
            self.execute('elapsed', seconds=60)
            self.assertNotIn('fly', derive(self.person, ruleset=self.profile.ruleset).get('movimento_modos', {}))

    def test_elemental_defenses_consumption_combination_purge_and_sheet(self):
        from .character_engine import derive
        self.pc.nivel = 7
        self.pc.save(update_fields=['nivel'])
        known = ['salamandra-ignea', 'yeti-boreal', 'kraken-onisciente',
                 'esfinge-visionaria', 'raptor-sombrio']
        self.execute('learn', selected=known)
        baseline = derive(self.person, ruleset=self.profile.ruleset)
        self.execute('prepare', selected=known[:2])
        self.execute('consume', formula=known[0])
        sheet = derive(self.person, ruleset=self.profile.ruleset)
        self.assertIn('fogo', sheet['resistencias'])
        self.assertIn('frio', sheet['vulnerabilidades'])
        self.assertNotIn('fogo', sheet['vulnerabilidades'])
        response = self.client.get(reverse('hunter_sheet', args=[self.person.pk]))
        self.assertContains(response, 'Vulnerabilidades: frio')
        self.execute('consume', formula=known[1])
        sheet = derive(self.person, ruleset=self.profile.ruleset)
        for damage in ('fogo', 'frio'):
            self.assertIn(damage, sheet['resistencias'])
            self.assertIn(damage, sheet['vulnerabilidades'])
        self.assertNotIn('vulnerabilidades', derive(self.person))
        self.execute('purge')
        sheet = derive(self.person, ruleset=self.profile.ruleset)
        self.assertEqual(sheet['resistencias'], baseline['resistencias'])
        self.assertEqual(sheet.get('vulnerabilidades', []), baseline.get('vulnerabilidades', []))

    def test_chimera_defenses_suppress_only_mutagen_vulnerability_and_expire(self):
        from .character_engine import derive
        from .hunter_mutagens import apply_defenses
        self.pc.nivel = 18
        self.pc.save(update_fields=['nivel'])
        known = ['salamandra-ignea', 'yeti-boreal', 'kraken-onisciente',
                 'esfinge-visionaria', 'raptor-sombrio', 'gorgona-prateada',
                 'vermeluz-das-cavernas', 'lobo-alfa']
        self.execute('learn', selected=known)
        self.execute('prepare', selected=known[:2])
        self.execute('chimera', movement='voo', resistances=['fogo', 'acido'])
        sheet = derive(self.person, ruleset=self.profile.ruleset)
        self.assertTrue({'fogo', 'frio', 'acido'} <= set(sheet['resistencias']))
        self.assertEqual(sheet['resistencias'].count('fogo'), 1)
        self.assertEqual(sheet.get('vulnerabilidades', []), [])
        other_sources = {'resistencias': ['radiante'], 'vulnerabilidades': ['fogo']}
        apply_defenses(self.person, self.profile.ruleset, other_sources)
        self.assertIn('radiante', other_sources['resistencias'])
        self.assertEqual(other_sources['vulnerabilidades'], ['fogo'])
        self.execute('elapsed', seconds=60)
        sheet = derive(self.person, ruleset=self.profile.ruleset)
        self.assertFalse({'fogo', 'frio', 'acido'} & set(sheet['resistencias']))
        self.assertEqual(sheet.get('vulnerabilidades', []), [])

    def test_attribute_formulas_feed_sheet_saves_and_purge_without_changing_base(self):
        from .character_engine import derive
        known = ['kraken-onisciente', 'esfinge-visionaria', 'raptor-sombrio', 'gorgona-prateada']
        self.execute('learn', selected=known)
        base = derive(self.person, ruleset=self.profile.ruleset)
        legacy = derive(self.person)
        for formula, raised, reduced in zip(known, ['INT', 'SAB', 'DES', 'FOR'],
                                           ['SAB', 'INT', 'FOR', 'DES']):
            with self.subTest(formula=formula):
                self.client.post(reverse('personagem_descansar', args=[self.person.pk]),
                                 {'tipo': 'curto', 'next': self.url})
                self.execute('prepare', selected=[formula])
                self.execute('consume', formula=formula)
                sheet = derive(self.person, ruleset=self.profile.ruleset)
                for key, delta in ((raised, 3), (reduced, -3)):
                    expected = base['atributos'][key]['valor'] + delta
                    self.assertEqual(sheet['atributos'][key]['valor'], expected)
                    mod_delta = (expected - 10) // 2 - base['atributos'][key]['mod']
                    self.assertEqual(sheet['saves'][key]['bonus'], base['saves'][key]['bonus'] + mod_delta)
                self.assertEqual(derive(self.person)['atributos'], legacy['atributos'])
                response = self.client.get(reverse('hunter_sheet', args=[self.person.pk]))
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.context['sheet']['atributos'], sheet['atributos'])
                self.execute('purge')
                self.assertEqual(derive(self.person, ruleset=self.profile.ruleset)['atributos'], base['atributos'])

    def test_attribute_scaling_cap_and_chimera_expiry(self):
        from .character_engine import derive
        self.pc.nivel = 18
        self.pc.save(update_fields=['nivel'])
        self.person.inteligencia = 20
        self.person.save(update_fields=['inteligencia'])
        self.learn()
        self.execute('prepare', selected=['kraken-onisciente', 'esfinge-visionaria'])
        base = derive(self.person, ruleset=self.profile.ruleset)
        self.execute('chimera', movement='voo', resistances=['fogo', 'frio'])
        sheet = derive(self.person, ruleset=self.profile.ruleset)
        self.assertEqual(sheet['atributos']['INT']['valor'], 22)
        self.assertEqual(sheet['atributos']['SAB']['valor'], min(22, base['atributos']['SAB']['valor'] + 5))
        self.execute('elapsed', seconds=60)
        self.assertEqual(derive(self.person, ruleset=self.profile.ruleset)['atributos'], base['atributos'])
        self.person.refresh_from_db()
        self.assertEqual(self.person.inteligencia, 20)

    def test_opposed_formulas_scale_and_share_resource_formula_context(self):
        from .character_engine import derive, _resource_formula_context
        self.pc.nivel = 11
        self.pc.save(update_fields=['nivel'])
        known = ['kraken-onisciente', 'esfinge-visionaria', 'raptor-sombrio',
                 'gorgona-prateada', 'salamandra-ignea', 'yeti-boreal']
        self.execute('learn', selected=known)
        self.execute('prepare', selected=known[:2])
        base = derive(self.person, ruleset=self.profile.ruleset)
        self.execute('consume', formula=known[0])
        single = derive(self.person, ruleset=self.profile.ruleset)
        self.assertEqual(single['atributos']['INT']['valor'], min(22, base['atributos']['INT']['valor'] + 4))
        self.execute('consume', formula=known[1])
        sheet = derive(self.person, ruleset=self.profile.ruleset)
        for key in ('INT', 'SAB'):
            self.assertEqual(sheet['atributos'][key]['valor'], min(22, base['atributos'][key]['valor'] + 4) - 3)
        from .versioned_library import ruleset_evaluation
        with ruleset_evaluation(self.profile.ruleset):
            ctx, _ = _resource_formula_context(self.person, list(self.person.classes.all()),
                                               ruleset=self.profile.ruleset)
        self.assertEqual(ctx['int_mod'], sheet['atributos']['INT']['mod'])
        self.assertEqual(ctx['wis_mod'], sheet['atributos']['SAB']['mod'])

    def test_preparation_consumption_purge_rest_and_http(self):
        known = self.learn()
        with self.assertRaises(ValueError):
            self.execute('learn', selected=known)
        self.execute('prepare', selected=[known[0]])
        self.profile.refresh_from_db()
        payload = dict(action='mutagens', mutagen_event='consume',
            operation_id=str(uuid.uuid4()), version=self.profile.version,
            formula=known[0], confirmed='1')
        self.assertEqual(self.client.post(self.url, payload).status_code, 302)
        self.assertEqual(self.client.post(self.url, payload).status_code, 302)
        self.profile.refresh_from_db()
        self.assertEqual(panel(self.profile)['active'], [known[0]])
        self.assertEqual(panel(self.profile)['prepared'], [])
        self.assertContains(self.client.get(reverse('hunter_sheet', args=[self.person.pk])),
                            'Fórmulas Mutagênicas')
        self.execute('purge')
        with self.assertRaises(ValueError):
            self.execute('prepare', selected=[known[0]])
        self.assertEqual(self.client.post(reverse('personagem_descansar', args=[self.person.pk]),
            {'tipo': 'curto', 'next': self.url}).status_code, 302)
        self.execute('prepare', selected=[known[1]])
        with self.assertRaises(ValueError):
            self.execute('consume', formula=known[0])

    def test_chimera_cost_duration_recovery_and_replay(self):
        self.pc.nivel = 18
        self.pc.save(update_fields=['nivel'])
        known = self.learn()
        self.execute('prepare', selected=known[:3])
        self.profile.refresh_from_db()
        args = dict(operation_id=uuid.uuid4(), expected_version=self.profile.version,
                    movement='voo', resistances=['fogo', 'frio'])
        result = self.execute('chimera', **args)
        self.assertEqual(result['active'], known[:3])
        self.assertEqual(self.execute('chimera', **args), result)
        self.assertEqual(self.person.recursos.get(chave__startswith='hunter:').atual, 14)
        self.assertEqual(self.execute('elapsed', seconds=60)['cooldown_seconds'], 3600)
        with self.assertRaises(ValueError):
            self.execute('chimera', movement='voo', resistances=['fogo', 'frio'])
        self.assertEqual(self.execute('elapsed', seconds=3600)['cooldown_seconds'], 0)
        self.assertEqual(self.client.post(reverse('personagem_descansar', args=[self.person.pk]),
            {'tipo': 'longo', 'next': self.url}).status_code, 302)
        self.execute('prepare', selected=known[:3])
        self.execute('chimera', movement='escalada', resistances=['acido', 'frio'])

    def test_formula_catalog_gates_and_foreign_order(self):
        import json
        from pathlib import Path
        from .hunter_rework import catalog
        reference = json.loads((Path(__file__).parent / 'rules/hunter_content.json').read_text(encoding='utf-8'))
        text = next(row['text'] for row in reference['features']
                    if row['id'] == '104-nivel-3-formulas-mutagenicas')
        formulas = catalog()['mutagen_formulas']
        self.assertEqual(len(formulas), 16)
        self.assertEqual(len({row['id'] for row in formulas}), 16)
        for row in formulas:
            self.assertIn(row['name'], text)
            self.assertIn(row['text'], text)
        options = panel(self.profile)['options']
        self.assertNotIn('carapaca-de-basilisco', [row['id'] for row in options])
        with self.assertRaises(ValueError):
            self.execute('learn', selected=['carapaca-de-basilisco'])
        with self.assertRaises(ValueError):
            self.execute('chimera', movement='voo', resistances=['fogo', 'frio'])
        self.pc.id_subclasse = self.subs['ordem-do-enxame']
        self.pc.save(update_fields=['id_subclasse'])
        self.profile.refresh_from_db()
        self.assertIsNone(panel(self.profile))
        with self.assertRaises(ValueError):
            self.execute('learn', selected=[])
