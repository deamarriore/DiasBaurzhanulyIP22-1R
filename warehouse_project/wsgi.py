import os
from django.core.wsgi import get_wsgi_application

# Указываем Django, где лежат настройки
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'warehouse_project.settings')

# Vercel ищет переменную с именем 'app' или 'application'
# Мы создаем обе, чтобы точно сработало
application = get_wsgi_application()
app = application