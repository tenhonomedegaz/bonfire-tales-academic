"""Existing collaborator membership shown without payment or entitlement writes."""

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from .subscriptions import subscription_status


@login_required(login_url='/login/')
@never_cache
@require_GET
def subscription_management(request):
    from .views import COLABORADOR_TIERS

    state = subscription_status(request.user)
    tier = next((item for item in COLABORADOR_TIERS
                 if item['key'] == state['tier']), None)
    return render(request, 'home/pages/subscription_management.html', {
        'page_title': 'Minha assinatura', 'noindex': True, 'ads_enabled': False,
        'membership': state, 'membership_tier': tier,
    })
