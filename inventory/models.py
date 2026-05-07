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
    
    @property
    def current_stock(self):
        """Текущий остаток по партиям"""
        return sum(batch.quantity_remaining for batch in self.batches.all())
    
    def update_stock_from_batches(self):
        """Обновляет current_quantity из партий"""
        self.current_quantity = self.current_stock
        self.save(update_fields=['current_quantity', 'updated_at'])
    
    def get_fifo_batches(self, quantity_needed):
        """Возвращает партии для списания по FIFO"""
        batches = self.batches.filter(quantity_remaining__gt=0).order_by('received_date')
        result = []
        remaining = quantity_needed
        for batch in batches:
            if remaining <= 0:
                break
            available = min(remaining, batch.quantity_remaining)
            result.append((batch, available))
            remaining -= available
        return result if remaining == 0 else None


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


class Batch(models.Model):
    """Партия товара для учета FIFO"""
    product = models.ForeignKey(Product, on_delete=models.PROTECT, verbose_name="Товар", related_name='batches')
    batch_number = models.CharField(max_length=100, unique=True, verbose_name="Номер партии")
    quantity_received = models.PositiveIntegerField(verbose_name="Количество получено")
    quantity_remaining = models.PositiveIntegerField(verbose_name="Остаток в партии")
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Цена за единицу")
    received_date = models.DateField(verbose_name="Дата получения")
    expiry_date = models.DateField(null=True, blank=True, verbose_name="Срок годности")
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, verbose_name="Поставщик")
    
    class Meta:
        verbose_name = "Партия"
        verbose_name_plural = "Партии"
        ordering = ['received_date']
        indexes = [
            models.Index(fields=['product', 'received_date']),
        ]
    
    def __str__(self):
        return f"Партия {self.batch_number} - {self.product.name}"
    
    def is_expired(self):
        """Проверяет, истек ли срок годности"""
        from datetime import date
        if self.expiry_date:
            return self.expiry_date < date.today()
        return False
    
    def get_status(self):
        """Возвращает статус партии"""
        if self.is_expired():
            return "Истек срок"
        elif self.quantity_remaining == 0:
            return "Распродана"
        else:
            return "Активна"


class StockTransaction(models.Model):
    """Транзакция движения товара (приход/расход)"""
    TRANSACTION_TYPES = (
        ('in', 'Приход'),
        ('out', 'Расход'),
    )
    
    product = models.ForeignKey(Product, on_delete=models.PROTECT, verbose_name="Товар", related_name='stock_transactions')
    batch = models.ForeignKey(Batch, on_delete=models.PROTECT, null=True, blank=True, verbose_name="Партия")
    transaction_type = models.CharField(max_length=10, choices=TRANSACTION_TYPES, verbose_name="Тип транзакции")
    quantity = models.PositiveIntegerField(verbose_name="Количество")
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="Цена за единицу")
    total_cost = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True, verbose_name="Общая стоимость")
    transaction_date = models.DateTimeField(auto_now_add=True, verbose_name="Дата транзакции")
    reason = models.TextField(blank=True, verbose_name="Причина")
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, verbose_name="Выполнил")
    
    class Meta:
        verbose_name = "Транзакция склада"
        verbose_name_plural = "Транзакции склада"
        ordering = ['-transaction_date']
        indexes = [
            models.Index(fields=['product', '-transaction_date']),
            models.Index(fields=['batch', '-transaction_date']),
        ]
    
    def __str__(self):
        return f"{self.get_transaction_type_display()} {self.quantity} {self.product.name}"
    
    def save(self, *args, **kwargs):
        if self.unit_cost and self.quantity:
            self.total_cost = self.unit_cost * self.quantity
        super().save(*args, **kwargs)
