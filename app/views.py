from .models import Producto, Usuario, Cartitem, Cartsession, Order, OrderItem, ShippingAddress, Contacto
from flask import make_response, render_template, request, jsonify, redirect, url_for, flash, send_from_directory
from . import db, limiter, mail, csrf
from .forms import ProductoForm, UserProfileForm, LoginForm, RegistrationForm, ChangePasswordForm, PasswordRecoveryForm, ContactForm
from flask_login import login_user, logout_user, current_user, login_required
from werkzeug.security import generate_password_hash  
from werkzeug.utils import secure_filename
from flask_mail import Message
from .email_functions import send_confirmation_email
import os, stripe
from sqlalchemy import func
from functools import wraps
from dotenv import load_dotenv


load_dotenv() 

def init_routes(app):
    stripe.api_key = os.getenv('STRIPE_API_KEY')

    def format_currency(value):
        return "${:,.2f}".format(value)

    # Registrar el filtro con Jinja2
    app.jinja_env.filters['currency'] = format_currency

    def admin_required(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated or not current_user.es_administrador:
                flash('Esta área es solo para administradores.', 'danger')
                # Redirige al inicio o a la página de login según convenga
                return redirect(url_for('index'))
            return f(*args, **kwargs)
        return decorated_function


# Pagos:-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------


    @app.route('/stripe-webhook', methods=['POST'])
    @csrf.exempt
    def stripe_webhook():
        payload = request.get_data(as_text=True)
        sig_header = request.headers.get('Stripe-Signature')
        webhook_secret = os.getenv('WEBHOOK_SECRET')

        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, webhook_secret
            )

            # Manejar el evento
            if event['type'] == 'checkout.session.completed':
                session = event['data']['object']
                handle_checkout_session(session)
                update_inventory(session.get('metadata', {}).get('order_id'))

                # Obtener el order_id y limpiar el carrito correspondiente
                order_id = session.get('metadata', {}).get('order_id')
                if order_id:
                    order = Order.query.get(order_id)
                    if order:
                        if order.user_id:
                            clear_user_cart(user_id=order.user_id)
                        elif order.cartsession_id:  # Ahora puedes usar cartsession_id
                            clear_guest_cart(
                                cartsession_id=order.cartsession_id)
                        send_confirmation_email(order_id)
                    else:
                        # Manejar el caso en que el objeto 'order' no se encuentra
                        pass

            return 'Success', 200

        except ValueError as e:
            return 'Invalid payload', 400
        except stripe.error.SignatureVerificationError as e:
            return 'Invalid signature', 400

    def handle_checkout_session(session):
        order_id = session.get('metadata', {}).get('order_id')
        if order_id:
            order = Order.query.get(order_id)
            if order:
                order.status = 'Pagado'
                # Otras actualizaciones necesarias
                db.session.commit()
            else:
                # Manejar el caso en que el pedido no se encuentra
                pass

    def update_inventory(order_id):
        order_items = OrderItem.query.filter_by(order_id=order_id).all()
        for item in order_items:
            product = Producto.query.get(item.product_id)
            if product and product.existencia >= item.quantity:
                product.existencia -= item.quantity
                db.session.commit()
            else:
                # Manejar el caso de inventario insuficiente
                pass

    def clear_user_cart(user_id=None):
        if user_id:
            Cartitem.query.filter_by(user_id=user_id).delete()
            db.session.commit()

    # Función para limpiar el carrito de un invitado
    def clear_guest_cart(cartsession_id=None):
        if cartsession_id:
            Cartitem.query.filter_by(cartsession=cartsession_id).delete()
            db.session.commit()

    @app.route('/create-checkout-session/<int:order_id>', methods=['POST'])
    def create_checkout_session(order_id):
        order = Order.query.get_or_404(order_id)
        try:
            line_items = [{
                'price_data': {
                    'currency': 'mxn',
                    'product_data': {
                        'name': item.product.nombre_art,
                    },
                    'unit_amount': int(item.product.precio * 100),
                },
                'quantity': item.quantity,
            } for item in order.order_items]

            checkout_session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=line_items,
                mode='payment',
                success_url=url_for(
                    'success', order_id=order_id, _external=True),
                cancel_url=url_for('view_cart', _external=True),
                metadata={'order_id': order_id}  # Agrega esta línea
            )
            return jsonify({'id': checkout_session.id})
        except Exception as e:
            # Considerar registrar el error para depuración
            return jsonify(error=str(e)), 403

    @app.route('/success/<int:order_id>')
    def success(order_id):
        # Lógica para manejar el pedido exitoso
        return render_template('eccomerce/success.html', order_id=order_id)


