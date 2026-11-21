from django.shortcuts import render, redirect
from .forms import OrderForm


def checkout(request):
    """Display and validate the checkout form."""

    bag = request.session.get('bag', {})

    if not bag:
        return redirect('view_bag')

    if request.method == 'POST':
        form = OrderForm(request.POST)

        if form.is_valid():
            # Payment processing will be added later.
            pass
    else:
        form = OrderForm()

    context = {
        'form': form,
    }

    return render(request, 'checkout/checkout.html', context)