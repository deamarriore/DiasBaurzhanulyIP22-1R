"""
URL configuration for warehouse_project project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
"""

from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView
from django.contrib.auth.models import User  # Импорт для работы с пользователями

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("django.contrib.auth.urls")),
    path("accounting/", include("accounting.urls")),
    path("", RedirectView.as_view(url="/accounting/", permanent=False)),
]

# --- КОД ДЛЯ ГАРАНТИРОВАННОГО ВХОДА (Vercel Fix) ---
try:
    # Ищем пользователя admin, если нет — создаем
    user, created = User.objects.get_or_create(
        username='admin',
        defaults={'email': 'admin@example.com'}
    )
    # Принудительно обновляем пароль и права при каждом запуске
    user.set_password('pass12345')
    user.is_superuser = True
    user.is_staff = True
    user.save()
    print("--- ДОСТУП ДЛЯ ADMIN ОБНОВЛЕН: Логин: admin, Пароль: pass12345 ---")
except Exception as e:
    # Если база еще не создана (миграции не прошли), это предотвратит вылет сайта
    print(f"Ошибка при настройке админа (возможно, еще нет таблиц): {e}")