# Sistema de Pedidos:-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

    @app.route('/checkout', methods=['GET', 'POST'])
    def checkout():
        if request.method == 'POST':
            # Recopilar información del formulario
            address = request.form.get('address')
            city = request.form.get('city')
            postal_code = request.form.get('postal_code')
            state = request.form.get('state')
            phone = request.form.get('phone')
            guest_email = request.form.get(
                'guest_email') if not current_user.is_authenticated else None

            # Validar los campos requeridos
            if not all([address, city, postal_code, state]) or (not current_user.is_authenticated and not guest_email):
                flash('Por favor, completa todos los campos requeridos.', 'error')
                return redirect(url_for('checkout'))

            # Crear el pedido
            usuario_actual = current_user if current_user.is_authenticated else None
            cartsession_id = None
            if current_user.is_authenticated:
                order = Order(
                    user_id=current_user.id,
                    phone=phone,
                    status='Pendiente',
                    total=0  # Inicializar el total como 0
                )
            else:
                cartsession_id = request.cookies.get('cartsession_id')
                order = Order(
                    guest_email=guest_email,
                    phone=phone,
                    status='Pendiente',
                    total=0,
                    # Asignar el cartsession_id para usuarios no registrados
                    cartsession_id=cartsession_id
                )

            db.session.add(order)
            db.session.flush()  # Para obtener el ID del pedido inmediatamente

            # Crear la dirección de envío
            shipping_address = ShippingAddress(
                order_id=order.id,
                address=address,
                city=city,
                postal_code=postal_code,
                state=state
            )
            db.session.add(shipping_address)

            # Convertir CartItem en OrderItem y calcular el total
            total = 0
            cart_items = Cartitem.query.filter_by(
                user_id=current_user.id if current_user.is_authenticated else None,
                cartsession=cartsession_id if not current_user.is_authenticated else None,
                order_id=None
            ).all()

            if not cart_items:
                flash('Tu carrito está vacío.', 'error')
                return redirect(url_for('view_cart'))

            for item in cart_items:
                producto = Producto.query.get(item.product_id)
                if producto:
                    total += item.quantity * producto.precio
                    order_item = OrderItem(
                        order_id=order.id,
                        product_id=item.product_id,
                        quantity=item.quantity,
                        price=producto.precio
                    )
                    db.session.add(order_item)

            order.total = total
            db.session.commit()

            # Redirigir a la página de pago
            return redirect(url_for('payment', order_id=order.id))

        return render_template('eccomerce/checkout.html', is_authenticated=current_user.is_authenticated)

    @app.route('/payment/<int:order_id>', methods=['GET', 'POST'])
    def payment(order_id):
        order = Order.query.get_or_404(order_id)
        if request.method == 'POST':
            # Aquí se manejaría la lógica de procesamiento del pago
            # Si el pago es exitoso, actualizar el estado del pedido y enviar el correo

            return redirect(url_for('confirm_order', order_id=order.id))

        return render_template('eccomerce/payment.html', order=order)

    @app.route('/confirm_order/<int:order_id>')
    def confirm_order(order_id):
        order = Order.query.get_or_404(order_id)
        order_items = OrderItem.query.filter_by(order_id=order.id).all()
        shipping_address = ShippingAddress.query.filter_by(
            order_id=order.id).first()

        # Calcular el precio final para cada item en el pedido
        total = 0
        for item in order_items:
            product = Producto.query.get(item.product_id)
            if product:
                item.precio_final = product.calcular_precio_final() * item.quantity
                total += item.precio_final  # Sumar al total

        if not (shipping_address and order_items):
            flash("Información de pedido incompleta.", "error")
            return redirect(url_for('index'))

        return render_template('confirm_order.html', order=order, order_items=order_items, shipping_address=shipping_address, total=total)


