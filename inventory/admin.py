from django.contrib import admin
from django.utils.html import format_html
from .models import Category, Supplier, Product, StockOperation


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'created_at')
    search_fields = ('name',)
    ordering = ('name',)


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ('name', 'contact_person', 'phone', 'email', 'address_short')
    search_fields = ('name', 'contact_person', 'phone', 'email')
    list_filter = ('created_at',)
    readonly_fields = ('created_at',)
    fieldsets = (
        ('Основная информация', {
            'fields': ('name', 'contact_person', 'email', 'phone')
        }),
        ('Адрес', {
            'fields': ('address',)
        }),
        ('Служебная информация', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    
    def address_short(self, obj):
        """Показывает сокращённый адрес (первые 50 символов)"""
        return obj.address[:50] + '...' if len(obj.address) > 50 else obj.address
    address_short.short_description = 'Адрес'


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('article', 'name', 'category', 'supplier', 'price', 'stock_status', 'min_threshold')
    list_filter = ('category', 'supplier', 'created_at')
    search_fields = ('name', 'article')
    readonly_fields = ('created_at', 'updated_at', 'get_stock_status_display')
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('name', 'article', 'category', 'supplier', 'description')
        }),
        ('Цена и остатки', {
            'fields': ('price', 'current_quantity', 'min_threshold', 'get_stock_status_display')
        }),
        ('Служебная информация', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def stock_status(self, obj):
        """Показывает визуальный статус запасов"""
        if obj.current_quantity == 0:
            color = 'red'
            status = '❌ Нет'
        elif obj.is_low_stock():
            color = 'orange'
            status = f'⚠️ Низко ({obj.current_quantity})'
        else:
            color = 'green'
            status = f'✅ OK ({obj.current_quantity})'
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color, status
        )
    stock_status.short_description = 'Статус запасов'
    
    def get_stock_status_display(self, obj):
        """Детальное отображение статуса запасов в форме"""
        return obj.get_stock_status()
    get_stock_status_display.short_description = 'Статус'


@admin.register(StockOperation)
class StockOperationAdmin(admin.ModelAdmin):
    list_display = ('operation_display', 'product', 'quantity', 'created_by', 'created_at')
    list_filter = ('operation_type', 'created_at', 'created_by')
    search_fields = ('product__name', 'product__article', 'reason')
    readonly_fields = ('created_at', 'created_by')
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Операция', {
            'fields': ('product', 'operation_type', 'quantity')
        }),
        ('Детали', {
            'fields': ('reason', 'created_by', 'created_at')
        }),
    )
    
    def operation_display(self, obj):
        """Показывает тип операции с визуальным индикатором"""
        if obj.operation_type == 'in':
            return format_html(
                '<span style="color: green; font-weight: bold;">⬆️ Приход</span>'
            )
        else:
            return format_html(
                '<span style="color: red; font-weight: bold;">⬇️ Расход</span>'
            )
    operation_display.short_description = 'Тип операции'
    
    def save_model(self, request, obj, form, change):
        """Автоматически заполняем поле created_by текущим пользователем"""
        if not change:  # Только для новых записей
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
