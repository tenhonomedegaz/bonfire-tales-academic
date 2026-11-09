"""Shared presentation, validation and state policy for the independent GM hub."""
from datetime import datetime, timezone as utc_timezone
import uuid
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from django import forms
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.core.files.storage import default_storage
from django.utils import timezone

from .models import TbMesaAnuncio, TbPerfilMestre

ROLE_CHOICES = tuple(TbPerfilMestre._meta.get_field('modo').choices)
MASTER_MODES = ('mestre', 'ambos')
BRASILIA = ZoneInfo('America/Sao_Paulo')


def safe_public_url(value, discord=False):
    value = str(value or '').strip()
    if not value:
        return ''
    try:
        URLValidator(schemes=['https'])(value)
        parsed = urlsplit(value)
        if parsed.username or parsed.password:
            return ''
        if discord:
            import re
            if parsed.hostname not in ('discord.com', 'www.discord.com') or not re.fullmatch(r'/channels/\d+/\d+/?', parsed.path):
                return ''
    except (ValueError, ValidationError):
        return ''
    return value


def rank_catalog():
    from .character_engine import _RANK_FAIXA, aventuras_para_nivel, ouro_por_aventura
    return [dict(nome=name, minimo=lo, maximo=hi, aventuras=aventuras_para_nivel(lo),
                 ouro=ouro_por_aventura(lo), key=str(lo),
                 nivel='Dádiva épica' if lo == 21 else 'Lenda' if lo == 22 else str(lo) if lo == hi else f'{lo}–{hi}')
            for lo, hi, name in _RANK_FAIXA]


def can_review(user):
    from .gestao.policy import can
    return can(user, 'editorial.announcements')


def can_authorize(user):
    from .gestao.policy import can
    return can(user, 'masters.authorize')


def participation(profile=None):
    from .master_registration import applications_open
    get = profile.get if isinstance(profile, dict) else lambda key, default='': getattr(profile, key, default)
    mode = get('modo', 'jogador')
    mode = mode if mode in dict(ROLE_CHOICES) else 'jogador'
    status = get('status_mestre', 'nenhum')
    master = status == 'aprovado'
    mode = mode if master else 'jogador'
    return dict(modo=mode, role_label=dict(ROLE_CHOICES)[mode], is_master=master,
                applications_open=applications_open(),
                status_mestre=status, solicitado=status != 'nenhum', versao=get('versao', 0),
                nota_avaliacao=get('nota_avaliacao'),
                solicitado_em=get('solicitado_em'),
                apresentacao=get('apresentacao'), estilo=get('estilo'), disponibilidade=get('disponibilidade'),
                experiencia=get('experiencia'), combinados=get('combinados'),
                listado=bool(master and get('listado', False)))