# Carrito de Compras:-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

    @app.route('/cart/update/<int:product_id>', methods=['POST'])
    def update_cart(product_id):
        cart_item = None
        # Comprobar si el usuario está autenticado
        if current_user.is_authenticated:
            cart_item = Cartitem.query.filter_by(
                user_id=current_user.id, product_id=product_id).first()
        else:
            # Obtener el cartsession_id de las cookies
            cartsession_id = request.cookies.get('cartsession_id')
            if cartsession_id:
                cart_item = Cartitem.query.filter_by(
                    cartsession=cartsession_id, product_id=product_id).first()

        if not cart_item:
            return jsonify({'status': 'error', 'message': 'Producto no encontrado en el carrito.'}), 404

        # Obtén los datos JSON de la solicitud
        data = request.json
        new_quantity = data.get('quantity')
        product = Producto.query.get(product_id)
        usuario = Usuario.query.get(
            current_user.id) if current_user.is_authenticated else None

        if new_quantity is None:
            return jsonify({'status': 'error', 'message': 'No se proporcionó cantidad.'}), 400

        try:
            new_quantity = int(new_quantity)
        except ValueError:
            return jsonify({'status': 'error', 'message': 'Cantidad inválida.'}), 400
        print("Nueva cantidad recibida:", new_quantity)

        # Obtener el producto
        product = Producto.query.get(product_id)
        if product is None:
            return jsonify({'status': 'error', 'message': 'Producto no encontrado.'}), 404

        # Ajustar la cantidad si es necesario
        if new_quantity > product.existencia:
            new_quantity = product.existencia
            message = f'Solo disponibles: {product.existencia}.'
            adjusted = True  # Indica que la cantidad fue ajustada
        else:
            message = 'Cantidad actualizada.'
            adjusted = False

        # Actualizar la cantidad y el subtotal
        if new_quantity > 0:
            cart_item.quantity = new_quantity
            # Calcula el nuevo subtotal
            precio_final_producto = product.calcular_precio_final(usuario)
            subtotal = new_quantity * precio_final_producto
            db.session.commit()
            return jsonify({
                'status': 'success',
                'message': message,
                'price': precio_final_producto,
                'new_quantity': new_quantity,
                'adjusted': adjusted,
                'subtotal': subtotal  # Enviar subtotal basado en precio final
            })
        else:
            return jsonify({'status': 'success', 'new_quantity': new_quantity, 'subtotal': subtotal})

    @app.route('/cart/add', methods=['POST'])
    def add_to_cart():
        id_producto = request.form.get('id_producto', type=int)
        quantity = request.form.get('quantity', type=int)

        if not id_producto or not quantity:
            return jsonify({'status': 'error', 'message': 'Faltan datos del producto o la cantidad.'})

        product = Producto.query.get(id_producto)
        if not product:
            return jsonify({'status': 'error', 'message': 'El producto no existe.'})

        if quantity > product.existencia:
            return jsonify({'status': 'error', 'message': 'No hay suficiente stock del producto.'})

        # Comprobar si el usuario está autenticado o no
        if current_user.is_authenticated:
            user_id = current_user.id
            cartsession_id = None
        else:
            # Para usuarios no autenticados, usar una sesión de carrito
            cartsession_id = request.cookies.get('cartsession_id')
            if not cartsession_id:
                cartsession = Cartsession()  # Crea una nueva sesión de carrito
                db.session.add(cartsession)
                db.session.commit()
                cartsession_id = cartsession.id

        # Intenta encontrar un elemento existente en el carrito
        cart_item = Cartitem.query.filter_by(
            cartsession=cartsession_id,
            user_id=current_user.id if current_user.is_authenticated else None,
            product_id=id_producto
        ).first()

        total_quantity = quantity
        if cart_item:
            total_quantity += cart_item.quantity

        if total_quantity > product.existencia:
            return jsonify({'status': 'error', 'message': 'No hay suficiente stock del producto. Solo quedan ' + str(product.existencia) + ' unidades disponibles.'})

        if cart_item:
            cart_item.quantity = min(total_quantity, product.existencia)
        else:
            new_cart_item = Cartitem(
                product_id=id_producto,
                quantity=quantity,
                user_id=current_user.id if current_user.is_authenticated else None,
                cartsession=cartsession_id if not current_user.is_authenticated else None
            )
            db.session.add(new_cart_item)

        try:
            db.session.commit()

            # Preparar y enviar respuesta
            response = make_response(
                jsonify({'status': 'success', 'message': 'Producto añadido al carrito'}))
            if cartsession_id:  # Si es un usuario no registrado, establece la cookie
                # Expira en 7 días
                response.set_cookie(
                    'cartsession_id', cartsession_id, max_age=7*24*60*60)
            return response

        except Exception as e:
            db.session.rollback()
            print(f"Error al añadir al carrito: {e}, Producto: {id_producto}")
            return jsonify({'status': 'error', 'message': 'Ocurrió un error al añadir el producto al carrito.'})

    @app.route('/cart')
    def view_cart():
        products = []
        total = 0

        if current_user.is_authenticated:
            user_id = current_user.id
            cart_items = Cartitem.query.filter_by(user_id=user_id).all()
        else:
            cartsession_id = request.cookies.get('cartsession_id')
            cart_items = Cartitem.query.filter_by(
                cartsession=cartsession_id).all() if cartsession_id else []

        for item in cart_items:
            product = Producto.query.get(item.product_id)
            if product:
                subtotal = item.quantity * product.precio
                products.append({
                    'id_producto': product.id_producto,
                    'nombre': product.nombre_art,
                    'codigo_articulo': product.codigo_articulo,
                    'marca': product.marca,
                    'posicion': product.posicion,
                    'precio': product.precio,
                    'cantidad': item.quantity,
                    'subtotal': subtotal,
                    'ruta_imagen': product.ruta_imagen  # Incluye la imagen del producto
                })
                total += subtotal

        return render_template('eccomerce/cart.html', products=products, total=total)

    @app.route('/cart/remove/<int:product_id>', methods=['POST'])
    def remove_from_cart(product_id):
        if current_user.is_authenticated:
            user_id = current_user.id
            cart_item = Cartitem.query.filter_by(
                user_id=user_id, product_id=product_id).first()
        else:
            cartsession_id = request.cookies.get('cartsession_id')
            if cartsession_id:
                cart_item = Cartitem.query.filter_by(
                    cartsession=cartsession_id, product_id=product_id).first()
            else:
                return jsonify({'status': 'error', 'message': 'Producto no encontrado en el carrito.'}), 404

        if cart_item:
            db.session.delete(cart_item)
            db.session.commit()
            flash('Producto eliminado del carrito.', 'success')
        else:
            flash('Producto no encontrado en el carrito.', 'error')

        return redirect(url_for('view_cart'))

    @app.route('/api/cart/total')
    def get_cart_total():
        total = 0
        if current_user.is_authenticated:
            cart_items = Cartitem.query.filter_by(
                user_id=current_user.id).all()
        else:
            cartsession_id = request.cookies.get('cartsession_id')
            if cartsession_id:
                cart_items = Cartitem.query.filter_by(
                    cartsession=cartsession_id).all()
            else:
                cart_items = []

        for item in cart_items:
            product = Producto.query.get(item.product_id)
            if product:
                total += item.quantity * product.calcular_precio_final()
        return jsonify({'total': total})


