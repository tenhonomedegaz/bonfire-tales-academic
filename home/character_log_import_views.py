"""Private, bounded operator UI for registered bot-sheet history."""
import re
from urllib.parse import urlencode

from django import forms
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db import DatabaseError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_http_methods

from .character_log_import import apply_log, preview_log, registered_logs
from .character_log_models import CharacterLogImportBatch
from .character_log_workbook import MAX_BYTES, MAX_RECORDS


class PreviewForm(forms.Form):
    log_id = forms.RegexField(r'^[A-Za-z0-9_-]{1,30}$', max_length=30,
        error_messages={'required': 'Selecione uma ficha cadastrada no bot.',
                        'invalid': 'Identificador de ficha invalido.',
                        'max_length': 'Identificador de ficha excede 30 caracteres.'})
    guild_id = forms.RegexField(r'^[0-9]{15,22}$', required=False, max_length=22,
        error_messages={'invalid': 'Informe o ID do servidor Discord com 15 a 22 digitos.',
                        'max_length': 'ID do servidor Discord excede 22 digitos.'})
    uploaded = forms.FileField(required=False,
        error_messages={'invalid': 'Arquivo invalido. Envie um XLSX de ate 8 MB.',
                        'empty': 'O arquivo XLSX enviado esta vazio.'})

    def clean_uploaded(self):
        upload = self.cleaned_data.get('uploaded')
        if upload is not None:
            if upload.size > MAX_BYTES or not upload.name.lower().endswith('.xlsx'):
                raise ValidationError('Envie um arquivo XLSX de ate 8 MB.')
        return upload


STATE_LABELS = {
    'staff_confirmed': ('Log aprovado pela staff', 'success', 'Registro historico da fonte cadastrada; nao concede nova recompensa nem presume um recibo financeiro vinculado.'),
    'quantity_unproven': ('Quantidade a comprovar', 'warning', 'Missao e participante encontrados, mas falta prova da quantidade de aventuras.'),
    'matched': ('Correspondencia confirmada', 'success', 'Vinculo com missao existente do bot; sem novo credito.'),
    'conflict': ('Conflito', 'warning', 'Quantidade da planilha diverge do registro do bot.'),
    'ambiguous': ('Ambiguo', 'warning', 'Mais de uma correspondencia possivel ou missao repetida; sem escolha automatica.'),
    'unproven': ('Participacao nao comprovada', 'warning', 'Titulo encontrado, mas a participacao deste personagem nao foi comprovada.'),
    'unmatched': ('Sem correspondencia', 'muted', 'Nenhuma missao correspondente comprovada no bot.'),
    'adjustment': ('Bonificacao / resgate a comprovar', 'warning', 'Categoria identificada, mas exige recibo ou evidencia validada pela staff. Nao concede credito.'),
}
SOURCE_LABELS = {
    'uploaded_xlsx': 'Arquivo XLSX enviado',
    'registered_google_sheet': 'Planilha Google cadastrada no bot',
}


def _rows(rows):
    result = []
    for row in rows[:MAX_RECORDS]:
        label, tone, reason = STATE_LABELS.get(row.get('state'),
            ('Revisao pendente', 'warning', 'Estado nao reconhecido; revisar a origem.'))
        result.append({**row, 'state_label': label, 'tone': tone, 'reason': reason})
    return result


def _pagination(page, params, key, anchor):
    def url(number):
        return '?' + urlencode({**params, key: number}) + '#' + anchor
    return {
        'page': page,
        'previous': url(page.previous_page_number()) if page.has_previous() else '',
        'next': url(page.next_page_number()) if page.has_next() else '',
    }


def _render(request, context, status=200):
    metadata = context.get('metadata', {})
    bot_summary = metadata.get('bot_summary', {})
    comparison = []
    if bot_summary:
        for key, label in [('level', 'Nivel'), ('class_name', 'Classe'),
                           ('rank_name', 'Rank'), ('adventures_reported', 'Aventuras declaradas')]:
            comparison.append({'label': label,
                'sheet': metadata.get(key) if metadata.get(key) not in (None, '') else 'Nao informado',
                'bot': bot_summary.get(key) if bot_summary.get(key) not in (None, '') else 'Nao informado'})
    return render(request, 'home/gestao/character_logs.html', {
        'page_title': 'Fichas do bot', 'noindex': True, 'ads_enabled': False,
        'can_view_people': True, 'management_section': 'character_logs',
        'root_url': reverse('gestao:character_logs'), 'metadata_comparison': comparison, **context,
    }, status=status)