class ParticipationForm(forms.ModelForm):
    banner_portfolio = forms.FileField(required=False, label='Banner do portfólio',
        widget=forms.FileInput(attrs={'accept':'image/png,image/jpeg,image/webp,image/gif'}),
        help_text='Até 8 MB. Este banner é independente do seu perfil de jogador.')
    remover_banner_portfolio = forms.BooleanField(required=False, label='Remover banner do portfólio')
    tema_portfolio = forms.ChoiceField(label='Tema do portfólio', choices=[('bonfire','Bonfire · gratuito')])

    def __init__(self, *args, user=None, **kwargs):
        # Old clients omit the new appearance field; preserve their preference.
        if args and args[0] is not None and 'tema_portfolio' not in args[0]:
            data = args[0].copy()
            data['tema_portfolio'] = getattr(kwargs.get('instance'), 'tema_portfolio', 'bonfire') or 'bonfire'
            args = (data, *args[1:])
        super().__init__(*args, **kwargs)
        self.fields['modo'].choices = [('mestre','Só mestre'),('ambos','Jogador e mestre')]
        if user is not None:
            from .views import _appearance_options
            self.fields['tema_portfolio'].choices = [(item['key'], item.get('label', item.get('nome', item['key'])))
                for item in _appearance_options(user, 'theme', 'perfil') if not item['locked']]
        current = self.instance.tema_portfolio or 'bonfire'
        if current not in dict(self.fields['tema_portfolio'].choices):
            self.fields['tema_portfolio'].choices += [(current, 'Preferência preservada · indisponível no momento')]

    class Meta:
        model = TbPerfilMestre
        fields = ['modo', 'apresentacao', 'estilo', 'disponibilidade', 'experiencia', 'combinados', 'listado', 'tema_portfolio']
        labels = {'modo':'Como você participa?', 'apresentacao':'Sua apresentação como mestre',
                  'estilo':'Estilo de mestragem', 'disponibilidade':'Disponibilidade',
                  'experiencia':'Minha trajetória e histórias narradas', 'combinados':'O que esperar das minhas mesas',
                  'listado':'Quero aparecer na vitrine pública de mestres'}
        widgets = {'modo':forms.RadioSelect, 'apresentacao':forms.Textarea(attrs={'rows':4}),
                   'experiencia':forms.Textarea(attrs={'rows':4}), 'combinados':forms.Textarea(attrs={'rows':3}),
                   'estilo':forms.TextInput(attrs={'placeholder':'Investigação, interpretação, exploração…'}),
                   'disponibilidade':forms.TextInput(attrs={'placeholder':'Sábados à noite · horário de Brasília'})}

    def clean(self):
        cleaned = super().clean()
        if self.instance.status_mestre != 'aprovado':
            raise ValidationError('Seu portfólio poderá ser editado após a autorização da administração.')
        return cleaned

    def clean_banner_portfolio(self):
        uploaded = self.cleaned_data.get('banner_portfolio')
        if uploaded:
            validate_banner(uploaded)
        return uploaded


