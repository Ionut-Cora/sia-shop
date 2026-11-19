from django.shortcuts import render, redirect, get_object_or_404
from products.models import Product


def view_bag(request):
    """Display the shopping bag."""

    bag = request.session.get('bag', {})
    bag_items = []
    total = 0

    for item_id, item_data in bag.items():
        product = get_object_or_404(Product, pk=item_id)
        unit_price = product.price

        if product.sale_price and product.sale_price < product.price:
            unit_price = product.sale_price

        if isinstance(item_data, dict):
            for size, quantity in item_data['items_by_size'].items():
                line_total = unit_price * quantity
                total += line_total

                bag_items.append({
                    'item_id': item_id,
                    'product': product,
                    'size': size,
                    'quantity': quantity,
                    'unit_price': unit_price,
                    'line_total': line_total,
                })
        else:
            line_total = unit_price * item_data
            total += line_total

            bag_items.append({
                'item_id': item_id,
                'product': product,
                'size': None,
                'quantity': item_data,
                'unit_price': unit_price,
                'line_total': line_total,
            })

    context = {
        'bag': bag,
        'bag_items': bag_items,
        'total': total,
    }

    return render(request, 'bag/bag.html', context)

def add_to_bag(request, item_id):
    """Add a product and its selected size to the shopping bag."""

    product = get_object_or_404(Product, pk=item_id)

    if request.method == 'POST':
        try:
            quantity = int(request.POST.get('quantity', 1))
        except (ValueError, TypeError):
            return redirect('view_bag')

        if quantity < 1 or quantity > 99:
            return redirect('view_bag')
        
        size = request.POST.get('size')

        if product.has_sizes:
            if size not in product.get_available_sizes():
                return redirect('view_bag')
        else:
            if size:
                return redirect('view_bag')
            
        bag = request.session.get('bag', {})
        item_id = str(item_id)

        if size:
            if item_id in bag:
                if isinstance(bag[item_id], int):
                    bag[item_id] = {'items_by_size': {}}

                if size in bag[item_id]['items_by_size']:
                    current_quantity = bag[item_id]['items_by_size'][size]

                    if current_quantity + quantity > 99:
                        return redirect('view_bag')

                    bag[item_id]['items_by_size'][size] += quantity
                else:
                    bag[item_id]['items_by_size'][size] = quantity
            else:
                bag[item_id] = {
                    'items_by_size': {
                        size: quantity
                    }
                }
        else:
            if item_id in bag:
                current_quantity = bag[item_id]

                if current_quantity + quantity > 99:
                    return redirect('view_bag')

                bag[item_id] += quantity
            else:
                bag[item_id] = quantity

        request.session['bag'] = bag

    return redirect('view_bag')