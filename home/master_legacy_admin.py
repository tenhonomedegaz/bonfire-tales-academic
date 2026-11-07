"""Superuser-only import, attribution and explicit wallet reconciliation."""
from django import forms
from django.contrib import admin, messages
from django.contrib.auth import get_user_model
from django.core import signing
from django.core.exceptions import ValidationError
from django.db import DatabaseError, transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import path, reverse
from django.utils.html import format_html

from .master_legacy import bind_master, discover_bot_links, import_archive, require_admin
from .models import TbImportacaoMestre, TbMestreLegado, TbRegistroMestreLegado, TbRevisaoMissaoBot

SALT = 'home.master-legacy.import'


class ImportForm(forms.Form):
    fonte = forms.CharField(max_length=160, initial='mercado-mestres', label='Identificador da fonte')
    arquivo = forms.FileField(label='Planilha Excel (.xlsx)')


class BindForm(forms.Form):
    user = forms.ModelChoiceField(get_user_model().objects.filter(is_active=True).order_by('username'), label='Conta do site')
    wallet_mode = forms.ChoiceField(label='Conciliacao de moedas', choices=[
        ('defer', 'Somente vincular cadastro; nao alterar moedas agora'),
        ('empty', 'Importar somente se a carteira estiver vazia'),
        ('add', 'Somei e conferi: adicionar o saldo legado ao atual'),
        ('replace', 'Conferi sobreposicao: saldo da planilha substitui o saldo atual')])
    expected_balance = forms.IntegerField(required=False, label='Saldo MM atual conferido (para somar/substituir)')
    expected_events = forms.IntegerField(required=False, label='Moedas de Evento atuais conferidas')


def import_view(model_admin, request):
    require_admin(request.user)
    context = {**model_admin.admin_site.each_context(request), 'opts': model_admin.model._meta,
               'title': 'Importar mercado de mestres', 'form': ImportForm()}
    if request.method == 'POST':
        try:
            if request.POST.get('confirmar'):
                saved = signing.loads(request.POST.get('payload', ''), salt=SALT, max_age=900)
                if not TbImportacaoMestre.objects.filter(fonte=saved['source']).exists():
                    from .master_legacy_api import _backup
                    _backup()
                archive, created = import_archive(saved['plan'], saved['source'], actor=request.user)
                messages.success(request, 'Historico importado. Vincule os mestres ou confira a autoria no bot.'
                                 if created else 'Esta planilha ja foi importada; nenhum saldo foi duplicado.')
                return redirect(reverse('admin:home_tbmestrelegado_changelist') + f'?importacao__id__exact={archive.pk}')
            form = ImportForm(request.POST, request.FILES)
            context['form'] = form
            if form.is_valid():
                from .master_legacy_workbook import parse_workbook
                upload = form.cleaned_data['arquivo']
                if upload.size > 8 * 1024 * 1024:
                    raise ValidationError('Planilha deve ter ate 8 MB.')
                plan = parse_workbook(upload)
                context.update(plan=plan, payload=signing.dumps(
                    {'source': form.cleaned_data['fonte'], 'plan': plan}, salt=SALT, compress=True))
        except (ValidationError, signing.BadSignature, ValueError, KeyError, TypeError, OSError) as exc:
            messages.error(request, str(exc)[:500])
    return render(request, 'admin/home/master_legacy/import.html', context)


@admin.register(TbImportacaoMestre)
class LegacyImportAdmin(admin.ModelAdmin):
    list_display = ('fonte', 'checksum', 'criado_em', 'criado_por')
    readonly_fields = ('fonte', 'checksum', 'dados', 'criado_em', 'criado_por')
    change_list_template = 'admin/home/master_legacy/change_list.html'

    def get_urls(self):
        return [path('importar/', self.admin_site.admin_view(lambda request: import_view(self, request)),
                     name='home_tbimportacaomestre_importar')] + super().get_urls()

    def has_module_permission(self, request):
        return request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_active and request.user.is_superuser

    has_change_permission = has_view_permission

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(TbMestreLegado)
class LegacyMasterAdmin(LegacyImportAdmin):
    list_display = ('numero', 'nome', 'user', 'discord_id', 'saldo_mm', 'moedas_evento',
                    'carteira_importada_em', 'conciliacao', 'vincular_link')
    list_filter = ('importacao', 'carteira_importada_em')
    search_fields = ('nome', 'rotulo_original', 'user__username', 'discord_id')
    readonly_fields = tuple(field.name for field in TbMestreLegado._meta.fields)
    change_list_template = 'admin/change_list.html'
    actions = ['conferir_bot']

    def get_urls(self):
        return [path('<int:object_id>/vincular/', self.admin_site.admin_view(self.bind_view),
                     name='home_tbmestrelegado_vincular')] + admin.ModelAdmin.get_urls(self)

    @admin.display(description='Atribuicao')
    def vincular_link(self, obj):
        return format_html('<a href="{}">Vincular / conciliar</a>',
                           reverse('admin:home_tbmestrelegado_vincular', args=[obj.pk]))

    def bind_view(self, request, object_id):
        require_admin(request.user)
        identity = get_object_or_404(TbMestreLegado, pk=object_id)
        form = BindForm(request.POST or None, initial={'user': identity.user_id})
        if request.method == 'POST' and form.is_valid():
            try:
                bind_master(identity.pk, form.cleaned_data.pop('user').pk, actor=request.user, **form.cleaned_data)
                messages.success(request, 'Identidade vinculada. Confira o estado da conciliacao de moedas.')
                return redirect('admin:home_tbmestrelegado_changelist')
            except ValidationError as exc:
                form.add_error(None, exc)
        return render(request, 'admin/home/master_legacy/bind.html', {
            **self.admin_site.each_context(request), 'opts': self.model._meta,
            'title': f'Vincular {identity}', 'identity': identity, 'form': form})

    @admin.action(description='Conferir autoria de todas as publicacoes no bot e vincular casos inequivocos')
    def conferir_bot(self, request, queryset):
        require_admin(request.user)
        for archive_id in queryset.values_list('importacao_id', flat=True).distinct():
            try:
                with transaction.atomic():
                    result = discover_bot_links(archive_id)
                messages.success(request, str(result))
            except (ValidationError, DatabaseError):
                messages.error(request, 'Nao foi possivel concluir a leitura do bot; nenhum vinculo parcial foi aplicado.')


@admin.register(TbRegistroMestreLegado)
class LegacyRecordAdmin(LegacyImportAdmin):
    list_display = ('mestre', 'tipo', 'titulo', 'data', 'valor_mm', 'bot_quest_id', 'transacao')
    list_filter = ('tipo', 'mestre__importacao')
    search_fields = ('mestre__nome', 'titulo', 'bot_quest_id')
    readonly_fields = tuple(field.name for field in TbRegistroMestreLegado._meta.fields)
    change_list_template = 'admin/change_list.html'

    def get_urls(self):
        return admin.ModelAdmin.get_urls(self)


@admin.register(TbRevisaoMissaoBot)
class MissionReviewAdmin(LegacyImportAdmin):
    list_display = ('quest_id', 'master_name', 'decision', 'adventures', 'master_mm', 'financial_mode', 'receipt')
    list_filter = ('decision', 'financial_mode')
    search_fields = ('quest_id', 'master_name', 'master_discord_id', 'canonical_id')
    readonly_fields = tuple(field.name for field in TbRevisaoMissaoBot._meta.fields)
    change_list_template = 'admin/change_list.html'

    def get_urls(self):
        return admin.ModelAdmin.get_urls(self)
