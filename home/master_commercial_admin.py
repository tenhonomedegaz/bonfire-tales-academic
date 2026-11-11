"""Independent staff review for completed tables and paid listing permission."""

from django import forms
from django.contrib import admin
from django.core.exceptions import PermissionDenied, ValidationError
from django.utils import timezone

from .master_hub import can_authorize
from .models import TbAutorizacaoVitrine, TbPerfilMestre, TbVerificacaoMesa


class EvidenceForm(forms.ModelForm):
    class Meta:
        model = TbVerificacaoMesa
        fields = ('aventura', 'aberta', 'validada', 'observacao')

    def clean(self):
        data = super().clean()
        adventure = data.get('aventura')
        if adventure and (not adventure.data or adventure.data > timezone.localdate()):
            raise ValidationError('A mesa precisa ter ocorrido até hoje.')
        if data.get('validada') and not data.get('observacao', '').strip():
            raise ValidationError('Registre a evidência da realização e da divulgação, se aberta.')
        return data


class CommercialAuthorizationForm(forms.ModelForm):
    class Meta:
        model = TbAutorizacaoVitrine
        fields = ('user', 'autorizada', 'observacao')

    def clean(self):
        data = super().clean()
        user = data.get('user')
        if data.get('autorizada') and user and not TbPerfilMestre.objects.filter(
                user=user, status_mestre='aprovado', user__is_active=True).exists():
            raise ValidationError('Autorize primeiro a participação de mestre no site.')
        if not data.get('observacao', '').strip():
            raise ValidationError('Registre o motivo da decisão comercial.')
        return data


class ReviewAdmin(admin.ModelAdmin):
    actions = None

    def has_module_permission(self, request):
        return can_authorize(request.user)

    def has_view_permission(self, request, obj=None):
        return can_authorize(request.user)

    def has_add_permission(self, request):
        return can_authorize(request.user)

    def has_change_permission(self, request, obj=None):
        return can_authorize(request.user)

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(TbVerificacaoMesa)
class VerifiedTableAdmin(ReviewAdmin):
    form = EvidenceForm
    list_display = ('aventura', 'aberta', 'validada', 'validado_por', 'validado_em')
    list_filter = ('validada', 'aberta')
    readonly_fields = ('validado_por', 'validado_em')
    raw_id_fields = ('aventura',)

    def get_readonly_fields(self, request, obj=None):
        return self.readonly_fields + (('aventura',) if obj else ())

    def save_model(self, request, obj, form, change):
        if not can_authorize(request.user) or obj.aventura.mestre_id == request.user.pk:
            raise PermissionDenied('Você não pode verificar a própria mesa.')
        obj.validado_por = request.user
        super().save_model(request, obj, form, change)


@admin.register(TbAutorizacaoVitrine)
class CommercialAuthorizationAdmin(ReviewAdmin):
    form = CommercialAuthorizationForm
    list_display = ('user', 'autorizada', 'avaliado_por', 'avaliado_em')
    list_filter = ('autorizada',)
    readonly_fields = ('avaliado_por', 'avaliado_em')
    raw_id_fields = ('user',)

    def get_readonly_fields(self, request, obj=None):
        return self.readonly_fields + (('user',) if obj else ())

    def save_model(self, request, obj, form, change):
        if not can_authorize(request.user) or obj.user_id == request.user.pk:
            raise PermissionDenied('Você não pode autorizar a própria vitrine.')
        obj.avaliado_por = request.user
        super().save_model(request, obj, form, change)
