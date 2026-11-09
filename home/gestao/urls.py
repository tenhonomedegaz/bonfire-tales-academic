from django.urls import path

from . import views
from . import request_views
from . import role_policy_views
from . import training_views
from . import character_profile_views
from . import editorial_views
from . import story_views
from .. import character_log_import_views
from .. import character_log_review_views

app_name = 'gestao'

urlpatterns = [
    path('', views.index, name='index'),
    path('solicitacoes/', request_views.index, name='requests'),
    path('solicitacoes/nova/', request_views.create, name='request_create'),
    path('solicitacoes/<int:pk>/', request_views.detail, name='request_detail'),
    path('solicitacoes/<int:pk>/treinamento/', training_views.register, name='request_training'),
    path('solicitacoes/<int:pk>/dados/', character_profile_views.correct, name='request_profile'),
    path('cargos/', role_policy_views.index, name='role_policy'),
    path('editorial/', editorial_views.index, name='editorial'),
    path('historias/<int:pk>/', story_views.review, name='story_review'),
    path('personagens/<int:pk>/treinamentos/', training_views.open_case, name='training_case'),
    path('personagens/<int:pk>/dados/', character_profile_views.open_case, name='profile_case'),
    path('pessoas/', views.people, name='people'),
    path('pessoas/<int:user_id>/', views.person, name='person'),
    path('pessoas/<int:user_id>/conceder/', views.grant, name='grant'),
    path('pessoas/<int:user_id>/cargos/', views.roles, name='roles'),
    path('fichas-bot/', character_log_import_views.index, name='character_logs'),
    path('historico/conciliacao/', character_log_review_views.index, name='character_log_reviews'),
    path('historico/conciliacao/<int:entry_id>/', character_log_review_views.detail,
         name='character_log_review_detail'),
]
