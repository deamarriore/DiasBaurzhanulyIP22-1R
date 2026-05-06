"""
URL configuration for warehouse_project project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
"""

from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView
from django.contrib.auth.models import User # Импорт для создания пользователя

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("django.contrib.auth.urls")),
    path("accounting/", include("accounting.urls")),
    path("", RedirectView.as_view(url="/accounting/", permanent=False)),
]

# АВТОМАТИЧЕСКОЕ СОЗДАНИЕ АДМИНА
# Этот код сработает сразу после запуска сервера на Vercel
try:
    # Проверяем, есть ли уже такой пользователь, чтобы не создавать дубликат
    if not User.objects.filter(username='admin').exists():
        User.objects.create_superuser(
            username='admin', 
            email='admin@example.com', 
            password='pass12345'
        )
        print("Суперпользователь успешно создан!")
    else:
        # Если пользователь есть, на всякий случай обновляем пароль
        user = User.objects.get(username='admin')
        user.set_password('pass12345')
        user.save()
        print("Пароль администратора обновлен!")
except Exception as e:
    # Если таблицы еще не созданы миграциями, просто пропускаем ошибку
    print(f"Ошибка при настройке админа: {e}")