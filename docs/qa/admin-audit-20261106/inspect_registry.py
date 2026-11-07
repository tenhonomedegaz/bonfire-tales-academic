"""Inspect admin metadata in isolated SQLite; never connect to the configured DB."""
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
os.environ['DJANGO_SECRET_KEY'] = 'admin-metadata-audit-only'
os.environ['POSTGRES_URL'] = 'postgresql://unused:unused@127.0.0.1:1/unused'
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bonfire.settings')
from bonfire import settings
settings.DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':memory:'}}
import django
django.setup()
from django.contrib import admin
from django.db import connections
from django.test import RequestFactory

for connection in connections.all():
    if connection.vendor != 'sqlite' or connection.settings_dict['NAME'] != ':memory:':
        raise RuntimeError('Only isolated memory databases are allowed')

request = RequestFactory().get('/admin/')
request.user = SimpleNamespace(is_active=True, is_authenticated=True, is_staff=True,
    is_superuser=True, pk=0, has_perm=lambda *a, **kw: True,
    has_module_perms=lambda *a, **kw: True, get_username=lambda: 'metadata-auditor')

def readable(value):
    return value if isinstance(value, str) else getattr(value, '__name__', str(type(value).__name__))

rows = []
for model, handler in admin.site._registry.items():
    row = {'model': model._meta.label, 'name': str(model._meta.verbose_name_plural),
        'admin_class': type(handler).__name__, 'managed': model._meta.managed,
        'list_display': [readable(x) for x in handler.get_list_display(request)],
        'search_fields': list(handler.search_fields), 'list_filter': [readable(x) for x in handler.list_filter],
        'list_editable': list(handler.list_editable),
        'autocomplete_fields': list(handler.autocomplete_fields), 'raw_id_fields': list(handler.raw_id_fields),
        'readonly_fields': [readable(x) for x in handler.get_readonly_fields(request)],
        'inlines': [readable(x) for x in handler.inlines],
        'list_select_related': handler.list_select_related,
        'actions': list(handler.get_actions(request)),
        'add_allowed': handler.has_add_permission(request),
        'change_allowed_at_module_level': handler.has_change_permission(request),
        'delete_allowed_at_module_level': handler.has_delete_permission(request),
        'nullable_patch_installed': bool(getattr(handler, '_bonfire_nullable_installed', False)),
        'row_delete_patch_installed': bool(getattr(handler, '_bonfire_delete_installed', False)),
        'json_fields': [f.name for f in model._meta.fields if f.get_internal_type() == 'JSONField'],
        'permission_check_note': 'Module-level metadata only; object-specific guards may differ.'}
    rows.append(row)
rows.sort(key=lambda row: row['model'])
summary = {'registered_models': len(rows), 'without_search': sum(not x['search_fields'] for x in rows),
    'with_raw_ids': sum(bool(x['raw_id_fields']) for x in rows),
    'with_json_fields': sum(bool(x['json_fields']) for x in rows),
    'with_delete_selected': sum('delete_selected' in x['actions'] for x in rows),
    'unmanaged_models': sum(not x['managed'] for x in rows),
    'nullable_patch_installed': sum(x['nullable_patch_installed'] for x in rows),
    'row_delete_patch_installed': sum(x['row_delete_patch_installed'] for x in rows)}
output = ROOT / 'docs/qa/admin-audit-20261106/registry.json'
output.write_text(json.dumps({'scope': 'local code metadata, no production records',
    'summary': summary, 'models': rows}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps(summary))
