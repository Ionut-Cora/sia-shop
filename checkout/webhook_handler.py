import logging

from django.http import HttpResponse
from django.db import transaction

from .models import Order
from .emails import send_confirmation_email


logger = logging.getLogger(__name__)


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

        amount_received = intent['amount_received']
        currency = intent['currency']
        payment_status = intent['status']

        # Validate the payment information.
        if payment_status != 'succeeded':
            return HttpResponse(status=400)

        if currency != 'gbp':
            return HttpResponse(status=400)

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

        # Verify the received payment amount.
        expected_amount = int(order.order_total * 100)

        if amount_received != expected_amount:
            return HttpResponse(
                content='Payment amount does not match order total.',
                status=400,
            )

        # Safely update the payment status.
        with transaction.atomic():
            updated = Order.objects.filter(
                pk=order.pk,
                stripe_pid=pid,
                order_total=order.order_total,
                payment_status__in=['pending', 'failed'],
            ).update(payment_status='paid')

            if not updated:
                already_paid = Order.objects.filter(
                    pk=order.pk,
                    stripe_pid=pid,
                    order_total=order.order_total,
                    payment_status='paid',
                ).exists()

                if not already_paid:
                    return HttpResponse(status=503)

        # Send the order confirmation email.
        try:
            email_sent = send_confirmation_email(order.pk)

            if not email_sent:
                return HttpResponse(
                    content='Payment confirmed. Email delivery pending.',
                    status=503,
                )

        except Exception:
            logger.exception(
                'Confirmation email failed for order %s',
                order.order_number,
            )

            return HttpResponse(
                content='Payment confirmed. Email delivery failed.',
                status=503,
            )

        return HttpResponse(
            content='Order payment confirmed successfully.',
            status=200,
        )

    def handle_payment_intent_payment_failed(self, event):
        """Handle failed Stripe payment attempts."""

        intent = event['data']['object']
        pid = intent['id']

        # Update pending orders only.
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