@never_cache
@sensitive_post_parameters('ticket', 'uploaded')
@require_http_methods(['GET', 'POST'])
@csrf_protect
def index(request):
    actor = request.user
    if not actor.is_authenticated or not actor.is_active or not actor.is_superuser:
        raise PermissionDenied

    context = {'q': '', 'logs': [], 'error': '', 'guild_id': ''}
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'apply':
            ticket = request.POST.get('ticket', '')
            if request.POST.getlist('confirm') != ['yes']:
                context['error'] = 'Marque a confirmacao explicita e gere outra previa antes de importar.'
                return _render(request, context, 400)
            if not ticket or len(ticket) > 1500000:
                context['error'] = 'Previa invalida. Analise a planilha novamente.'
                return _render(request, context, 400)
            try:
                batch = apply_log(actor, ticket)
            except ValidationError as exc:
                context['error'] = '; '.join(exc.messages)[:1000]
                return _render(request, context, 400)
            except DatabaseError:
                context['error'] = 'Nao foi possivel confirmar o registro. Consulte os recibos antes de tentar novamente.'
                return _render(request, context, 503)
            return redirect(reverse('gestao:character_logs') + '?' + urlencode({'batch': batch.pk}))

        if action != 'preview':
            context['error'] = 'Acao invalida. Nenhuma importacao foi solicitada.'
            return _render(request, context, 400)
        form = PreviewForm(request.POST, request.FILES)
        if not form.is_valid():
            context['error'] = '; '.join(message for errors in form.errors.values()
                                        for message in errors)[:1000]
            return _render(request, context, 400)
        upload = form.cleaned_data['uploaded']
        data = upload.read(MAX_BYTES + 1) if upload is not None else None
        if data is not None and len(data) > MAX_BYTES:
            context['error'] = 'Envie um arquivo XLSX de ate 8 MB.'
            return _render(request, context, 400)
        try:
            preview = preview_log(actor, form.cleaned_data['log_id'], uploaded=data,
                                  guild_id=form.cleaned_data['guild_id'] or None)
        except ValidationError as exc:
            context['error'] = '; '.join(exc.messages)[:1000]
            return _render(request, context, 400)
        except DatabaseError:
            context['error'] = 'Consulta indisponivel. Nenhuma importacao foi confirmada; tente novamente mais tarde.'
            return _render(request, context, 503)
        rows = _rows(preview['rows'])
        context.update(preview=preview, metadata=preview['metadata'],
            owner=preview['owner'], character_name=preview['log'].characterName,
            discord_id=preview['log'].discordUserId, discord_tag=preview['log'].discordUserTag,
            character_id=preview['character_id'], warnings=preview['warnings'],
            source_label=SOURCE_LABELS['uploaded_xlsx' if upload is not None else 'registered_google_sheet'],
            row_count=len(rows), matched=preview['matched'], pending=preview['pending'],
            row_groups=[{'start': i + 1, 'end': min(i + 25, len(rows)), 'rows': rows[i:i + 25]}
                        for i in range(0, len(rows), 25)])
        return _render(request, context)

    q = request.GET.get('q', '').strip()
    context['q'] = q[:22]
    if q and not re.fullmatch(r'[0-9]{15,22}', q):
        context['error'] = 'Informe um ID Discord de 15 a 22 digitos, nao o nome de exibicao.'
        return _render(request, context, 400)
    try:
        if q:
            context['logs'] = registered_logs(actor, q)
        batch_id = request.GET.get('batch', '')
        if batch_id:
            if not re.fullmatch(r'[0-9]{1,19}', batch_id) or not 0 < int(batch_id) <= 9223372036854775807:
                raise ValidationError('Recibo invalido.')
            batch = get_object_or_404(CharacterLogImportBatch.objects.select_related('source__owner', 'actor'), pk=batch_id)
            snapshot = batch.snapshot
            rows = _rows(snapshot.get('rows', []))
            page = Paginator(rows, 25).get_page(request.GET.get('page'))
            context.update(batch=batch, owner=batch.source.owner,
                character_name=batch.source.character_name, discord_id=batch.source.discord_user_id,
                character_id=batch.source.character_id, metadata=snapshot.get('metadata', {}),
                source_label=SOURCE_LABELS.get(snapshot.get('metadata', {}).get('input_kind'), 'Origem nao informada'),
                warnings=snapshot.get('warnings', []), row_count=len(rows),
                matched=sum(row['state'] == 'matched' for row in rows),
                pending=sum(row['state'] not in ('matched', 'staff_confirmed') for row in rows),
                receipt_rows=page, receipt_nav=_pagination(page, {'batch': batch.pk}, 'page', 'history'))

        batches = CharacterLogImportBatch.objects.select_related('source__owner', 'actor').order_by('-created_at', '-pk')
        if q:
            batches = batches.filter(source__discord_user_id=q)
        page = Paginator(batches, 25).get_page(request.GET.get('imports_page'))
        context['imports'] = [
            {'batch': batch, 'metadata': batch.snapshot.get('metadata', {}),
             'source_label': SOURCE_LABELS.get(batch.snapshot.get('metadata', {}).get('input_kind'), 'Origem nao informada')}
            for batch in page]
        params = {'q': q} if q else {}
        if batch_id:
            params['batch'] = batch_id
        context['imports_nav'] = _pagination(page, params, 'imports_page', 'imports')
    except ValidationError as exc:
        context['error'] = '; '.join(exc.messages)[:1000]
        return _render(request, context, 400)
    except DatabaseError:
        context['error'] = 'Historico indisponivel no momento. Tente novamente mais tarde.'
        return _render(request, context, 503)
    return _render(request, context)
