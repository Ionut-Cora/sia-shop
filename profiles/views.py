from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.cache import never_cache

from checkout.models import Order
from .models import UserProfile
from .forms import UserProfileForm


@login_required
@never_cache
def profile(request):
    """Display and update the customer's profile."""

    user_profile, created = UserProfile.objects.get_or_create(
        user=request.user
    )

    if request.method == 'POST':
        form = UserProfileForm(
            request.POST,
            instance=user_profile,
        )

        if form.is_valid():
            form.save()

            messages.success(
                request,
                'Your profile has been updated successfully.',
            )

            return redirect('profile')

    else:
        form = UserProfileForm(instance=user_profile)

    # Retrieve the customer's paid orders.
    orders = Order.objects.filter(
        user=request.user,
        payment_status='paid',
    ).order_by('-date')

    context = {
        'form': form,
        'orders': orders,
    }

    return render(
        request,
        'profiles/profile.html',
        context,
    )


@login_required
@never_cache
def order_history(request, order_number):
    """Display an individual order belonging to the customer."""

    order = get_object_or_404(
        Order,
        order_number=order_number,
        user=request.user,
        payment_status='paid',
    )

    context = {
        'order': order,
    }

    return render(
        request,
        'profiles/order_history.html',
        context,
    )