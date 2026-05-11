from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, F, Sum
from django.shortcuts import get_object_or_404, redirect, render

from .forms import ProductForm
from .models import Category, Product, StockOperation


@login_required
def inventory_home(request):
    products = Product.objects.select_related('category', 'supplier').order_by('name')
    total_products = products.count()
    total_quantity = products.aggregate(total=Sum('current_quantity'))['total'] or 0
    total_value = products.aggregate(total=Sum(F('price') * F('current_quantity')))['total'] or 0
    low_stock_count = products.filter(current_quantity__lt=F('min_threshold')).count()
    categories = Category.objects.annotate(product_count=Count('product')).order_by('-product_count')
    low_stock_products = products.filter(current_quantity__lt=F('min_threshold')).order_by('current_quantity')[:10]
    recent_operations = StockOperation.objects.select_related('product', 'created_by').order_by('-created_at')[:10]

    return render(
        request,
        'inventory/index.html',
        {
            'products': products,
            'total_products': total_products,
            'total_quantity': total_quantity,
            'total_value': total_value,
            'low_stock_count': low_stock_count,
            'categories': categories,
            'low_stock_products': low_stock_products,
            'recent_operations': recent_operations,
        },
    )


@login_required
def product_create(request):
    if request.method == 'POST':
        form = ProductForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Товар добавлен в склад.')
            return redirect('inventory:home')
    else:
        form = ProductForm()

    return render(request, 'inventory/product_form.html', {'form': form, 'title': 'Добавить товар'})


@login_required
def product_edit(request, pk):
    product = get_object_or_404(Product, pk=pk)
    if request.method == 'POST':
        form = ProductForm(request.POST, instance=product)
        if form.is_valid():
            form.save()
            messages.success(request, 'Изменения сохранены.')
            return redirect('inventory:home')
    else:
        form = ProductForm(instance=product)

    return render(request, 'inventory/product_form.html', {'form': form, 'title': f'Редактировать товар: {product.name}'})
