from django.db.models import Q
from django.shortcuts import render, get_object_or_404
from .models import Product


def all_products(request):
    products = Product.objects.all()

    query = request.GET.get('q')

    if query:
        products = products.filter(
            Q(name__icontains=query) | Q(description__icontains=query)
        )

    category = request.GET.get('category')

    if category:
        products = products.filter(category__name=category)

    sort = request.GET.get('sort', 'price')

    if sort == 'rating':
        products = products.order_by('-rating')
    elif sort == 'category':
        products = products.order_by('category__name')
    elif sort == 'name':
        products = products.order_by('name')
    else:
        products = products.order_by('price')

    context = {
        'products': products,
    }

    return render(request, 'products/products.html', context)

def product_detail(request, product_id):
    """Display an individual product."""

    product = get_object_or_404(Product, pk=product_id)

    context = {
        'product': product,
    }

    return render(request, 'products/product_detail.html', context)