class TableAnnouncementForm(forms.ModelForm):
    revisao = forms.IntegerField(min_value=0, initial=0, widget=forms.HiddenInput)
    data_missao = forms.DateField(label='Data da missão', required=False, widget=forms.DateInput(format='%Y-%m-%d', attrs={'type':'date'}),
                                  help_text='Dia em que a sessão acontecerá. Use a data do horário de Brasília.')
    hora_missao = forms.TimeField(label='Hora da missão · Brasília', required=False, widget=forms.TimeInput(format='%H:%M', attrs={'type':'time'}),
                                  help_text='Horário de início, no fuso de Brasília (UTC−3).')
    ranks = forms.MultipleChoiceField(label='Ranks aceitos', choices=(), widget=forms.CheckboxSelectMultiple,
                                      help_text='Marque todos os ranks que podem participar desta missão.')
    tags = forms.CharField(label='Tags da missão', required=False, max_length=400,
                          help_text='Palavras-chave separadas por vírgula. Ex.: investigação, exploração, iniciantes. Até 12 tags de 32 caracteres.')
    jogadores_prioritarios = forms.MultipleChoiceField(label='Jogadores prioritários', required=False, choices=(),
        widget=forms.SelectMultiple(attrs={'size':4}), help_text='Opcional. Pessoas com prioridade na seleção; não representam vaga confirmada. Use Ctrl ou ⌘ para selecionar mais de uma.')
    jogadores_obrigatorios = forms.MultipleChoiceField(label='Jogadores obrigatórios', required=False, choices=(),
        widget=forms.SelectMultiple(attrs={'size':4}), help_text='Opcional. Pessoas cuja participação é necessária, por exemplo para continuar uma história. A lista não pode ultrapassar as vagas. A confirmação continua no Discord.')
    banner = forms.FileField(label='Banner da missão', required=False,
        widget=forms.FileInput(attrs={'accept':'image/png,image/jpeg,image/webp,image/gif','data-mission-banner':''}),
        help_text='Envie PNG, JPEG, WebP ou GIF de até 8 MB. Uma imagem horizontal, idealmente 1600 × 600, destaca sua aventura.')
    remover_banner = forms.BooleanField(label='Remover banner atual', required=False)

    class Meta:
        model = TbMesaAnuncio
        fields = ['titulo', 'descricao', 'data_missao', 'hora_missao', 'duracao_minutos', 'vagas', 'ranks', 'formato',
                  'plataforma', 'mesa_url', 'tags', 'regras_url', 'jogadores_prioritarios', 'jogadores_obrigatorios',
                  'banner', 'remover_banner', 'discord_url', 'agenda_combinar',
                  'modalidade', 'cobranca', 'preco', 'preco_unidade', 'sessoes', 'cortesias', 'preco_avulso', 'inclusoes', 'condicoes']
        labels = {'titulo':'Nome da missão', 'descricao':'Descrição da missão',
                  'duracao_minutos':'Duração prevista (minutos)', 'vagas':'Vagas previstas',
                  'formato':'Tipo de missão', 'plataforma':'Plataforma', 'regras_url':'Link das regras',
                  'discord_url':'Canal da missão no Discord (opcional)', 'mesa_url':'Link da mesa',
                  'agenda_combinar':'Datas a combinar com o grupo', 'modalidade':'Participação',
                  'cobranca':'Modelo de cobrança', 'preco':'Preço em R$', 'preco_unidade':'Este preço é…',
                  'sessoes':'Sessões contratadas (sem cortesias)', 'cortesias':'Sessões adicionais de cortesia',
                  'preco_avulso':'Preço avulso por sessão (R$)', 'inclusoes':'O que está incluído', 'condicoes':'Condições específicas da oferta'}
        help_texts = {
            'titulo':'O nome que os jogadores verão na vitrine e na lista de missões.',
            'descricao':'Apresente a premissa sem spoilers, o tom da aventura, os objetivos e os combinados importantes. Separe o texto em parágrafos.',
            'vagas':'Quantidade total de participantes, incluindo os jogadores obrigatórios. Entre 3 e 12.',
            'duracao_minutos':'Tempo estimado da sessão, não uma recompensa automática. Ex.: 180 para três horas.',
            'formato':'Indique se será uma sessão única, uma missão em várias sessões ou uma campanha.',
            'plataforma':'Onde a mesa será jogada. Ex.: Roll20, Foundry ou apenas Discord.',
            'mesa_url':'Endereço HTTPS da mesa virtual. Aparece somente no anúncio da missão; não é necessário no seu portfólio.',
            'regras_url':'Opcional. Um documento HTTPS com regras ou combinados específicos desta mesa.',
            'discord_url':'Se a missão já tem um canal no servidor, informe-o aqui para direcionar inscrições. Preparar o anúncio não cria uma missão no bot.',
            'preco':'Preço de referência para a unidade e o modelo escolhidos. O total aparece antes de qualquer aceite.',
            'sessoes':'Quantidade fechada entre 1 e 52. Não é assinatura nem cobrança recorrente.',
            'cortesias':'Sem cobrança ou repasse adicional. Não reduzem a quantidade de sessões contratadas.',
            'preco_avulso':'Obrigatório para pacotes: usado no recálculo se o jogador desistir após começar.',
            'inclusoes':'Descreva preparação, plataforma, materiais e o que o grupo recebe.',
            'condicoes':'Explique datas a combinar, número de jogadores, cancelamento tardio e condições do modelo escolhido. O regulamento geral continua valendo.'}
        widgets = {'descricao':forms.Textarea(attrs={'rows':7}),
                   'discord_url':forms.URLInput(attrs={'placeholder':'https://discord.com/channels/…/…'}),
                   'inclusoes':forms.Textarea(attrs={'rows':3}), 'condicoes':forms.Textarea(attrs={'rows':4})}

    def __init__(self, *args, player_choices=(), **kwargs):
        if args and args[0] is not None:
            data = args[0].copy()
            for name, default in (('modalidade','gratuita'),('cobranca','sessao'),('preco_unidade','pessoa'),('sessoes','1'),('cortesias','0')):
                if name not in data: data[name] = str(getattr(kwargs.get('instance'),name,default))
            args = (data, *args[1:])
        super().__init__(*args, **kwargs)
        self.fields['ranks'].choices = [(rank['nome'], rank['nome']) for rank in rank_catalog()]
        for name in ('jogadores_prioritarios', 'jogadores_obrigatorios'):
            self.fields[name].choices = list(player_choices)
        for name, field in self.fields.items():
            if field.help_text:
                field.widget.attrs['aria-describedby'] = f'id_{name}_help'
        self.fields['vagas'].min_value, self.fields['vagas'].max_value = 3, 12
        self.fields['duracao_minutos'].min_value, self.fields['duracao_minutos'].max_value = 30, 720
        self.initial['tags'] = ', '.join(self.instance.tags or [])
        if self.instance.pk:
            self.initial['revisao'] = self.instance.revisao
            if self.instance.data:
                local = timezone.localtime(self.instance.data, BRASILIA)
                self.initial['data_missao'], self.initial['hora_missao'] = local.date(), local.time()
            self.initial['ranks'] = self.instance.ranks or [self.instance.rank]

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('agenda_combinar'):
            cleaned['data'] = None
        elif cleaned.get('data_missao') and cleaned.get('hora_missao'):
            value = datetime.combine(cleaned['data_missao'], cleaned['hora_missao'], tzinfo=BRASILIA)
            if value <= timezone.now():
                self.add_error('data_missao', 'Escolha uma data e hora futuras para anunciar a missão.')
            else:
                cleaned['data'] = value.astimezone(utc_timezone.utc)
        else:
            self.add_error('data_missao', 'Informe data e hora, ou marque datas a combinar.')
        if cleaned.get('modalidade') == 'paga':
            from .table_commerce import validate_offer
            try:
                validate_offer(cleaned)
            except ValidationError as error:
                self.add_error(None, error)
        else:
            # An old paid price must never leak onto a newly free invitation.
            cleaned.update(preco=None, preco_avulso=None, sessoes=1, cortesias=0, inclusoes='', condicoes='')
        required = set(cleaned.get('jogadores_obrigatorios', []))
        if required & set(cleaned.get('jogadores_prioritarios', [])):
            self.add_error('jogadores_prioritarios', 'Uma pessoa não precisa estar nas duas listas. Mantenha-a apenas em obrigatórios.')
        if len(required) > cleaned.get('vagas', 12):
            self.add_error('jogadores_obrigatorios', 'A quantidade de obrigatórios não pode ultrapassar as vagas.')
        return cleaned

    def clean_discord_url(self):
        raw = self.cleaned_data.get('discord_url', '')
        value = safe_public_url(raw, discord=True)
        if raw and not value:
            raise ValidationError('Use o link HTTPS de um canal da missão no Discord (servidor e canal).')
        return value

    def clean_mesa_url(self):
        value = self.cleaned_data.get('mesa_url', '')
        if value and not safe_public_url(value):
            raise ValidationError('Use um link HTTPS, sem credenciais na URL.')
        return value

    def clean_regras_url(self):
        value = self.cleaned_data.get('regras_url', '')
        if value and not safe_public_url(value):
            raise ValidationError('Use um link HTTPS, sem credenciais na URL.')
        return value

    def clean_tags(self):
        tags = list(dict.fromkeys(tag.strip() for tag in self.cleaned_data.get('tags', '').split(',') if tag.strip()))
        if len(tags) > 12 or any(len(tag) > 32 for tag in tags):
            raise ValidationError('Use até 12 tags, cada uma com no máximo 32 caracteres.')
        return tags

    def clean_banner(self):
        uploaded = self.cleaned_data.get('banner')
        if uploaded:
            validate_banner(uploaded)
        return uploaded

    def save(self, commit=True):
        table = super().save(commit=False)
        table.data = self.cleaned_data['data']
        table.rank = self.cleaned_data['ranks'][0]  # Retain legacy field for old consumers.
        if commit:
            table.save()
        return table

    def clean_vagas(self):
        value = self.cleaned_data['vagas']
        if not 3 <= value <= 12:
            raise ValidationError('Informe entre 3 e 12 vagas previstas.')
        return value

    def clean_duracao_minutos(self):
        value = self.cleaned_data['duracao_minutos']
        if not 30 <= value <= 720:
            raise ValidationError('Informe uma duração entre 30 e 720 minutos.')
        return value


