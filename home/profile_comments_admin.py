"""Import this module from home.admin to register wall moderation."""

from django.contrib import admin
from django.utils import timezone

from .models import TbPerfilComentario, TbPerfilComentarioCurtida


@admin.register(TbPerfilComentario)
class ProfileCommentAdmin(admin.ModelAdmin):
    list_display = ('id', 'autor', 'perfil', 'criado_em', 'removido_em', 'removido_por')
    list_filter = ('removido_em',)
    search_fields = ('texto', 'autor__username', 'perfil__username')
    list_select_related = ('autor', 'perfil', 'removido_por')
    readonly_fields = ('id', 'autor', 'perfil', 'texto', 'chave_operacao', 'criado_em',
                       'removido_em', 'removido_por')
    actions = ('soft_remove_comments',)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.action(description='Remover comentarios selecionados do mural', permissions=['change'])
    def soft_remove_comments(self, request, queryset):
        if not self.has_change_permission(request):
            return
        count = queryset.filter(removido_em__isnull=True).update(
            removido_em=timezone.now(), removido_por=request.user)
        self.message_user(request, f'{count} comentario(s) removido(s) do mural.')


@admin.register(TbPerfilComentarioCurtida)
class ProfileCommentLikeAdmin(admin.ModelAdmin):
    list_display = ('id', 'comentario_id', 'quem', 'criado_em')
    list_select_related = ('quem',)
    readonly_fields = ('id', 'comentario', 'quem', 'criado_em')
    actions = None

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
