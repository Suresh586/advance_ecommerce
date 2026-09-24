from django.shortcuts import render,redirect
from django.http import HttpResponse
from carts.models import CartItem
from .forms import OrderForm
import datetime
from store.models import Product
from django.core.mail import EmailMessage
from django.template.loader import  render_to_string

# Create your views here.



from .models import Order, Payment, OrderProduct

def payments(request):

    order_number = request.GET.get('order_number')

    if not order_number:
        return redirect('store')

    try:
        order = Order.objects.get(
            order_number=order_number,
            is_ordered=False
        )
    except Order.DoesNotExist:
        return redirect('store')

    if request.method == "POST":

        payment_method = request.POST.get('payment_method')

        # 1. Create Payment
        payment = Payment.objects.create(
            user=request.user,
            payment_id='COD' + str(order.id),
            payment_method=payment_method,
            amount_paid=order.order_total,
            status='Pending'
        )

        # 2. Get cart items
        cart_items = CartItem.objects.filter(user=request.user)

        # 3. Create OrderProduct for every CartItem
        for cart_item in cart_items:

            order_product = OrderProduct()

            order_product.order = order
            order_product.payment = payment
            order_product.user = request.user
            order_product.product = cart_item.product
            order_product.quantity = cart_item.quantity
            order_product.product_price = cart_item.product.price
            order_product.ordered = True

            # First save OrderProduct
            order_product.save()

            # Then copy variations from CartItem
            product_variation = cart_item.variations.all()
            order_product.variations.set(product_variation)

            product=Product.objects.get(id=cart_item.product_id)
            product.stock -= cart_item.quantity
            product.save()

        # 4. Attach payment to order
        order.payment = payment
        order.is_ordered = True
        order.save()

        # 5. Delete cart items
        cart_items.delete()
   
        mail_subject='Thank you for you order'
        message=render_to_string('orders/order_successful_email.html',{
            'user':request.user,
            'order':order,
            
        })
        to_email=request.user.email
        send_email=EmailMessage(mail_subject,message,to=[to_email])
        send_email.send()    
            

        return redirect('order_complete',order_number=order.order_number)

def place_order(request, total=0, quantity=0):

    current_user = request.user

    cart_items = CartItem.objects.filter(user=current_user)

    cart_count = cart_items.count()

    if cart_count <= 0:
        return redirect('store')

    grand_total = 0
    tax = 0

    for cart_item in cart_items:
        total += cart_item.product.price * cart_item.quantity
        quantity += cart_item.quantity

    tax = (2 * total) / 100
    grand_total = total + tax

    if request.method == "POST":

        form = OrderForm(request.POST)

        if form.is_valid():

            data = Order()

            data.user = current_user
            data.first_name = form.cleaned_data['first_name']
            data.last_name = form.cleaned_data['last_name']
            data.phone = form.cleaned_data['phone']
            data.email = form.cleaned_data['email']
            data.address_line_1 = form.cleaned_data['address_line_1']
            data.address_line_2 = form.cleaned_data['address_line_2']
            data.country = form.cleaned_data['country']
            data.state = form.cleaned_data['state']
            data.city = form.cleaned_data['city']
            data.order_note = form.cleaned_data['order_note']

            data.order_total = grand_total
            data.tax = tax
            data.ip = request.META.get('REMOTE_ADDR')

            data.save()

            yr = int(datetime.date.today().strftime('%Y'))
            dt = int(datetime.date.today().strftime('%d'))
            mt = int(datetime.date.today().strftime('%m'))

            d = datetime.date(yr, mt, dt)

            current_date = d.strftime("%Y%m%d")

            order_number = current_date + str(data.id)

            data.order_number = order_number
            data.save()
            order=Order.objects.get(user=current_user,is_ordered=False,order_number=order_number)
            context={
                'order':order,
                'cart_items':cart_items,
                'total':total,
                'tax':tax,
                'grand_total':grand_total
            }

            return render (request,'orders/payments.html',context)

        else:
            print(form.errors)

    return redirect('checkout')

def order_complete(request, order_number):

    try:
        order = Order.objects.get(
            order_number=order_number,
            is_ordered=True
        )
    except Order.DoesNotExist:
        return redirect('store')

    order_products = OrderProduct.objects.filter(
        order=order
    )

    subtotal = 0

    for order_product in order_products:
        subtotal += order_product.product_price * order_product.quantity

    context = {
        'order': order,
        'order_products': order_products,
        'subtotal': subtotal,
        'tax': order.tax,
        'grand_total': order.order_total,
    }

    return render(
        request,
        'orders/order_complete.html',
        context
    )