def transition(current, action, reviewer=False):
    if action == 'rascunho':
        return 'rascunho'
    if action == 'enviar':
        return 'pendente'
    if action == 'encerrar':
        return 'encerrado'
    if reviewer and current == 'pendente' and action in ('aprovar', 'ajustes'):
        return 'publicado' if action == 'aprovar' else 'ajustes'
    raise ValidationError('Esta alteração não é permitida neste estado.')


def profile_context(user, include_tables=False):
    profile = TbPerfilMestre.objects.filter(user=user).first()
    result = {'community':participation(profile), 'participation_form':ParticipationForm(instance=profile, user=user),
              'master_mode_choices':ROLE_CHOICES, 'can_authorize':can_authorize(user),
              'can_review':can_review(user)}
    if include_tables:
        from django.db.models import Q
        from .master_commercial import visible_public_tables
        result['public_tables'] = visible_public_tables(list(TbMesaAnuncio.objects.filter(
            Q(data__gte=timezone.now()) | Q(agenda_combinar=True),
            mestre=user, estado='publicado').select_related('mestre')[:12])) if result['community']['is_master'] else []
    else:
        result['my_tables'] = list(TbMesaAnuncio.objects.filter(mestre=user).order_by('-atualizado_em')[:100])
    from .master_portfolio import portfolio_context
    result.update(portfolio_context(user, profile, public=include_tables))
    return result