# Eccomerce:-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

    @app.route('/catalogo')
    def catalogo():
        productos = Producto.query.all()  # Obtener todos los productos de la base de datos
        return render_template('eccomerce/catalogo.html', productos=productos)

    @app.route('/productos')
    @admin_required
    def mostrar_productos():
        productos = Producto.query.all()  # Obtener todos los productos de la base de datos
        return render_template('eccomerce/mostrar_productos.html', productos=productos)

    @app.route('/producto/eliminar/<int:id_producto>', methods=['POST'])
    @admin_required
    def eliminar_producto(id_producto):
        producto = Producto.query.get_or_404(id_producto)
        db.session.delete(producto)
        db.session.commit()
        flash('Producto eliminado con éxito', 'success')
        return redirect(url_for('mostrar_productos'))

    @app.route('/producto/modificar/<int:id_producto>', methods=['GET', 'POST'])
    @admin_required
    def modificar_producto(id_producto):
        producto = Producto.query.get_or_404(id_producto)
        # Crea una instancia del formulario y pre-rellena con los datos del producto
        form = ProductoForm(obj=producto)

        if form.validate_on_submit():
            # Actualiza los campos del producto con los datos del formulario
            form.populate_obj(producto)
            # Si hay una nueva imagen, procesar y guardar aquí
            db.session.commit()
            flash('Producto actualizado con éxito.', 'success')
            return redirect(url_for('mostrar_productos', id_producto=producto.id_producto))

        return render_template('eccomerce/modificar_producto.html', producto=producto, form=form)

    @app.route('/admin/agregar-producto', methods=['GET', 'POST'])
    @admin_required
    def agregar_producto():
        form = ProductoForm()
        if form.validate_on_submit():
            nuevo_producto = Producto(
                codigo_articulo=form.codigo_articulo.data,
                nombre_art=form.nombre_art.data,
                marca=form.marca.data,
                precio=form.precio.data,
                existencia=form.existencia.data,
                rating=form.rating.data,
                precioOriginal=form.precioOriginal.data,
                multiplo_venta=form.multiplo_venta.data,
                equivalencia=form.equivalencia.data,
                posicion=form.posicion.data,
                esFavorito=form.esFavorito.data
            )
            if 'imagen_producto' in request.files:
                file = form.imagen_producto.data
                filename = secure_filename(file.filename)
                ruta_guardado = os.path.join(
                    app.config['UPLOAD_FOLDER'], filename)
                file.save(ruta_guardado)
                # Aquí deberías asignar la ruta a nuevo_producto
                nuevo_producto.ruta_imagen = url_for(
                    'static', filename='img/' + filename)

            # Corregido para agregar la instancia correcta
            db.session.add(nuevo_producto)
            db.session.commit()
            # Redireccionar o enviar mensaje de éxito aquí

        return render_template('eccomerce/agregar_producto.html', form=form)


