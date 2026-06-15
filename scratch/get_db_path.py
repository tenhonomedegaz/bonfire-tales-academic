import os
import sys
import django

sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bonfire.settings')
django.setup()

from django.conf import settings
print(f"Site Database name: {settings.DATABASES['default']['NAME']}")
