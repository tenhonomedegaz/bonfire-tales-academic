from django.test import TestCase
from home.models import TbClasse, TbClassehabilidade, TbSubclasse, TbRecursoclasse
from home.versioned_classes import seal_class_snapshot
from home.spellcasting import class_spellcasting_contract, limit_at, slot_table_at, max_spell_level_at


class VersionedSpellcastingTests(TestCase):
    def test_contract_limits_slots_and_unlock_survive_changes(self):
        cl = TbClasse.objects.create(nome='Frozen caster', slug='frozen-caster',
            tags_json=['subclass-choices{3}', 'spellcasting{ability:int, list:frozen-caster, slots:full}'])
        sub = TbSubclasse.objects.create(id_classe=cl, nome='Frozen school', slug='frozen-school')
        feature = TbClassehabilidade.objects.create(id_classe=cl, id_subclasse=sub, nome='Ability',
            niveladquirido=3, descricao='', tags_json=['spellcasting{ability:wis}'])
        resource = TbRecursoclasse.objects.create(id_classe=cl, nome='Prepared', slug='prepared',
            tipo='table-only', valores_json={'1': '2', '3': '4'})
        slots = TbRecursoclasse.objects.create(id_classe=cl, nome='Third circle', slug='3o',
            tipo='table-only', valores_json={'3': '2'})
        ruleset = seal_class_snapshot(cl.pk)
        spec = {'kind': 'resource', 'value': 'prepared'}
        def read(pinned=None):
            contract = class_spellcasting_contract(cl, level=3, subclass=sub, ruleset=pinned)
            return (contract, limit_at(spec, cl, level=3, subclass=sub, ruleset=pinned),
                    slot_table_at(cl, level=3, subclass=sub, ruleset=pinned),
                    max_spell_level_at(contract, cl, level=3, subclass=sub, ruleset=pinned))
        before = read()
        self.assertEqual(before[0]['ability'], 'wis')
        self.assertEqual(before[1:], (4, {3: 2}, 3))
        self.assertEqual(read(ruleset), before)
        feature.tags_json = ['spellcasting{ability:cha}']
        feature.save()
        resource.valores_json = {'1': '99'}
        resource.save()
        slots.valores_json = {'3': '0'}
        slots.save()
        self.assertNotEqual(read(), before)
        self.assertEqual(read(ruleset), before)
        self.assertEqual(class_spellcasting_contract(cl, level=2, subclass=sub, ruleset=ruleset)['ability'], 'int')
        self.assertEqual(limit_at(spec, cl, level=2, ruleset=ruleset), 2)
        self.assertEqual(slot_table_at(cl, level=2, ruleset=ruleset), {})
        resource.delete()
        slots.delete()
        self.assertEqual(read(ruleset), before)