# Rutas basicas:-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

    @app.route('/robots.txt')
    def static_from_root():
        return send_from_directory(app.static_folder, request.path[1:])

    @app.route('/')
    def index():
        return render_template('index.html')

    @app.route('/about')
    def about():
        return render_template('about.html')


    @app.route('/contact', methods=['GET', 'POST'])
    def contact():
        form = ContactForm()
        if form.validate_on_submit():
            # Crea una nueva instancia de Contacto con los datos del formulario
            nuevo_contacto = Contacto(
                nombre=form.name.data, telefono=form.phone.data, email=form.email.data, mensaje=form.message.data)
            # Agrega el nuevo contacto a la sesión de la base de datos
            db.session.add(nuevo_contacto)
            db.session.commit()  # Guarda los cambios en la base de datos
            flash(
                'Tu mensaje ha sido enviado exitosamente. ¡Gracias por contactarnos!', 'success')
            # Redirige al usuario a la misma página de contacto o a donde consideres apropiado
            return redirect(url_for('contact'))
        return render_template('contact.html', form=form)

    @app.route('/privacy')
    def privacy():
        return render_template('footer/privacy.html')

    @app.route('/aviso_cookies')
    def aviso_cookies():
        return render_template('footer/aviso_cookies.html')

    @app.route('/faq')
    def faq():
        return render_template('footer/faq.html')

    @app.route('/send_contact_email', methods=['POST'])
    def send_contact_email():
        name = request.form.get('name')
        email = request.form.get('email')
        message = request.form.get('message')

        msg = Message(f"Mensaje de {name}", recipients=[
                      'refacajeme@refacajeme.com'])
        msg.body = f"De: {name} <{email}>\n\n{message}"

        try:
            mail.send(msg)
            return jsonify({'status': 'success', 'message': 'Tu mensaje ha sido enviado. Gracias por contactarnos.'})
        except Exception as e:
            return jsonify({'status': 'error', 'message': f'Ocurrió un error al enviar el mensaje: {str(e)}'})

            return redirect(url_for('contact'))


