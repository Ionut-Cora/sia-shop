from django.shortcuts import render, redirect
from .forms import OrderForm
from decimal import Decimal
from products.models import Product


def checkout(request):
    """Display and validate the checkout form."""

    bag = request.session.get('bag', {})

    if not bag:
        return redirect('view_bag')

    order_items = []
    total = Decimal('0.00')

    for item_id, item_data in bag.items():
        product = Product.objects.get(pk=item_id)

        if product.sale_price is not None and product.sale_price < product.price:
            price = product.sale_price
        else:
            price = product.price

        if isinstance(item_data, int):
            quantity = item_data
            subtotal = price * quantity
            total += subtotal

            order_items.append({
                'product': product,
                'product_name': product.name,
                'product_size': '',
                'quantity': quantity,
                'price': price,
                'subtotal': subtotal,
            })
        else:
            for size, quantity in item_data['items_by_size'].items():
                subtotal = price * quantity
                total += subtotal

                order_items.append({
                    'product': product,
                    'product_name': product.name,
                    'product_size': size,
                    'quantity': quantity,
                    'price': price,
                    'subtotal': subtotal,
                })

    if request.method == 'POST':
        form = OrderForm(request.POST)

        if form.is_valid():
            # Payment processing will be added later.
            pass
    else:
        form = OrderForm()

    context = {
        'form': form,
        'total': total,
        'order_items': order_items,
    }

    return render(request, 'checkout/checkout.html', context)