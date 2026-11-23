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

// Get the checkout form.
const paymentForm = document.getElementById('payment-form');

// Get the checkout submit button.
const submitButton = document.getElementById('submit-button');

// Get the payment error message container.
const paymentErrors = document.getElementById('payment-errors');

// Handle checkout form submission.
paymentForm.addEventListener('submit', function(event) {
    event.preventDefault();

    paymentErrors.textContent = 'Payment processing is not enabled yet.';
});