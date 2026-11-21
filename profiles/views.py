from django.shortcuts import render
from django.contrib.auth.decorators import login_required


@login_required
def profile(request):
    """Display the logged-in customer's profile."""

    return render(request, 'profiles/profile.html')