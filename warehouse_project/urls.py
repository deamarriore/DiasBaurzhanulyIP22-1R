"""
URL configuration for warehouse_project project.
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView
from django.contrib.auth.models import User
from django.core.management import call_command
from django.db import connection
from accounting import views as accounting_views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("django.contrib.auth.urls")),
    path("register/", accounting_views.register, name="register"),
    path("accounting/", include("accounting.urls")),
    path("inventory/", include("inventory.urls")),
    path("", RedirectView.as_view(url="/accounting/", permanent=False)),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)


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


def ensure_inventory_product_image_column():
    """Добавляем поле image в inventory_product, если оно отсутствует."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("PRAGMA table_info(inventory_product)")
            columns = [row[1] for row in cursor.fetchall()]
            if 'image' not in columns:
                cursor.execute("ALTER TABLE inventory_product ADD COLUMN image varchar(1000)")
                print('--- ДОБАВЛЕНО ПОЛЕ inventory_product.image ---')
    except Exception as e:
        print(f"--- ERROR ENSURING PRODUCT IMAGE COLUMN: {e} ---")

initialize_database()
ensure_inventory_product_image_column()