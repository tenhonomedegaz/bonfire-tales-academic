"""Memorial público de Lenda: somente campos editoriais e feitos publicados."""

from django.http import Http404
from django.shortcuts import get_object_or_404, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_safe

from .models import TbFeitoLenda, TbPersonagem
from .ranks import character_rank


@never_cache
@require_safe
def legend_detail(request, pk):
    person = get_object_or_404(
        TbPersonagem.objects.select_related('dono', 'id_raca').prefetch_related('classes__id_classe'),
        pk=pk,
    )
    rank = character_rank(person)
    if not rank['is_lenda']:
        raise Http404()
    owner = request.user.is_authenticated and request.user.pk == person.dono_id
    preview = owner and request.GET.get('preview') == '1'
    if (not person.publico or person.arquivado) and not preview:
        raise Http404()
    classes = list(person.classes.all())
    principal = next((row for row in classes if row.principal), classes[0] if classes else None)
    character = {
        'pk': person.pk, 'nome': person.nome, 'dono': person.dono.username,
        'foto_url': person.foto_url, 'descricao': person.descricao_publica,
        'raca': person.id_raca.nome if person.id_raca_id else '',
        'classe': principal.id_classe.nome if principal else '',
    }
    feats = TbFeitoLenda.objects.filter(personagem=person, publicado=True)
    return render(request, 'home/pages/lenda.html', {
        'character': character, 'rank': rank, 'feitos': feats, 'preview': preview,
        'page_title': f'{person.nome} — Lenda de Cinéria', 'noindex': preview,
        'meta_description': f'Conheça o legado e os feitos públicos de {person.nome}, Lenda de Cinéria.',
    })
