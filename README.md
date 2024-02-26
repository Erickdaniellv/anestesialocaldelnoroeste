# Nombre del Proyecto E-commerce

Este proyecto es un sitio web de e-commerce desarrollado con [Python](https://www.python.org/) y el microframework [Flask](https://flask.palletsprojects.com/). Fue diseñado para ofrecer una experiencia de compra en línea sencilla y segura.

## Características

- **Gestión de Productos**: Añade, edita y elimina productos desde una interfaz administrativa.
- **Carrito de Compras**: Permite a los usuarios agregar productos a su carrito y gestionarlos.
- **Sistema de Autenticación**: Incluye registro de usuarios y autenticación de sesión.
- **Pasarela de Pagos**: Integra [Stripe](https://stripe.com/) para procesar pagos de forma segura.
- **Responsive Design**: Diseñado para ser completamente responsivo y accesible desde cualquier dispositivo.

## Tecnologías Utilizadas

- Backend: Python, Flask
- Frontend: HTML, CSS, [Tailwind CSS](https://tailwindcss.com/), JavaScript
- Base de Datos: SQLite/PostgreSQL
- Otros: Flask-Migrate para las migraciones de base de datos, Flask-Mail para el envío de correos electrónicos, Flask-WTF para formularios.

## Instalación

Para instalar y ejecutar este proyecto localmente, sigue los siguientes pasos:

1. Clona el repositorio:

```bash
git clone https://github.comErickdaniellv/anestesialocaldelnoroeste.git
cd tu_repositorio

python -m venv venv
source venv/bin/activate  # En Windows usa `venv\Scripts\activate`
pip install -r requirements.txt


flask db upgrade

flask run







