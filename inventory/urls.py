from django.urls import path

from . import views

app_name = 'inventory'

urlpatterns = [
    path('', views.inventory_home, name='home'),
    path('products/new/', views.product_create, name='product_create'),
    path('products/<int:pk>/edit/', views.product_edit, name='product_edit'),
]
