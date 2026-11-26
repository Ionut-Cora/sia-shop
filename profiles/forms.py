from django import forms
from .models import UserProfile


class UserProfileForm(forms.ModelForm):
    """Allow customers to update their delivery information."""

    class Meta:
        model = UserProfile

        fields = (
            'default_full_name',
            'default_phone_number',
            'default_street_address1',
            'default_street_address2',
            'default_town_or_city',
            'default_county',
            'default_postcode',
            'default_country',
        )

        labels = {
            'default_full_name': 'Full Name',
            'default_phone_number': 'Phone Number',
            'default_street_address1': 'Street Address 1',
            'default_street_address2': 'Street Address 2',
            'default_town_or_city': 'Town or City',
            'default_county': 'County',
            'default_postcode': 'Postcode',
            'default_country': 'Country',
        }