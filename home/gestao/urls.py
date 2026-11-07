from django.urls import path

from . import views
from .. import character_log_import_views
from .. import character_log_review_views

app_name = 'gestao'

urlpatterns = [
    path('', views.index, name='index'),
    path('pessoas/', views.people, name='people'),
    path('pessoas/<int:user_id>/', views.person, name='person'),
    path('pessoas/<int:user_id>/conceder/', views.grant, name='grant'),
    path('fichas-bot/', character_log_import_views.index, name='character_logs'),
    path('historico/conciliacao/', character_log_review_views.index, name='character_log_reviews'),
    path('historico/conciliacao/<int:entry_id>/', character_log_review_views.detail,
         name='character_log_review_detail'),
]
