from decimal import Decimal
from django.db import transaction
from django.core.exceptions import ValidationError
from .models import Product, Batch, StockTransaction


class InventoryService:
    """Сервис для управления складом с учетом партий"""
    
    @staticmethod
    @transaction.atomic
    def receive_stock(product, batch_number, quantity, unit_cost, supplier, received_date, expiry_date=None):
        """Прием товара на склад с созданием партии"""
        if quantity <= 0:
            raise ValidationError("Количество должно быть положительным")
        
        batch = Batch.objects.create(
            product=product,
            batch_number=batch_number,
            quantity_received=quantity,
            quantity_remaining=quantity,
            unit_cost=unit_cost,
            received_date=received_date,
            expiry_date=expiry_date,
            supplier=supplier
        )
        
        # Создаем транзакцию прихода
        StockTransaction.objects.create(
            product=product,
            batch=batch,
            transaction_type='in',
            quantity=quantity,
            unit_cost=unit_cost,
            reason=f"Прием партии {batch_number}",
            created_by=None  # TODO: передать пользователя
        )
        
        # Обновляем общий остаток
        product.update_stock_from_batches()
        
        return batch
    
    @staticmethod
    @transaction.atomic
    def issue_stock_fifo(product, quantity_needed, reason="", created_by=None):
        """Списание товара по методу FIFO"""
        if quantity_needed <= 0:
            raise ValidationError("Количество должно быть положительным")
        
        # Получаем партии для списания
        fifo_batches = product.get_fifo_batches(quantity_needed)
        if not fifo_batches:
            raise ValidationError(f"Недостаточно товара на складе. Доступно: {product.current_stock} шт.")
        
        total_cost = Decimal('0')
        issued_quantity = 0
        
        for batch, qty_to_issue in fifo_batches:
            # Создаем транзакцию расхода
            transaction_obj = StockTransaction.objects.create(
                product=product,
                batch=batch,
                transaction_type='out',
                quantity=qty_to_issue,
                unit_cost=batch.unit_cost,
                reason=reason,
                created_by=created_by
            )
            
            # Уменьшаем остаток в партии
            batch.quantity_remaining -= qty_to_issue
            batch.save(update_fields=['quantity_remaining'])
            
            total_cost += batch.unit_cost * qty_to_issue
            issued_quantity += qty_to_issue
        
        # Обновляем общий остаток
        product.update_stock_from_batches()
        
        return {
            'issued_quantity': issued_quantity,
            'total_cost': total_cost,
            'average_cost': total_cost / issued_quantity if issued_quantity > 0 else Decimal('0')
        }