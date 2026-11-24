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
paymentForm.addEventListener('submit', async function(event) {
    event.preventDefault();

    // Clear previous error messages.
    paymentErrors.textContent = '';

    // Disable the submit button.
    submitButton.disabled = true;

    // Collect the checkout form data.
    const formData = new FormData(paymentForm);

    try {
        // Send the checkout form data to Django.
        const response = await fetch(window.location.href, {
            method: 'POST',
            body: formData,
        });

        // Read the JSON response.
        const data = await response.json();

        if (response.ok && data.success) {
            paymentErrors.textContent = 'Pending order created successfully.';

        } else if (data.errors) {
            // Collect Django form validation errors.
            const errorMessages = [];

            for (const field in data.errors) {
                for (const error of data.errors[field]) {
                    errorMessages.push(error.message);
                }
            }

            // Display the validation errors.
            paymentErrors.textContent = errorMessages.join(' ');

        } else {
            paymentErrors.textContent = data.error || 'Order creation failed.';
        }

    } catch (error) {
        paymentErrors.textContent = 'Unable to process checkout. Please try again.';

    } finally {
        // Re-enable the submit button.
        submitButton.disabled = false;
    }
});