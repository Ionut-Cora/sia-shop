from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string

from .models import Order


def send_confirmation_email(order_id):
    """Send a confirmation email for a paid order."""

    order = Order.objects.get(pk=order_id)

    # Only send confirmation emails for paid orders.
    if order.payment_status != 'paid':
        return False

    # Prevent repeated confirmation emails.
    if order.confirmation_email_sent:
        return True

    context = {
        'order': order,
    }

    # Render the email subject.
    subject = render_to_string(
        'checkout/confirmation_emails/confirmation_email_subject.txt',
        context,
    ).strip()

    # Render the email body.
    body = render_to_string(
        'checkout/confirmation_emails/confirmation_email_body.txt',
        context,
    )

    # Send the confirmation email.
    sent = send_mail(
        subject,
        body,
        settings.DEFAULT_FROM_EMAIL,
        [order.email],
        fail_silently=False,
    )

    # Record successful email delivery.
    if sent:
        Order.objects.filter(
            pk=order_id,
            payment_status='paid',
        ).update(confirmation_email_sent=True)

        return True

    return False