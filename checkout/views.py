from decimal import Decimal
import stripe
from django.conf import settings
from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.views.decorators.cache import never_cache
from products.models import Product
from .forms import OrderForm
from .models import Order, OrderLineItem
from profiles.models import UserProfile


stripe.api_key = settings.STRIPE_SECRET_KEY


@never_cache
def checkout(request):
    """Display and validate the checkout form."""

    bag = request.session.get('bag', {})

    if not bag:
        return redirect('view_bag')

    order_items = []
    total = Decimal('0.00')

    for item_id, item_data in bag.items():
        # Check that the product still exists.
        try:
            product = Product.objects.get(pk=item_id)

        except Product.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'A product in your shopping bag is no longer available.',
            }, status=400)

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

    # Prevent checkout with an invalid order total.
    if stripe_total < 30:
        return JsonResponse({
            'success': False,
            'error': 'The minimum order total is £0.30.',
        }, status=400)

    existing_intent_id = request.session.get('payment_intent_id')
    
    # Verify ownership of any order linked to this payment session.
    if existing_intent_id:
        linked_order = Order.objects.filter(
            stripe_pid=existing_intent_id
        ).first()

        if linked_order is not None:
            current_user_id = (
                request.user.id
                if request.user.is_authenticated
                else None
            )

            if linked_order.user_id != current_user_id:
                return JsonResponse({
                    'success': False,
                    'error': 'Unable to access this payment session.',
                }, status=403)

    # Verify the submitted PaymentIntent ID.
    if request.method == 'POST':
        submitted_intent_id = request.POST.get('payment_intent_id')

        if not existing_intent_id or submitted_intent_id != existing_intent_id:
            return JsonResponse({
                'success': False,
                'error': 'Invalid payment session. Please refresh the checkout page.',
            }, status=400)

    intent = None

    if existing_intent_id:
        try:
            existing_intent = stripe.PaymentIntent.retrieve(existing_intent_id)

            # Prevent duplicate payments.
            if existing_intent.status in (
                'succeeded',
                'processing',
                'requires_action',
                'requires_capture',
            ):
                return JsonResponse({
                    'success': False,
                    'error': 'A payment has already been completed or is awaiting completion.',
                }, status=409)

            if (
                existing_intent.status in (
                    'requires_payment_method',
                    'requires_confirmation',
                )
                and existing_intent.currency == 'gbp'
            ):
                if existing_intent.amount != stripe_total:
                    # Prevent amount changes during form submission.
                    if request.method == 'POST':
                        return JsonResponse({
                            'success': False,
                            'error': 'Order total changed. Please refresh the checkout page.',
                        }, status=400)

                    # Prevent amount changes after order creation.
                    if Order.objects.filter(
                        stripe_pid=existing_intent_id
                    ).exists():
                        return JsonResponse({
                            'success': False,
                            'error': 'An order already exists for this payment.',
                        }, status=409)

                    intent = stripe.PaymentIntent.modify(
                        existing_intent_id,
                        amount=stripe_total,
                    )
                else:
                    intent = existing_intent

        except stripe.error.InvalidRequestError:
            return JsonResponse({
                'success': False,
                'error': 'The payment session could not be verified.',
            }, status=400)

        except stripe.error.StripeError:
            return JsonResponse({
                'success': False,
                'error': 'Payment service temporarily unavailable. Please try again.',
            }, status=503)

    if intent is None:
        # Prevent PaymentIntent replacement during form submission.
        if request.method == 'POST':
            return JsonResponse({
                'success': False,
                'error': 'Payment session expired. Please refresh the checkout page.',
            }, status=400)

        try:
            intent = stripe.PaymentIntent.create(
                amount=stripe_total,
                currency='gbp',
                automatic_payment_methods={'enabled': True},
            )

        except stripe.error.StripeError:
            return JsonResponse({
                'success': False,
                'error': 'Unable to initialise payment. Please try again.',
            }, status=503)

    request.session['payment_intent_id'] = intent.id

    if request.method == 'POST':
        form = OrderForm(request.POST)
        if form.is_valid():
            # Retrieve any existing order for this PaymentIntent.
            existing_order = Order.objects.filter(
                stripe_pid=intent.id
            ).first()

            # Verify existing order ownership.
            if existing_order is not None:
                current_user_id = (
                    request.user.id
                    if request.user.is_authenticated
                    else None
                )

                if existing_order.user_id != current_user_id:
                    return JsonResponse({
                        'success': False,
                        'error': 'Unable to access this order.',
                    }, status=403)

                # Prevent payment retries for paid orders.
                if existing_order.payment_status == 'paid':
                    return JsonResponse({
                        'success': False,
                        'error': 'This order has already been paid.',
                    }, status=409)

                # Verify that the existing order total is unchanged.
                if existing_order.order_total != total:
                    return JsonResponse({
                        'success': False,
                        'error': 'Your shopping bag total has changed.',
                    }, status=409)

                # Retrieve the existing order line items.
                existing_items = list(
                    existing_order.lineitems.values_list(
                        'product_id',
                        'product_name',
                        'product_size',
                        'quantity',
                        'lineitem_total',
                    )
                )

                # Prepare the current shopping bag items.
                current_items = [
                    (
                        item['product'].id,
                        item['product_name'],
                        item['product_size'],
                        item['quantity'],
                        item['subtotal'],
                    )
                    for item in order_items
                ]

                # Verify that the shopping bag contents are unchanged.
                if sorted(existing_items, key=str) != sorted(current_items, key=str):
                    return JsonResponse({
                        'success': False,
                        'error': 'Your shopping bag contents have changed.',
                    }, status=409)

                # Verify that the delivery information is unchanged.
                for field in form.Meta.fields:
                    if getattr(existing_order, field) != form.cleaned_data[field]:
                        return JsonResponse({
                            'success': False,
                            'error': 'Your delivery information has changed.',
                        }, status=409)

            # Prepare the order without saving it yet.
            order = form.save(commit=False)

            # Associate the order with the logged-in customer.
            if request.user.is_authenticated:
                order.user = request.user

            # Assign the server-calculated order total.
            order.order_total = total

            # Associate the order with the Stripe PaymentIntent.
            order.stripe_pid = intent.id

            # Safely reuse an existing order.
            if existing_order is not None:
                if existing_order.payment_status in ('pending', 'failed'):
                    return JsonResponse({
                        'success': True,
                        'order_number': existing_order.order_number,
                        'payment_status': existing_order.payment_status,
                        'success_url': request.build_absolute_uri(
                            reverse(
                                'checkout_success',
                                args=[existing_order.order_number],
                            )
                        ),
                    })

                return JsonResponse({
                    'success': False,
                    'error': 'This order cannot be reused.',
                }, status=409)

            else:
                try:
                    # Save the order and line items together.
                    with transaction.atomic():
                        order.save()

                        # Loop through the order items.
                        for item in order_items:
                            OrderLineItem.objects.create(
                                order=order,
                                product=item['product'],
                                product_name=item['product_name'],
                                product_size=item['product_size'],
                                quantity=item['quantity'],
                                lineitem_total=item['subtotal'],
                            )

                except IntegrityError:
                    return JsonResponse({
                        'success': False,
                        'error': 'Unable to create the order due to a database conflict.',
                    }, status=409)

                # Return successful order creation response.
                return JsonResponse({
                    'success': True,
                    'order_number': order.order_number,
                    'payment_status': order.payment_status,
                    'success_url': request.build_absolute_uri(
                        reverse(
                            'checkout_success',
                            args=[order.order_number],
                        )
                    ),
                })

        # Return checkout validation errors.
        return JsonResponse({
            'success': False,
            'errors': form.errors.get_json_data(),
        }, status=400)
    else:
        # Prepopulate delivery information for registered customers.
        if request.user.is_authenticated:
            user_profile, created = UserProfile.objects.get_or_create(
                user=request.user
            )

            form = OrderForm(initial={
                'full_name': user_profile.default_full_name,
                'email': request.user.email,
                'phone_number': user_profile.default_phone_number,
                'street_address1': user_profile.default_street_address1,
                'street_address2': user_profile.default_street_address2,
                'town_or_city': user_profile.default_town_or_city,
                'county': user_profile.default_county,
                'postcode': user_profile.default_postcode,
                'country': user_profile.default_country,
            })

        else:
            form = OrderForm()

    context = {
        'form': form,
        'total': total,
        'order_items': order_items,
        'stripe_public_key': settings.STRIPE_PUBLIC_KEY,
        'client_secret': intent.client_secret,
        'payment_intent_id': intent.id,
    }

    return render(request, 'checkout/checkout.html', context)


@never_cache
def checkout_success(request, order_number):
    """Display the result of a checkout payment."""

    order = get_object_or_404(
        Order,
        order_number=order_number,
    )

    # Verify that the customer can access this order.
    if order.user_id is not None:
        if (
            not request.user.is_authenticated
            or request.user.id != order.user_id
        ):
            return redirect('view_bag')

    else:
        if not order.stripe_pid or order.stripe_pid not in (
            request.session.get('payment_intent_id'),
            request.session.get('completed_payment_intent_id'),
        ):
            return redirect('view_bag')

    # Clear the shopping bag only after confirmed payment.
    if order.payment_status == 'paid':
        if request.session.get('payment_intent_id') == order.stripe_pid:
            request.session['completed_payment_intent_id'] = order.stripe_pid
            request.session.pop('bag', None)
            request.session.pop('payment_intent_id', None)

    context = {
        'order': order,
    }

    return render(
        request,
        'checkout/checkout_success.html',
        context,
    )