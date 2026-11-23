// Read the Stripe publishable key from the Django template.
const stripePublicKey = JSON.parse(
    document.getElementById('stripe-public-key').textContent
);

// Initialize Stripe.
const stripe = Stripe(stripePublicKey);

// Read the PaymentIntent client secret from the Django template.
const clientSecret = JSON.parse(
    document.getElementById('client-secret').textContent
);

// Initialize Stripe Elements using the PaymentIntent client secret.
const elements = stripe.elements({
    clientSecret: clientSecret
});

// Create the Stripe Payment Element.
const paymentElement = elements.create('payment');

// Mount the Payment Element onto the checkout page.
paymentElement.mount('#payment-element');