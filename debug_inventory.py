import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'warehouse_project.settings')
import django

django.setup()

from inventory.models import Product, Category, StockOperation
from accounting.models import Counterparty
from django.db.models import Count, F, Sum

print('products', Product.objects.count())
print('categories', Category.objects.count())
print('ops', StockOperation.objects.count())
print('customer counterparties', Counterparty.objects.filter(kind__in=['customer', 'both']).count())
print('supplier counterparties', Counterparty.objects.filter(kind__in=['supplier', 'both']).count())
print('all counterparties', Counterparty.objects.count())
print('categories annot', list(Category.objects.annotate(product_count=Count('product')).values('name','product_count')))
print('total qty', Product.objects.aggregate(total=Sum('current_quantity')))
print('recent ops', list(StockOperation.objects.select_related('product','created_by').order_by('-created_at')[:3].values('product__name','created_by__username','quantity')))
