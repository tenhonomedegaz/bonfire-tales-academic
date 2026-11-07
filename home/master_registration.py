"""Registration gate and numbered roster; names alone never grant membership."""
from django.conf import settings
from django.core.exceptions import PermissionDenied

from .models import TbMestreLegado, TbPerfilMestre


def applications_open():
    return bool(getattr(settings, 'MASTER_APPLICATIONS_OPEN', False))


def number_limit():
    return int(getattr(settings, 'MASTER_ROSTER_MAX_NUMBER', 76))


def roster_for(user_id):
    return TbMestreLegado.objects.filter(
        user_id=user_id, numero__gte=1, numero__lte=number_limit()).order_by('numero', 'pk')


def registration_audit(payload, api_key):
    from .db_access import ApiProblem
    from .master_legacy import require_admin
    try:
        require_admin(getattr(api_key, 'created_by', None))
    except PermissionDenied:
        raise ApiProblem(403, 'superuser_key_required', 'Consulta exige chave de superusuario ativo.') from None
    if not isinstance(payload, dict) or set(payload) - {'offset', 'limit'}:
        raise ApiProblem(400, 'invalid_registration_audit', 'Consulta invalida.')
    offset, limit = payload.get('offset', 0), payload.get('limit', 25)
    if type(offset) is not int or offset < 0 or type(limit) is not int or not 1 <= limit <= 50:
        raise ApiProblem(400, 'invalid_registration_audit', 'Use offset >= 0 e limit 1..50.')
    query = TbPerfilMestre.objects.exclude(status_mestre='nenhum').select_related('user__profile').order_by('user_id')
    profiles = list(query[offset:offset + limit])
    identities = list(TbMestreLegado.objects.filter(user_id__in=[p.user_id for p in profiles]))
    rows = []
    for profile in profiles:
        linked = [r for r in identities if r.user_id == profile.user_id]
        community = getattr(profile.user, 'profile', None)
        rows.append({'user_id': profile.user_id, 'username': profile.user.username,
                     'discord_id': getattr(community, 'discord_user_id', None),
                     'status': profile.status_mestre, 'version': profile.versao,
                     'identities': [{'id': r.pk, 'number': r.numero, 'name': r.nome,
                                     'in_range': 1 <= r.numero <= number_limit()} for r in linked]})
    return {'applications_open': applications_open(), 'max_number': number_limit(),
            'total': query.count(), 'offset': offset, 'rows': rows}
