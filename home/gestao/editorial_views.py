"""Read-through queue: editorial sources retain their own decisions and revisions."""
from urllib.parse import urlencode

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import CharField, F, Q, Value
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from home.models import TbCronica, TbTrabalhoMestre, TbMesaAnuncio
from home.character_stories import pending_stories
from .policy import can, can_review_editorial
from .views import _workspace


def review_page(request, queryset, *, item_parameter='item', page_parameter='page'):
    item = request.GET.get(item_parameter, '')
    if item.isascii() and item.isdigit() and len(item) <= 18:
        queryset = queryset.filter(pk=int(item))
    else:
        item = ''
    page = Paginator(queryset, 25).get_page(request.GET.get(page_parameter))
    def link(number):
        return '?' + urlencode({item_parameter: item, page_parameter: number})
    return page, {'page_obj': page,
        'previous_url': link(page.previous_page_number()) if page.has_previous() else '',
        'next_url': link(page.next_page_number()) if page.has_next() else ''}


@never_cache
@login_required(login_url='login')
@require_GET
def index(request):
    if not can_review_editorial(request.user):
        raise PermissionDenied
    query = request.GET.get('q', '').strip()[:150]
    source = request.GET.get('source', '')
    if source not in ('cronica', 'portfolio', 'anuncio', 'historia'):
        source = ''
    columns = ('pk', 'title', 'author', 'submitted', 'source')
    queues = []
    choices = []
    if can(request.user, 'editorial.triage') or can(request.user, 'editorial.decide'):
        choices.append(('cronica', 'Crônicas'))
        chronicles = TbCronica.objects.filter(
            Q(status='pendente') | Q(status='aprovada', revisao_edicao__estado='pendente'))
        if query:
            chronicles = chronicles.filter(Q(titulo__icontains=query) | Q(autor__username__icontains=query)
                                           | Q(revisao_edicao__titulo__icontains=query))
        if source in ('', 'cronica'):
            queues.append(chronicles.order_by().annotate(
                title=F('titulo'), author=F('autor__username'), submitted=F('data_submissao'),
                source=Value('cronica', output_field=CharField())).values(*columns))
    if can(request.user, 'editorial.portfolio'):
        choices.append(('portfolio', 'Trabalhos de mestres'))
        works = TbTrabalhoMestre.objects.filter(estado='pendente')
        if query:
            works = works.filter(Q(titulo__icontains=query) | Q(mestre__username__icontains=query))
        if source in ('', 'portfolio'):
            queues.append(works.order_by().annotate(
                title=F('titulo'), author=F('mestre__username'), submitted=F('atualizado_em'),
                source=Value('portfolio', output_field=CharField())).values(*columns))
    if can(request.user, 'editorial.announcements'):
        choices.append(('anuncio', 'Anúncios de mesas'))
        tables = TbMesaAnuncio.objects.filter(estado='pendente')
        if query:
            tables = tables.filter(Q(titulo__icontains=query) | Q(mestre__username__icontains=query))
        if source in ('', 'anuncio'):
            queues.append(tables.order_by().annotate(
                title=F('titulo'), author=F('mestre__username'), submitted=F('atualizado_em'),
                source=Value('anuncio', output_field=CharField())).values(*columns))
    if can(request.user, 'editorial.character_stories'):
        choices.append(('historia', 'Histórias de personagens'))
        stories = pending_stories(request.user)
        if query:
            stories = stories.filter(Q(character__nome__icontains=query) | Q(author__username__icontains=query))
        if source in ('', 'historia'):
            queues.append(stories.order_by().annotate(
                title=F('character__nome'), author_name=F('author__username'), submitted=F('submitted_at'),
                source=Value('historia', output_field=CharField())).values(
                    'pk', 'title', 'author_name', 'submitted', 'source'))
    if queues:
        combined = queues[0].union(*queues[1:], all=True).order_by('submitted', 'source', 'pk')
        page = Paginator(combined, 25).get_page(request.GET.get('page'))
    else:
        page = Paginator([], 25).get_page(1)
    for row in page:
        if 'author_name' in row:
            row['author'] = row['author_name']
        row['label'] = dict(choices)[row['source']]
        if row['source'] == 'historia':
            row['url'] = reverse('gestao:story_review', args=[row['pk']])
            continue
        route, parameter, anchor = {
            'cronica': ('cronicas_review', 'item', 'review-'),
            'portfolio': ('master_gallery_review', 'item', 'work-'),
            'anuncio': ('master_dashboard', 'anuncio', 'table-'),
        }[row['source']]
        row['url'] = reverse(route) + '?' + parameter + '=' + str(row['pk']) + '#' + anchor + str(row['pk'])
    return render(request, 'home/gestao/editorial.html', _workspace(
        request, 'Revisões editoriais', management_section='editorial', entries=page,
        source_choices=choices, filters={'q': query, 'source': source},
        pagination_query=urlencode({'q': query, 'source': source})))
