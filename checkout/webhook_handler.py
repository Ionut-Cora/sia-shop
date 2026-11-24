from django.http import HttpResponse
from django.db import transaction

from .models import Order


class StripeWH_Handler:
    """Handle Stripe webhook events."""

    def __init__(self, request):
        self.request = request

    def handle_event(self, event):
        """Handle unrecognised Stripe webhook events."""
        return HttpResponse(
            content=f'Unhandled webhook received: {event["type"]}',
            status=200,
        )

    def handle_payment_intent_succeeded(self, event):
        """Handle successful Stripe payments."""

        intent = event['data']['object']
        pid = intent['id']

        # Retrieve payment information.
        amount_received = intent['amount_received']
        currency = intent['currency']
        payment_status = intent['status']

        # Validate the payment status.
        if payment_status != 'succeeded':
            return HttpResponse(status=400)

        # Validate the payment currency.
        if currency != 'gbp':
            return HttpResponse(status=400)

        # Validate the received payment amount.
        if amount_received <= 0:
            return HttpResponse(status=400)

        # Retrieve the matching order.
        try:
            order = Order.objects.get(stripe_pid=pid)

        except Order.DoesNotExist:
            return HttpResponse(
                content='Matching order not found.',
                status=503,
            )

        # Convert the order total into pence.
        expected_amount = int(order.order_total * 100)

        # Verify that the received amount matches the order total.
        if amount_received != expected_amount:
            return HttpResponse(
                content='Payment amount does not match order total.',
                status=400,
            )

        # Safely update the order payment status.
        with transaction.atomic():
            updated = Order.objects.filter(
                pk=order.pk,
                stripe_pid=pid,
                order_total=order.order_total,
                payment_status__in=['pending', 'failed'],
            ).update(payment_status='paid')

            if not updated:
                if Order.objects.filter(
                    pk=order.pk,
                    stripe_pid=pid,
                    order_total=order.order_total,
                    payment_status='paid',
                ).exists():
                    return HttpResponse(
                        content='Order already marked as paid.',
                        status=200,
                    )

                return HttpResponse(status=503)

        return HttpResponse(
            content='Order payment confirmed successfully.',
            status=200,
        )

    def handle_payment_intent_payment_failed(self, event):
        """Handle failed Stripe payment attempts."""

        intent = event['data']['object']
        pid = intent['id']

        # Safely update pending orders only.
        with transaction.atomic():
            updated = Order.objects.filter(
                stripe_pid=pid,
                payment_status='pending',
            ).update(payment_status='failed')

            if not updated:
                if Order.objects.filter(stripe_pid=pid).exists():
                    return HttpResponse(
                        content='No payment status change required.',
                        status=200,
                    )

                return HttpResponse(
                    content='Matching order not found.',
                    status=503,
                )

        return HttpResponse(
            content='Order payment marked as failed.',
            status=200,
        )