// Retrieve the Stripe configuration.
const stripePublicKey = JSON.parse(
    document.getElementById('stripe-public-key').textContent
);

const clientSecret = JSON.parse(
    document.getElementById('client-secret').textContent
);

// Initialise Stripe and the Payment Element.
const stripe = Stripe(stripePublicKey);

// Match the Stripe Payment Element to the Sia Shop brand.
const appearance = {
    theme: 'stripe',

    variables: {
        colorPrimary: '#A65E32',
        colorBackground: '#FFFFFF',
        colorText: '#24211E',
        colorDanger: '#A65E32',
        colorTextSecondary: '#70452D',
        fontFamily: 'Arial, sans-serif',
        fontSizeBase: '16px',
        spacingUnit: '4px',
        borderRadius: '8px'
    },

    rules: {
        '.Input': {
            border: '1px solid #C49A6C',
            boxShadow: 'none',
            padding: '12px'
        },

        '.Input:focus': {
            border: '1px solid #70452D',
            boxShadow: '0 0 0 3px rgba(112, 69, 45, 0.15)'
        },

        '.Label': {
            color: '#70452D',
            fontWeight: '600'
        },

        '.Tab': {
            border: '1px solid #E8D8C3',
            boxShadow: 'none'
        },

        '.Tab:hover': {
            color: '#A65E32'
        },

        '.Tab--selected': {
            borderColor: '#A65E32',
            boxShadow: 'none'
        }
    }
};

const elements = stripe.elements({
    clientSecret: clientSecret,
    appearance: appearance
});

const paymentElement = elements.create('payment');

paymentElement.mount('#payment-element');

// Retrieve the checkout form elements.
const paymentForm = document.getElementById('payment-form');
const submitButton = document.getElementById('submit-button');
const paymentErrors = document.getElementById('payment-errors');

// Handle checkout form submission.
paymentForm.addEventListener('submit', async function(event) {
    event.preventDefault();

    // Prevent repeated submissions.
    if (submitButton.disabled) {
        return;
    }

    paymentErrors.textContent = '';
    submitButton.disabled = true;
    submitButton.textContent = 'Processing Payment...';

    try {
        // Validate the Stripe payment details.
        const { error: submitError } = await elements.submit();

        if (submitError) {
            paymentErrors.textContent = submitError.message;
            return;
        }

        // Collect the delivery information.
        const formData = new FormData(paymentForm);

        // Send the checkout information to Django.
        const response = await fetch(window.location.href, {
            method: 'POST',
            body: formData,
        });

        const data = await response.json();

        // Display server-side validation errors.
        if (!response.ok || !data.success) {
            if (data.errors) {
                const errorMessages = [];

                for (const field in data.errors) {
                    for (const error of data.errors[field]) {
                        errorMessages.push(error.message);
                    }
                }

                paymentErrors.textContent = errorMessages.join(' ');
            } else {
                paymentErrors.textContent =
                    data.error || 'Unable to create your order.';
            }

            return;
        }

        // Confirm the payment using Stripe.
        const { error } = await stripe.confirmPayment({
            elements: elements,
            confirmParams: {
                return_url: data.success_url,
            },
        });

        // Display immediate payment errors.
        if (error) {
            paymentErrors.textContent =
                error.message || 'Your payment could not be completed.';
        }

    } catch (error) {
        paymentErrors.textContent =
            'Unable to process checkout. Please try again.';

    } finally {
        // Restore the checkout button if payment has not redirected.
        submitButton.disabled = false;
        submitButton.textContent = 'Pay Now';
    }
});