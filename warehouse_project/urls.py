"""
URL configuration for warehouse_project project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
"""

from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView
from django.contrib.auth.models import User # Добавили импорт

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("django.contrib.auth.urls")),
    path("accounting/", include("accounting.urls")),
    path("", RedirectView.as_view(url="/accounting/", permanent=False)),
]

from django.contrib.auth.models import User

# Усиленная версия создания админа
try:
    # Пробуем найти или создать
    user, created = User.objects.get_or_create(
        username='admin',
        defaults={'email': 'admin@example.com'}
    )
    if created:
        user.set_password('pass12345')
        user.is_superuser = True
        user.is_staff = True
        user.save()
        print("--- АДМИН СОЗДАН УСПЕШНО ---")
    else:
        # Если админ уже есть, просто обновим ему пароль для верности
        user.set_password('pass12345')
        user.save()
        print("--- ПАРОЛЬ АДМИНА ОБНОВЛЕН ---")
except Exception as e:
    print(f"Ошибка базы: {e}")