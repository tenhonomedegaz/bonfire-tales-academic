
from django.contrib import admin
from django.urls import path, re_path, include
from django.conf import settings
import django.views.static
from home.content_maintenance import content_maintenance
from home.db_access_admin import api_key_console, api_key_revoke, api_key_rotate, api_keys
from home.db_access_api import db_collection, db_object, db_operation, db_schema

urlpatterns = [
    path('admin/api-keys/manage/', api_key_console, name='managed_api_key_console'),
    path('admin/api-keys/', api_keys, name='managed_api_keys'),
    path('admin/api-keys/<uuid:key_id>/revoke/', api_key_revoke, name='managed_api_key_revoke'),
    path('admin/api-keys/<uuid:key_id>/rotate/', api_key_rotate, name='managed_api_key_rotate'),
    path('admin/content-maintenance/<slug:package_id>/', content_maintenance),
    path('admin/', admin.site.urls),
    path('api/db/v1/schema/', db_schema, name='db_access_schema'),
    path('api/db/v1/operations/<slug:handler_name>/', db_operation, name='db_access_operation'),
    path('api/db/v1/<slug:model_name>/', db_collection, name='db_access_collection'),
    path('api/db/v1/<slug:model_name>/<str:object_pk>/', db_object, name='db_access_object'),
    path('', include('home.urls')),
]

# Serve MEDIA sempre (não só em DEBUG). O deploy atual é waitress atrás de um
# cloudflared named tunnel, sem nginx/reverse proxy separado servindo estáticos,
# então o próprio Django precisa responder por /media/ em produção (WhiteNoise
# só cobre STATIC). django.views.static.serve trata path traversal com segurança.
# Ao escalar, o ideal é mover MEDIA para object storage/CDN (R2/S3), mas isso
# fica para depois.
urlpatterns += [
    re_path(r'^media/(?P<path>.*)$', django.views.static.serve, {'document_root': settings.MEDIA_ROOT}),
]

