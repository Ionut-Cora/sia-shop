from django.shortcuts import render, redirect
from .forms import OrderForm


def checkout(request):
    """Display the checkout form."""

    bag = request.session.get('bag', {})

    if not bag:
        return redirect('view_bag')

    form = OrderForm()

    context = {
        'form': form,
    }

    return render(request, 'checkout/checkout.html', context)