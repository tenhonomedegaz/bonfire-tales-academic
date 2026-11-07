"""Superuser-only export preview and download, protected by the admin site."""
import json

from django.contrib import admin
from django.contrib.admin.models import CHANGE, LogEntry
from django.core import signing
from django.http import FileResponse, HttpResponseForbidden, JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from . import catalog_export as exports

SALT = 'bonfire.catalog-export.v1'


@require_http_methods(['GET', 'POST'])
def catalog_export_view(request):
    if not (request.user.is_authenticated and request.user.is_active
            and request.user.is_staff and request.user.is_superuser):
        return HttpResponseForbidden('Apenas superusers podem exportar catalogos.')
    if request.method == 'GET':
        return render(request, 'admin/catalog_export.html', {
            **admin.site.each_context(request), 'title': 'Exportar dados',
            'export_schema': exports.schema(), 'max_tables': exports.MAX_TABLES,
            'max_rows': exports.MAX_ROWS_PER_TABLE,
        })
    stream = None
    try:
        try:
            size = int(request.META.get('CONTENT_LENGTH') or 0)
        except (TypeError, ValueError):
            raise exports.ExportError('Tamanho da requisicao invalido.') from None
        # CSRF may already have parsed multipart POST; do not reread request.body.
        if size > 128 * 1024:
            raise exports.ExportError('Selecao muito grande.')
        action = request.POST.get('action')
        if action == 'preview':
            raw_spec = request.POST.get('spec', '{}')
            if len(raw_spec.encode('utf-8')) > 64 * 1024:
                raise exports.ExportError('Selecao muito grande.')
            spec = json.loads(raw_spec)
            prepared = exports.prepare(spec)
            data = exports.preview(prepared)
            ticket = signing.dumps({'user': request.user.pk, 'spec': spec,
                'counts': {row['name']: row['count'] for row in prepared}}, salt=SALT, compress=True)
            response = JsonResponse({'tables': data, 'total': sum(row['count'] for row in prepared), 'ticket': ticket})
            response['Cache-Control'] = 'no-store'
            return response
        if action != 'download':
            raise exports.ExportError('Acao invalida.')
        try:
            data = signing.loads(request.POST.get('ticket', ''), salt=SALT, max_age=600)
        except signing.BadSignature:
            raise exports.ExportError('Previa expirada ou invalida; gere uma nova previa.') from None
        if data['user'] != request.user.pk:
            return HttpResponseForbidden('Previa pertence a outro usuario.')
        prepared = exports.prepare(data['spec'])
        if {row['name']: row['count'] for row in prepared} != data['counts']:
            raise exports.ExportError('Os registros mudaram; gere uma nova previa.')
        stream = exports.build_workbook(prepared, request.user.pk)
        LogEntry.objects.create(user_id=request.user.pk, action_flag=CHANGE,
            object_repr='Exportacao de catalogos XLSX', change_message=json.dumps({
                'generated_export': [{'model': row['name'], 'count': row['count'],
                                      'fields': row['columns']} for row in prepared]}))
        response = FileResponse(stream, as_attachment=True,
            filename='bonfire_catalogos_%s.xlsx' % timezone.now().strftime('%Y%m%d_%H%M%S'),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Cache-Control'] = 'no-store'
        response['X-Content-Type-Options'] = 'nosniff'
        return response
    except (exports.ExportError, json.JSONDecodeError) as exc:
        if stream is not None:
            stream.close()
        return JsonResponse({'error': str(exc)}, status=400)
    except Exception:
        if stream is not None:
            stream.close()
        raise