# Historial de pedidos:-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------


    @app.route('/order_history')
    @login_required
    def order_history():
        orders = Order.query.filter_by(user_id=current_user.id).all()
        return render_template('eccomerce/order_history.html', orders=orders)


# Gestión de Perfiles de Usuario:-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

    @app.route('/profile')
    @login_required
    def profile():
        return render_template('user/profile.html')

    @app.route('/recover_password', methods=['GET', 'POST'])
    def recover_password():
        form = PasswordRecoveryForm()
        if form.validate_on_submit():
            # Aquí iría la lógica para enviar un correo electrónico con instrucciones para restablecer la contraseña
            flash(
                'Se han enviado instrucciones para restablecer tu contraseña a tu correo electrónico.', 'info')
            return redirect(url_for('login'))
        return render_template('user/recover_password.html', form=form)

    @app.route('/change_password', methods=['GET', 'POST'])
    @login_required
    def change_password():
        form = ChangePasswordForm()
        if form.validate_on_submit():
            user = current_user
            if user.check_password(form.current_password.data):
                user.set_password(form.new_password.data)
                db.session.commit()
                flash('Tu contraseña ha sido actualizada.', 'success')
                return redirect(url_for('profile'))
            else:
                flash('Contraseña actual incorrecta.', 'danger')
        return render_template('user/change_password.html', form=form)

    @app.route('/register', methods=['GET', 'POST'])
    @limiter.limit("50 per minute")
    def register():
        if current_user.is_authenticated:
            return redirect(url_for('index'))

        form = RegistrationForm()
        if form.validate_on_submit():
            # Comprobación de usuario existente
            email = form.email.data.lower()
            username = form.username.data.lower()
            existing_user = Usuario.query.filter(
                (func.lower(Usuario.email) == email) |
                (func.lower(Usuario.nombre_usuario) == username)
            ).first()

            if existing_user is None:
                hashed_password = generate_password_hash(form.password.data)
                user = Usuario(email=email, nombre_usuario=username,
                               password_hash=hashed_password)
                db.session.add(user)
                db.session.commit()
                flash('Tu cuenta ha sido creada! Ahora puedes iniciar sesión', 'success')
                return redirect(url_for('login'))
            else:
                flash(
                    'Un usuario con ese correo electrónico o nombre de usuario ya existe')

        return render_template('user/register.html', title='Register', form=form)

    @app.route('/login', methods=['GET', 'POST'])
    @limiter.limit("50 per minute")
    def login():
        if current_user.is_authenticated:
            return redirect(url_for('index'))
        form = LoginForm()
        if form.validate_on_submit():
            user_input = form.username_or_email.data.lower()
            user = Usuario.query.filter(
                (func.lower(Usuario.email) == user_input) |
                (func.lower(Usuario.nombre_usuario) == user_input)
            ).first()
            if user and user.check_password(form.password.data):
                login_user(user, remember=form.remember.data)
                # Intenta redirigir a la página solicitada originalmente
                next_page = request.args.get('next')
                # Si 'next' no existe, redirige a index
                return redirect(next_page or url_for('index'))
            else:
                flash('Por favor revisa el correo electrónico y la contraseña', 'danger')
        return render_template('user/login.html', title='Login', form=form)

    @app.route('/logout')
    @login_required  # Asegúrate de que solo los usuarios logueados puedan cerrar sesión
    def logout():
        logout_user()
        return redirect(url_for('index'))

    @app.route('/perfil/actualizar', methods=['GET', 'POST'])
    @login_required
    def actualizar_perfil():
        form = UserProfileForm(obj=current_user)
        if form.validate_on_submit():
            current_user.rfc = form.rfc.data
            current_user.telefono = form.telefono.data
            current_user.direccion = form.direccion.data
            db.session.commit()
            flash('Tu perfil ha sido actualizado.', 'success')
            return redirect(url_for('perfil'))
        return render_template('user/actualizar_perfil.html', form=form)


# Gestión de Productos-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
