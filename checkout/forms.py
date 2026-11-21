from django import forms
from .models import Order


class OrderForm(forms.ModelForm):
    """Form for collecting customer delivery information."""

    class Meta:
        model = Order
        fields = (
            'full_name',
            'email',
            'phone_number',
            'street_address1',
            'street_address2',
            'town_or_city',
            'county',
            'postcode',
            'country',
        )

    def clean_full_name(self):
        """Ensure the customer enters a valid full name."""

        full_name = self.cleaned_data.get('full_name', '').strip()

        if len(full_name) < 2:
            raise forms.ValidationError(
                'Please enter a name with at least 2 characters.'
            )

        return full_name