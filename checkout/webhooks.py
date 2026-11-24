import stripe

from django.conf import settings
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .webhook_handler import StripeWH_Handler


@csrf_exempt
@require_POST
def webhook(request):
    """Handle incoming Stripe webhook requests."""

    # Retrieve the webhook payload.
    payload = request.body

    # Retrieve the Stripe signature.
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')

    # Reject requests without a Stripe signature.
    if not sig_header:
        return HttpResponse(status=400)

    # Retrieve the webhook signing secret.
    wh_secret = settings.STRIPE_WH_SECRET

    # Prevent verification without a configured secret.
    if not wh_secret:
        return HttpResponse(status=503)

    # Verify the Stripe webhook signature.
    try:
        event = stripe.Webhook.construct_event(
            payload,
            sig_header,
            wh_secret,
        )

    except ValueError:
        return HttpResponse(status=400)

    except stripe.SignatureVerificationError:
        return HttpResponse(status=400)

    # Initialise the webhook handler.
    handler = StripeWH_Handler(request)

    # Map Stripe events to their corresponding handlers.
    event_map = {
        'payment_intent.succeeded':
            handler.handle_payment_intent_succeeded,
        'payment_intent.payment_failed':
            handler.handle_payment_intent_payment_failed,
    }

    # Retrieve the Stripe event type.
    event_type = event['type']

    # Select the appropriate event handler.
    event_handler = event_map.get(
        event_type,
        handler.handle_event,
    )

    # Execute the selected event handler.
    response = event_handler(event)

    # Return the handler response to Stripe.
    return response