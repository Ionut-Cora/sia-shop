from decimal import Decimal

from django.test import TestCase, RequestFactory

from .models import Order
from .webhook_handler import StripeWH_Handler


class StripeWebhookHandlerTests(TestCase):
    """Test Stripe webhook payment handling."""

    def setUp(self):
        """Prepare the webhook handler and test order."""

        self.factory = RequestFactory()
        self.request = self.factory.post('/checkout/wh/')
        self.handler = StripeWH_Handler(self.request)

        self.order = Order.objects.create(
            full_name='Test Customer',
            email='customer@example.com',
            phone_number='07700900123',
            street_address1='10 Test Street',
            town_or_city='London',
            postcode='SW1A 1AA',
            country='United Kingdom',
            order_total=Decimal('59.98'),
            stripe_pid='pi_test_webhook_001',
            payment_status='pending',
        )

    def test_successful_payment_marks_order_as_paid(self):
        """A successful payment should mark the order as paid."""

        event = {
            'type': 'payment_intent.succeeded',
            'data': {
                'object': {
                    'id': self.order.stripe_pid,
                    'amount_received': 5998,
                    'currency': 'gbp',
                    'status': 'succeeded',
                }
            }
        }

        response = self.handler.handle_payment_intent_succeeded(event)

        self.order.refresh_from_db()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.order.payment_status, 'paid')

    def test_failed_payment_marks_order_as_failed(self):
        """A failed payment should mark the order as failed."""

        event = {
            'type': 'payment_intent.payment_failed',
            'data': {
                'object': {
                    'id': self.order.stripe_pid,
                    'amount': 5998,
                    'currency': 'gbp',
                    'status': 'requires_payment_method',
                }
            }
        }

        response = self.handler.handle_payment_intent_payment_failed(event)

        self.order.refresh_from_db()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.order.payment_status, 'failed')

    def test_duplicate_successful_payment_event(self):
        """Duplicate successful events should not duplicate orders."""

        event = {
            'type': 'payment_intent.succeeded',
            'data': {
                'object': {
                    'id': self.order.stripe_pid,
                    'amount_received': 5998,
                    'currency': 'gbp',
                    'status': 'succeeded',
                }
            }
        }

        # Process the first successful payment event.
        first_response = self.handler.handle_payment_intent_succeeded(event)

        # Process the same event again.
        second_response = self.handler.handle_payment_intent_succeeded(event)

        self.order.refresh_from_db()

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(second_response.status_code, 200)
        self.assertEqual(self.order.payment_status, 'paid')
        self.assertEqual(Order.objects.count(), 1)
        self.assertEqual(self.order.order_total, Decimal('59.98'))

    def test_failed_payment_cannot_overwrite_paid_order(self):
        """A failed payment event must not overwrite a paid order."""

        # Mark the test order as paid.
        self.order.payment_status = 'paid'
        self.order.save()

        event = {
            'type': 'payment_intent.payment_failed',
            'data': {
                'object': {
                    'id': self.order.stripe_pid,
                    'amount': 5998,
                    'currency': 'gbp',
                    'status': 'requires_payment_method',
                }
            }
        }

        response = self.handler.handle_payment_intent_payment_failed(event)

        self.order.refresh_from_db()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.order.payment_status, 'paid')
        self.assertEqual(Order.objects.count(), 1)

    def test_successful_retry_marks_failed_order_as_paid(self):
        """A successful retry should mark a failed order as paid."""

        # Mark the test order as failed.
        self.order.payment_status = 'failed'
        self.order.save()

        event = {
            'type': 'payment_intent.succeeded',
            'data': {
                'object': {
                    'id': self.order.stripe_pid,
                    'amount_received': 5998,
                    'currency': 'gbp',
                    'status': 'succeeded',
                }
            }
        }

        response = self.handler.handle_payment_intent_succeeded(event)

        self.order.refresh_from_db()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.order.payment_status, 'paid')
        self.assertEqual(Order.objects.count(), 1)
        self.assertEqual(self.order.order_total, Decimal('59.98'))

    def test_incorrect_payment_amount_is_rejected(self):
        """An incorrect payment amount must not mark an order as paid."""

        event = {
            'type': 'payment_intent.succeeded',
            'data': {
                'object': {
                    'id': self.order.stripe_pid,
                    'amount_received': 2999,
                    'currency': 'gbp',
                    'status': 'succeeded',
                }
            }
        }

        response = self.handler.handle_payment_intent_succeeded(event)

        self.order.refresh_from_db()

        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.order.payment_status, 'pending')
        self.assertEqual(self.order.order_total, Decimal('59.98'))
        self.assertEqual(Order.objects.count(), 1)

    def test_incorrect_payment_currency_is_rejected(self):
        """A payment in the wrong currency must be rejected."""

        event = {
            'type': 'payment_intent.succeeded',
            'data': {
                'object': {
                    'id': self.order.stripe_pid,
                    'amount_received': 5998,
                    'currency': 'usd',
                    'status': 'succeeded',
                }
            }
        }

        response = self.handler.handle_payment_intent_succeeded(event)

        self.order.refresh_from_db()

        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.order.payment_status, 'pending')
        self.assertEqual(self.order.order_total, Decimal('59.98'))
        self.assertEqual(Order.objects.count(), 1)

    def test_successful_payment_without_matching_order(self):
        """An unknown PaymentIntent must not update existing orders."""

        event = {
            'type': 'payment_intent.succeeded',
            'data': {
                'object': {
                    'id': 'pi_test_unknown_999',
                    'amount_received': 5998,
                    'currency': 'gbp',
                    'status': 'succeeded',
                }
            }
        }

        response = self.handler.handle_payment_intent_succeeded(event)

        self.order.refresh_from_db()

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.content, b'Matching order not found.')
        self.assertEqual(self.order.payment_status, 'pending')
        self.assertEqual(self.order.order_total, Decimal('59.98'))
        self.assertEqual(Order.objects.count(), 1)