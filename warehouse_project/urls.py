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

# Код для автоматического создания администратора при запуске на Vercel
try:
    if not User.objects.filter(username='admin').exists():
        User.objects.create_superuser('admin', 'admin@example.com', 'pass12345')
        print("Суперпользователь создан!")
except Exception as e:
    print(f"Ошибка при создании пользователя: {e}")