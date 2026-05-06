"""
URL configuration for warehouse_project project.
"""

from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView
from django.contrib.auth.models import User
from django.core.management import call_command # Нужно для запуска миграций

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("django.contrib.auth.urls")),
    path("accounting/", include("accounting.urls")),
    path("", RedirectView.as_view(url="/accounting/", permanent=False)),
]

# ФИНАЛЬНЫЙ СКРИПТ ПОДГОТОВКИ БАЗЫ (ДЛЯ VERCEL)
def initialize_database():
    try:
        # 1. ПРИНУДИТЕЛЬНО создаем таблицы в базе /tmp/db.sqlite3
        # Это создает структуру таблиц, если их еще нет
        call_command('migrate', interactive=False)
        
        # 2. Создаем или обновляем админа
        if not User.objects.filter(username='admin').exists():
            User.objects.create_superuser(
                username='admin', 
                email='admin@example.com', 
                password='pass12345'
            )
            print("--- АДМИН СОЗДАН УСПЕШНО ---")
        else:
            user = User.objects.get(username='admin')
            user.set_password('pass12345')
            user.is_superuser = True
            user.is_staff = True
            user.save()
            print("--- ПАРОЛЬ АДМИНА ОБНОВЛЕН ---")
            
    except Exception as e:
        print(f"--- ОШИБКА БАЗЫ: {e} ---")

# Запускаем инициализацию
initialize_database()