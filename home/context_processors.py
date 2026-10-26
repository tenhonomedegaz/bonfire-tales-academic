from django.conf import settings

from .models import UserProfile


def master_review(request):
    """Expose the review queue only to users allowed to authorize masters."""
    from .master_participation import can_authorize
    from .models import TbPerfilMestre

    allowed = can_authorize(request.user)
    return {
        'master_review_access': allowed,
        'pending_master_requests_count': (
            TbPerfilMestre.objects.filter(status_mestre='pendente').count() if allowed else 0
        ),
    }


def user_profile(request):
    """Ensure `profile` is always available in templates for authenticated users."""
    if request.user.is_authenticated:
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        return {'user_profile': profile}
    return {'user_profile': None}


def site_presentation(request):
    """Metadados e publicidade ficam opt-in por página.

    O Google não permite inventário em telas de login, navegação, erro ou sem
    conteúdo editorial. Views editoriais precisam declarar ``ads_enabled=True``.
    """
    private_prefixes = (
        '/admin/', '/api/', '/wiki/', '/login/', '/logout/', '/cadastro/',
        '/recuperar-senha/', '/perfil/', '/sistemas/criacao-de-ficha/',
        '/sistemas/pathbuilder/', '/jogador/personagens/', '/mestre/mercado-de-mestre/',
        '/mercado/comunidade/',
    )
    # O mapa é uma ferramenta pública, não uma página editorial. Mantê-lo fora
    # do índice evita que sua interface seja avaliada como conteúdo superficial.
    tool_paths = ('/mapa/', '/mapa')
    return {
        'site_origin': getattr(settings, 'SITE_ORIGIN', 'https://bonfiretales.com.br').rstrip('/'),
        'adsense_publisher_id': getattr(settings, 'ADSENSE_PUBLISHER_ID', ''),
        'adsense_enabled': bool(getattr(settings, 'ADSENSE_ENABLED', False)),
        'adsense_sidebar_slot': getattr(settings, 'ADSENSE_SIDEBAR_SLOT', ''),
        'adsense_horizontal_slot': getattr(settings, 'ADSENSE_HORIZONTAL_SLOT', ''),
        'default_noindex': (
            request.path.startswith(private_prefixes)
            or request.path in tool_paths
        ),
    }
