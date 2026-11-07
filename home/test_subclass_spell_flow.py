"""Focused grants/sync regression. --isolated uses a disposable SQLite test DB."""
import sys
from pathlib import Path

ISOLATED = __name__ == '__main__' and '--isolated' in sys.argv
if ISOLATED:
    from django.conf import settings
    settings.configure(
        SECRET_KEY='isolated-subclass-spells', USE_TZ=True,
        INSTALLED_APPS=['django.contrib.auth','django.contrib.contenttypes','django.contrib.sessions','home'],
        DATABASES={'default':{'ENGINE':'django.db.backends.sqlite3','NAME':':memory:'}},
        MIGRATION_MODULES={'home':None}, ROOT_URLCONF=__name__, MIDDLEWARE=[],
        BASE_DIR=Path(__file__).resolve().parents[1], STATIC_URL='/static/',
        TEMPLATES=[{'BACKEND':'django.template.backends.django.DjangoTemplates','APP_DIRS':True}],
        DEFAULT_AUTO_FIELD='django.db.models.AutoField',
        SITE_POSTGRES_TABLES={},
        PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'],
        CACHES={'default':{'BACKEND':'django.core.cache.backends.locmem.LocMemCache'}},
    )
    import django
    django.setup()

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.db import connection
from django.test.utils import CaptureQueriesContext
from home.character_engine import magias_concedidas
from home.models import (TbClasse,TbSubclasse,TbClassehabilidade,TbMagia,
                         TbPersonagem,TbPersonagemClasse,TbPersonagemEscolha,TbPersonagemMagia)
from home.subclass_spell_catalog import spell_grant_tag

urlpatterns=[]


