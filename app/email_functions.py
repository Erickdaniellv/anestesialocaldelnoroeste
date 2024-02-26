from flask_mail import Message
from . import mail
from .models import Order, OrderItem, Usuario, ShippingAddress
from flask import render_template

def send_confirmation_email(order_id):
    order = Order.query.get(order_id)
    if not order:
        print(f"No se encontró la orden con ID {order_id}")
        return

    items = OrderItem.query.filter_by(order_id=order_id).all()

    # Determinar la dirección de correo electrónico del destinatario
    if order.user_id:
        user = Usuario.query.get(order.user_id)
        recipient_email = user.email
    else:
        recipient_email = order.guest_email

    additional_email = "refacajeme@refacajeme.com"

    
    msg = Message("Confirmación de Pedido", recipients=[recipient_email, additional_email])
    shipping_address = ShippingAddress.query.filter_by(order_id=order.id).first()
    email = order.guest_email if order.guest_email else (Usuario.query.get(order.user_id).email if order.user_id else None)

    msg.html = render_template("email_confirmation.html", order=order, items=items, shipping_address=shipping_address)
    try:
        mail.send(msg)
    except Exception as e:
        print("Error al enviar el correo de confirmación: ", e)




