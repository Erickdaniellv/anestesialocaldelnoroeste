# /home/erickdaniellv/refacajeme/app/__init__.py
from flask import Flask, g
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_wtf.csrf import CSRFProtect
from flask_mail import Mail
import os
from flask_caching import Cache


# Inicializar las extensiones fuera de create_app
csrf = CSRFProtect()
db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
limiter = Limiter(key_func=get_remote_address, default_limits=["20000 per day", "5000 per hour"])
mail = Mail()  # Inicializa Flask-Mail
cache = Cache(config={"CACHE_TYPE": "simple"})

def create_app():
    app = Flask(__name__)
    app.config.from_object('config.Config')
    csrf.init_app(app)
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    login_manager.login_view = 'login'
    limiter.init_app(app)
    mail.init_app(app)
    cache.init_app(app)

    # seguridad CSP
    #@app.before_request
    #def set_csp_nonce():
     #   g.csp_nonce = os.urandom(16).hex() 

    #@app.after_request
    #def apply_csp(response):
    #    csp = (
     #       "default-src 'self'; "
      #      "script-src 'self' 'unsafe-inline' https://code.jquery.com https://cdn.jsdelivr.net https://www.googletagmanager.com https://js.stripe.com https://checkout.stripe.com https://maxcdn.bootstrapcdn.com; "
       #     "style-src 'self' 'unsafe-inline' https://maxcdn.bootstrapcdn.com https://fonts.googleapis.com https://cdnjs.cloudflare.com; "
        #    "font-src 'self' https://fonts.gstatic.com https://cdnjs.cloudflare.com; "
         #   "img-src 'self' data: https://*.stripe.com https://refaobregon.s3.amazonaws.com; "
          #  "frame-src 'self' https://www.googletagmanager.com https://www.stripe.com https://checkout.stripe.com https://js.stripe.com; "
           # "connect-src 'self' https://www.google-analytics.com https://analytics.google.com; "
        #)
        #response.headers['Content-Security-Policy'] = csp
        #return response





    # Configuración del cargador de usuario para Flask-Login
    @login_manager.user_loader
    def load_user(user_id):
        # Import aquí para evitar importaciones circulares
        from .models import Usuario
        return Usuario.query.get(int(user_id))

    # Importar vistas después de la inicialización para evitar importaciones circulares
    from .views import init_routes
    init_routes(app)

    return app