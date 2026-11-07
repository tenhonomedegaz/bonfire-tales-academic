"""Prepare a data-only reconciliation from an API identity export; no DB settings."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from home.subclass_spell_catalog import resolve_spells, build_tag_plan, build_definitions


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--catalog', type=Path, required=True)
    parser.add_argument('--reference', type=Path, default=Path(__file__).resolve().parents[1] / 'home/content_packages/subclass_spells_20261104.json')
    parser.add_argument('--overrides', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    sources=parser.add_mutually_exclusive_group()
    sources.add_argument('--source-fixture', type=Path)
    sources.add_argument('--source-catalog', type=Path, help='Filtered API rows: classes, subclasses, features')
    parser.add_argument('--bindings', type=Path)
    parser.add_argument('--tag-plan-output', type=Path)
    parser.add_argument('--definitions-output', type=Path)
    args = parser.parse_args()
    manifest = json.loads(args.reference.read_text(encoding='utf-8-sig'))
    catalog = json.loads(args.catalog.read_text(encoding='utf-8-sig'))
    if isinstance(catalog, dict):
        if len(catalog['items']) != catalog['total']:
            raise ValueError('Supply all identity pages, not a truncated catalog')
        catalog = catalog['items']
    overrides = json.loads(args.overrides.read_text(encoding='utf-8-sig')) if args.overrides else {}
    result = resolve_spells(manifest, catalog, overrides=overrides)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result['counts']))
    pending = {row['english_name']: row['reason'] for row in result['pending']}
    print(json.dumps(pending, ensure_ascii=False, indent=2))
    bindings=json.loads(args.bindings.read_text(encoding='utf-8-sig')) if args.bindings else {}
    if args.definitions_output:
        definitions=build_definitions(result,bindings=bindings)
        args.definitions_output.parent.mkdir(parents=True,exist_ok=True)
        args.definitions_output.write_text(json.dumps(definitions,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    if args.source_fixture or args.source_catalog:
        if not args.tag_plan_output:
            raise ValueError('--tag-plan-output is required with source catalog')
        if args.source_fixture:
            rows=json.loads(args.source_fixture.read_text(encoding='utf-8-sig'))
            def collection(model, pk_name):
                return [{**row['fields'],pk_name:row['pk']} for row in rows if row['model']==model]
            source={'classes':collection('home.tbclasse','id_classe'),
                    'subclasses':collection('home.tbsubclasse','id_subclasse'),
                    'features':collection('home.tbclassehabilidade','id_habilidade')}
        else:
            source=json.loads(args.source_catalog.read_text(encoding='utf-8-sig'))
        plan=build_tag_plan(result,source['classes'],source['subclasses'],source['features'],bindings=bindings)
        args.tag_plan_output.parent.mkdir(parents=True,exist_ok=True)
        args.tag_plan_output.write_text(json.dumps(plan,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print(json.dumps({'tag_plan':plan['counts'],'pending_targets':plan['pending_targets']},ensure_ascii=False))


if __name__ == '__main__':
    main()
