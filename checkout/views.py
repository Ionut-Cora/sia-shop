from decimal import Decimal
import stripe
from django.conf import settings
from django.shortcuts import render, redirect
from products.models import Product
from .forms import OrderForm


stripe.api_key = settings.STRIPE_SECRET_KEY


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

        stripe_total = int(total * 100)

    existing_intent_id = request.session.get('payment_intent_id')
    intent = None

    if existing_intent_id:
        try:
            existing_intent = stripe.PaymentIntent.retrieve(
                existing_intent_id
            )

            if (
                existing_intent.status in (
                    'requires_payment_method',
                    'requires_confirmation',
                )
                and existing_intent.currency == 'gbp'
            ):
                if existing_intent.amount != stripe_total:
                    intent = stripe.PaymentIntent.modify(
                        existing_intent_id,
                        amount=stripe_total,
                    )
                else:
                    intent = existing_intent

        except stripe.error.InvalidRequestError:
            pass

    if intent is None:
        intent = stripe.PaymentIntent.create(
            amount=stripe_total,
            currency='gbp',
            automatic_payment_methods={'enabled': True},
        )

    request.session['payment_intent_id'] = intent.id

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
        'stripe_public_key': settings.STRIPE_PUBLIC_KEY,
        'client_secret': intent.client_secret,
    }

    return render(request, 'checkout/checkout.html', context)