class SubclassSpellFlowTests(TestCase):
    def setUp(self):
        self.cl=TbClasse.objects.create(nome='Generic source',slug='generic-source',tags_json=['subclass-choices:[3]'])
        self.sub=TbSubclasse.objects.create(id_classe=self.cl,nome='Any branch',slug='any-branch')
        self.spell=TbMagia.objects.create(nome='Granted test',nome_ingles='Granted test',slug='granted-test',nivel=2)
        self.other=TbMagia.objects.create(nome='Other test',slug='other-test',nivel=1)
        # Bulk insertion avoids unrelated first-character rewards.
        owner=get_user_model().objects.create_user('subclass-fixture')
        self.person=TbPersonagem.objects.bulk_create([TbPersonagem(nome='Fixture',nivel=20,dono=owner)])[0]
        self.pc=TbPersonagemClasse.objects.create(id_personagem=self.person,id_classe=self.cl,
                                                 id_subclasse=self.sub,nivel=3,principal=True)
        second=TbClasse.objects.create(nome='Other class',slug='other-class')
        TbPersonagemClasse.objects.create(id_personagem=self.person,id_classe=second,nivel=17)
        self.feature=TbClassehabilidade.objects.create(id_classe=self.cl,id_subclasse=self.sub,
            nome='Shared spell source',niveladquirido=3,tags_json=[spell_grant_tag(self.spell.slug,5)])

    def test_actual_feature_pipeline_uses_source_level_and_tag_changes(self):
        self.assertFalse(magias_concedidas(self.person)['concedidas'])
        self.pc.nivel=5;self.pc.save(update_fields=['nivel'])
        self.assertEqual([row['slug'] for row in magias_concedidas(self.person)['concedidas']],['granted-test'])
        self.feature.tags_json=[spell_grant_tag(self.other.slug,3)]
        self.feature.save(update_fields=['tags_json'])
        self.assertEqual([row['slug'] for row in magias_concedidas(self.person)['concedidas']],['other-test'])

    def test_sync_is_idempotent_and_preserves_independently_learned_spell(self):
        from home.views import _sync_magias_concedidas
        acquired=TbPersonagemMagia.objects.create(id_personagem=self.person,id_magia=self.spell,
            nome=self.spell.nome,nivel=2,origem='Separately learned',preparada=False,sempre_preparada=False)
        self.pc.nivel=5;self.pc.save(update_fields=['nivel'])
        _sync_magias_concedidas(self.person)
        ids=list(self.person.magias.values_list('pk',flat=True))
        _sync_magias_concedidas(self.person)
        self.assertEqual(set(ids),set(self.person.magias.values_list('pk',flat=True)))
        granted=self.person.magias.get(sempre_preparada=True)
        self.assertTrue(granted.preparada)
        self.pc.nivel=3;self.pc.save(update_fields=['nivel'])
        _sync_magias_concedidas(self.person)
        self.assertFalse(self.person.magias.filter(sempre_preparada=True).exists())
        self.assertTrue(self.person.magias.filter(pk=acquired.pk,preparada=False).exists())

    def test_variant_and_universal_grants_are_separate(self):
        from home.views import _sync_magias_concedidas
        self.feature.tags_json=[spell_grant_tag(self.other.slug,3),
            'pick:elemento:1(agua|fogo)',
            'match(pick:elemento){agua:{' + spell_grant_tag(self.spell.slug,3) + '}}']
        self.feature.save(update_fields=['tags_json'])
        _sync_magias_concedidas(self.person)
        self.assertEqual(list(self.person.magias.values_list('id_magia__slug',flat=True)),['other-test'])
        choice=TbPersonagemEscolha.objects.create(id_personagem=self.person,origem=self.feature.nome,
                                                  tipo='elemento',slot=0,valor='agua')
        _sync_magias_concedidas(self.person)
        self.assertEqual(set(self.person.magias.values_list('id_magia__slug',flat=True)),{'other-test','granted-test'})
        choice.valor='fogo';choice.save(update_fields=['valor'])
        _sync_magias_concedidas(self.person)
        self.assertEqual(list(self.person.magias.values_list('id_magia__slug',flat=True)),['other-test'])

    def test_vtt_reads_virtual_grant_without_materializing_it(self):
        from home.vtt_spell_access import effective_spell_access
        self.pc.nivel=5;self.pc.save(update_fields=['nivel'])
        with CaptureQueriesContext(connection) as queries:
            access=effective_spell_access(self.person)
        self.assertEqual([row['slug'] for row in access['magias']],['granted-test'])
        self.assertTrue(access['magias'][0]['sempre_preparada'])
        self.assertFalse(access['conjuracao_automatica'])
        self.assertFalse(self.person.magias.exists())
        self.assertFalse(any(query['sql'].lstrip().upper().startswith(('INSERT','UPDATE','DELETE')) for query in queries))

    def test_pinned_spell_access_preserves_revision_after_live_catalog_edit(self):
        from home.content_versions import create_revision,seal_ruleset
        from home.versioned_classes import inventory_class,EVALUATOR,VOCABULARY
        from home.versioned_spells import snapshot_spells
        from home.versioned_options import snapshot_options
        from home.versioned_origins import snapshot_origins
        from home.versioned_items import snapshot_magic_items,snapshot_mundane_items
        from home.versioned_conditions import snapshot_conditions
        from home.versioned_library import snapshot_library
        from home.tag_engine.library import Library
        from home.vtt_spell_access import effective_spell_access
        self.pc.nivel=5;self.pc.save(update_fields=['nivel'])
        revisions=[create_revision('class-catalog:%s'%c.pk,inventory_class(c.pk)) for c in TbClasse.objects.all()]
        revisions += [snapshot_spells(),snapshot_options(),snapshot_origins(),snapshot_magic_items(),
                      snapshot_mundane_items(),snapshot_conditions(),snapshot_library(raw=Library(prefer_db=False).raw)]
        ruleset=seal_ruleset(revisions,evaluator_version=EVALUATOR,vocabulary_version=VOCABULARY)
        self.pc.ruleset=ruleset;self.pc.save(update_fields=['ruleset'])
        before=effective_spell_access(self.person)
        self.assertEqual(before['catalogo']['tipo'],'fixado')
        self.assertEqual([row['slug'] for row in before['magias']],['granted-test'])
        self.spell.nome='Edited live name';self.spell.tags_json=['speed:+999']
        self.spell.save(update_fields=['nome','tags_json'])
        self.feature.tags_json=[];self.feature.save(update_fields=['tags_json'])
        self.assertEqual(effective_spell_access(self.person),before)
        self.assertFalse(self.person.magias.exists())


if ISOLATED:
    from django.test.runner import DiscoverRunner
    raise SystemExit(bool(DiscoverRunner(verbosity=1,interactive=False).run_tests(['home.test_subclass_spell_flow'])))
