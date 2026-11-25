from decimal import Decimal
from unittest.mock import patch, MagicMock

from django.test import TestCase, RequestFactory
from django.contrib.auth.models import User
from django.urls import reverse

from products.models import Product
from .models import Order, OrderLineItem
from .webhook_handler import StripeWH_Handler


class StripeWebhookHandlerTests(TestCase):
    """Test essential Stripe webhook functionality."""

    def setUp(self):
        """Prepare the webhook handler and test order."""

        request = RequestFactory().post('/checkout/wh/')
        self.handler = StripeWH_Handler(request)

        self.order = Order.objects.create(
            full_name='Test Customer',
            email='customer@example.com',
            phone_number='07700900123',
            street_address1='10 Test Street',
            town_or_city='London',
            postcode='SW1A 1AA',
            country='United Kingdom',
            order_total=Decimal('40.00'),
            stripe_pid='pi_test_webhook_001',
            payment_status='pending',
        )

        self.event = {
            'type': 'payment_intent.succeeded',
            'data': {
                'object': {
                    'id': self.order.stripe_pid,
                    'amount_received': 4000,
                    'currency': 'gbp',
                    'status': 'succeeded',
                }
            }
        }

    def test_successful_payment(self):
        """A successful payment should mark an order as paid."""

        response = self.handler.handle_payment_intent_succeeded(
            self.event
        )

        self.order.refresh_from_db()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.order.payment_status, 'paid')

    def test_failed_payment(self):
        """A failed payment should mark an order as failed."""

        self.event['type'] = 'payment_intent.payment_failed'
        self.event['data']['object']['status'] = (
            'requires_payment_method'
        )

        response = self.handler.handle_payment_intent_payment_failed(
            self.event
        )

        self.order.refresh_from_db()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.order.payment_status, 'failed')

    def test_duplicate_payment_event(self):
        """Repeated webhook events should not duplicate orders."""

        first_response = (
            self.handler.handle_payment_intent_succeeded(self.event)
        )

        second_response = (
            self.handler.handle_payment_intent_succeeded(self.event)
        )

        self.order.refresh_from_db()

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(second_response.status_code, 200)
        self.assertEqual(self.order.payment_status, 'paid')
        self.assertEqual(Order.objects.count(), 1)

    def test_incorrect_payment_amount(self):
        """An incorrect payment amount should be rejected."""

        self.event['data']['object']['amount_received'] = 2000

        response = self.handler.handle_payment_intent_succeeded(
            self.event
        )

        self.order.refresh_from_db()

        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.order.payment_status, 'pending')


class CheckoutPaymentRetryTests(TestCase):
    """Test essential checkout payment retry functionality."""

    def setUp(self):
        """Prepare a customer, product, order and shopping bag."""

        self.user = User.objects.create_user(
            username='testcustomer',
            email='customer@example.com',
        )

        self.product = Product.objects.create(
            name='Test Product',
            description='Product for automated testing.',
            price=Decimal('25.00'),
            sale_price=Decimal('20.00'),
            has_sizes=True,
            available_sizes='S,M,L',
        )

        self.delivery_data = {
            'full_name': 'Test Customer',
            'email': 'customer@example.com',
            'phone_number': '07700900123',
            'street_address1': '10 Test Street',
            'street_address2': '',
            'town_or_city': 'London',
            'county': 'Greater London',
            'postcode': 'SW1A 1AA',
            'country': 'United Kingdom',
        }

        self.order = Order.objects.create(
            user=self.user,
            order_total=Decimal('40.00'),
            stripe_pid='pi_test_checkout_001',
            payment_status='pending',
            **self.delivery_data,
        )

        OrderLineItem.objects.create(
            order=self.order,
            product=self.product,
            product_name=self.product.name,
            product_size='L',
            quantity=2,
            lineitem_total=Decimal('40.00'),
        )

        self.client.force_login(self.user)

        session = self.client.session
        session['bag'] = {
            str(self.product.id): {
                'items_by_size': {'L': 2},
            }
        }
        session['payment_intent_id'] = self.order.stripe_pid
        session.save()

        self.form_data = self.delivery_data.copy()
        self.form_data['payment_intent_id'] = self.order.stripe_pid

        self.intent = MagicMock()
        self.intent.id = self.order.stripe_pid
        self.intent.amount = 4000
        self.intent.currency = 'gbp'
        self.intent.status = 'requires_payment_method'

    @patch('checkout.views.stripe.PaymentIntent.retrieve')
    def test_existing_order_reuse(self, mock_retrieve):
        """A valid payment retry should reuse the existing order."""

        mock_retrieve.return_value = self.intent

        response = self.client.post(
            reverse('checkout'),
            self.form_data,
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])
        self.assertEqual(
            response.json()['order_number'],
            self.order.order_number,
        )
        self.assertEqual(Order.objects.count(), 1)
        self.assertEqual(OrderLineItem.objects.count(), 1)

    @patch('checkout.views.stripe.PaymentIntent.retrieve')
    def test_changed_shopping_bag(self, mock_retrieve):
        """Changed shopping bag contents should prevent order reuse."""

        mock_retrieve.return_value = self.intent

        session = self.client.session
        session['bag'] = {
            str(self.product.id): {
                'items_by_size': {'M': 2},
            }
        }
        session.save()

        response = self.client.post(
            reverse('checkout'),
            self.form_data,
        )

        self.assertEqual(response.status_code, 409)
        self.assertFalse(response.json()['success'])
        self.assertEqual(
            response.json()['error'],
            'Your shopping bag contents have changed.',
        )
        self.assertEqual(Order.objects.count(), 1)
        self.assertEqual(
            self.order.lineitems.get().product_size,
            'L',
        )