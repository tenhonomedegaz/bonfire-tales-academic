"""Read-only capacity presentation backed by the site's existing rights."""

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.views.decorators.http import require_safe

from . import permissions


@login_required(login_url='/login/')
@require_safe
def character_slots(request):
    characters = list(request.user.personagens.order_by('-atualizado_em'))
    details = permissions.limite_detalhe(request.user)
    return render(request, 'home/pages/character_slots.html', {
        'page_title': 'Meus slots de personagem',
        'characters': characters,
        'slot_details': details,
        'slot_limit': permissions.get_character_limit(request.user),
        'active_count': sum(not character.arquivado for character in characters),
        'retained_count': len(characters),
    })
