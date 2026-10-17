"""Character capacity and one-time MM redemption using existing site rights."""

from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import redirect, render
from django.views.decorators.http import require_safe, require_POST

from . import permissions
from .mestre_ouro import (CHARACTER_SLOT_PRICE_MM, buy_character_slot_with_mm,
                          has_unreconciled_mestre_ouro_history)
from .models import UserProfile


@login_required(login_url='/login/')
@require_safe
def character_slots(request):
    characters = list(request.user.personagens.order_by('-atualizado_em'))
    details = permissions.limite_detalhe(request.user)
    profile = UserProfile.objects.filter(user=request.user).first()
    balance = int(profile.moedas_mestragem or 0) if profile else 0
    legacy_pending = has_unreconciled_mestre_ouro_history(request.user.pk, profile)
    return render(request, 'home/pages/character_slots.html', {
        'page_title': 'Meus slots de personagem',
        'characters': characters,
        'slot_details': details,
        'slot_limit': permissions.get_character_limit(request.user),
        'active_count': sum(not character.arquivado for character in characters),
        'retained_count': len(characters),
        'slot_price_mm': CHARACTER_SLOT_PRICE_MM,
        'saldo_mm': balance,
        'slot_purchase_eligible': (permissions.is_mestre(request.user)
                                   and not details['mestre_ouro'] and not legacy_pending),
        'slot_legacy_pending': legacy_pending,
    })


@login_required(login_url='/login/')
@require_POST
def buy_character_slot(request):
    try:
        _, created = buy_character_slot_with_mm(request.user.pk)
    except ValueError as exc:
        reason = str(exc)
        if reason == 'insufficient MM balance':
            messages.error(request, 'Saldo insuficiente para o slot de 5.000 MM.')
        elif reason == 'legacy Mestre Ouro history requires review':
            messages.error(request, 'Seu histórico de Mestre Ouro precisa de revisão antes de uma nova compra.')
        else:
            messages.error(request, 'Este resgate não está disponível para sua conta.')
    else:
        if created:
            messages.success(request, 'Slot permanente concedido. O resgate de 5.000 MM foi registrado.')
        else:
            messages.info(request, 'Você já possui este slot permanente. Nenhum MM foi debitado.')
    return redirect('character_slots')
