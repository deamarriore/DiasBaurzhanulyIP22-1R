"""
URL configuration for warehouse_project project.
"""

from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView
from django.contrib.auth.models import User
from django.core.management import call_command 
from accounting import views as accounting_views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("django.contrib.auth.urls")),
    path("register/", accounting_views.register, name="register"),
    path("accounting/", include("accounting.urls")),
    path("inventory/", include("inventory.urls")),
    path("", RedirectView.as_view(url="/accounting/", permanent=False)),
]

def initialize_database():
    try:
        call_command('migrate', interactive=False)
        
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

initialize_database()