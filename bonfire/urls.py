
from django.contrib import admin
from django.urls import path, re_path, include
from django.conf import settings
import django.views.static
from home.hunter_publication_api import hunter_publication_maintenance

urlpatterns = [
    path('admin/server-logs/hunter-publication-maintenance/', hunter_publication_maintenance),
    path('admin/', admin.site.urls),
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