def public_announcements(search='', status='', existing_urls=()):
    from django.db.models import Q
    if status not in ('', 'idle'):
        return []
    query = TbMesaAnuncio.objects.filter(Q(data__gte=timezone.now()) | Q(agenda_combinar=True), estado='publicado', mestre__is_active=True,
                                        mestre__participacao__status_mestre='aprovado').select_related('mestre')
    if search:
        query = query.filter(Q(titulo__icontains=search) | Q(descricao__icontains=search) | Q(mestre__username__icontains=search))
    from .master_commercial import visible_public_tables
    return visible_public_tables([table for table in query[:100]
                                  if not table.discord_url or table.discord_url not in existing_urls])


def validate_banner(uploaded):
    if uploaded.size > 8 * 1024 * 1024:
        raise ValidationError('Envie uma imagem de até 8 MB.')
    uploaded.seek(0)
    header = uploaded.read(16)
    uploaded.seek(0)
    extension = ('png' if header.startswith(b'\x89PNG\r\n\x1a\n') else
                 'jpg' if header.startswith(b'\xff\xd8\xff') else
                 'gif' if header.startswith((b'GIF87a', b'GIF89a')) else
                 'webp' if header.startswith(b'RIFF') and header[8:12] == b'WEBP' else None)
    if not extension:
        raise ValidationError('Envie uma imagem PNG, JPEG, GIF ou WebP. SVG e outros arquivos não são aceitos.')
    return extension


def apply_banner(table, form, save_upload=None):
    uploaded = form.cleaned_data.get('banner')
    if uploaded:
        extension = validate_banner(uploaded)
        if save_upload:
            table.banner_url = save_upload(uploaded)
        else:
            name = default_storage.save(f'mission_banners/{table.mestre_id}/{uuid.uuid4().hex}.{extension}', uploaded)
            table.banner_url = default_storage.url(name)
    elif form.cleaned_data.get('remover_banner'):
        # Retain the old file for recoverability; only detach it from this mission.
        table.banner_url = ''


def player_choices():
    from django.contrib.auth import get_user_model
    return [(str(pk), name) for pk, name in get_user_model().objects.filter(is_active=True).order_by('username').values_list('pk', 'username')[:500]]


def selected_player_names(table, choices):
    names = dict(choices)
    return {key:[names.get(str(pk), 'Conta indisponível') for pk in getattr(table,key)]
            for key in ('jogadores_prioritarios', 'jogadores_obrigatorios')}
