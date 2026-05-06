from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError


class Category(models.Model):
    """Категория товара"""
    name = models.CharField(max_length=255, unique=True, verbose_name="Название категории")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    
    class Meta:
        verbose_name = "Категория"
        verbose_name_plural = "Категории"
        ordering = ['name']
    
    def __str__(self):
        return self.name


class Supplier(models.Model):
    """Поставщик товара"""
    name = models.CharField(max_length=255, unique=True, verbose_name="Название поставщика")
    contact_person = models.CharField(max_length=255, blank=True, verbose_name="Контактное лицо")
    phone = models.CharField(max_length=20, blank=True, verbose_name="Телефон")
    email = models.EmailField(blank=True, verbose_name="Email")
    address = models.TextField(verbose_name="Адрес")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    
    class Meta:
        verbose_name = "Поставщик"
        verbose_name_plural = "Поставщики"
        ordering = ['name']
    
    def __str__(self):
        return self.name


class Product(models.Model):
    """Товар"""
    name = models.CharField(max_length=255, verbose_name="Название товара")
    article = models.CharField(max_length=100, unique=True, verbose_name="Артикул")
    category = models.ForeignKey(Category, on_delete=models.PROTECT, verbose_name="Категория")
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, verbose_name="Поставщик")
    description = models.TextField(blank=True, verbose_name="Описание")
    price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Цена (руб.)")
    current_quantity = models.PositiveIntegerField(default=0, verbose_name="Текущее количество")
    min_threshold = models.PositiveIntegerField(default=10, verbose_name="Критический остаток (минимум)")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")
    
    class Meta:
        verbose_name = "Товар"
        verbose_name_plural = "Товары"
        ordering = ['name']
        indexes = [
            models.Index(fields=['article']),
            models.Index(fields=['category']),
        ]
    
    def __str__(self):
        return f"{self.name} (Артикул: {self.article})"
    
    def is_low_stock(self):
        """Проверяет, ниже ли текущее количество критического остатка"""
        return self.current_quantity < self.min_threshold
    
    def get_stock_status(self):
        """Возвращает статус запасов с описанием"""
        if self.current_quantity == 0:
            return "❌ На складе нет"
        elif self.is_low_stock():
            return f"⚠️  Низкий остаток ({self.current_quantity} шт.)"
        else:
            return f"✅ В наличии ({self.current_quantity} шт.)"


class StockOperation(models.Model):
    """История движений товара на складе"""
    OPERATION_TYPES = (
        ('in', 'Приход'),
        ('out', 'Расход'),
    )
    
    product = models.ForeignKey(Product, on_delete=models.PROTECT, verbose_name="Товар", related_name='operations')
    operation_type = models.CharField(max_length=10, choices=OPERATION_TYPES, verbose_name="Тип операции")
    quantity = models.PositiveIntegerField(verbose_name="Количество")
    reason = models.TextField(blank=True, verbose_name="Причина/Примечание")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата и время операции")
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, verbose_name="Выполнил пользователь")
    
    class Meta:
        verbose_name = "Операция со склада"
        verbose_name_plural = "Операции со склада"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['product', '-created_at']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        op_display = dict(self.OPERATION_TYPES)[self.operation_type]
        return f"{self.product.name} - {op_display} ({self.quantity} шт.) - {self.created_at.strftime('%d.%m.%Y')}"
    
    def save(self, *args, **kwargs):
        """
        Переопределяем save() для автоматического обновления количества товара в модели Product
        """
        # Проверяем, что количество не может быть отрицательным
        if self.quantity <= 0:
            raise ValidationError("Количество должно быть больше нуля")
        
        # Если это новая запись (не существует в БД)
        if self.pk is None:
            # Увеличиваем или уменьшаем количество товара в зависимости от типа операции
            if self.operation_type == 'in':
                # Приход: увеличиваем количество
                self.product.current_quantity += self.quantity
            elif self.operation_type == 'out':
                # Расход: уменьшаем количество
                # Проверяем, достаточно ли товара для расхода
                if self.product.current_quantity < self.quantity:
                    raise ValidationError(
                        f"Недостаточно товара на складе. Доступно: {self.product.current_quantity} шт., "
                        f"требуется: {self.quantity} шт."
                    )
                self.product.current_quantity -= self.quantity
            
            # Сохраняем изменения в Product
            self.product.save(update_fields=['current_quantity', 'updated_at'])
        
        # Сохраняем саму операцию
        super().save(*args, **kwargs)
