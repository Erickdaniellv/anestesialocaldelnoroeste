# /home/erickdaniellv/refacajeme/config.py
import os

class Config:
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL')

    #Guardar imagenes
    UPLOAD_FOLDER = 'C:/Users/Erick Lopez/Desktop/WEBS/anestesiadelnoroeste.com/app/static/img'

    SECRET_KEY = os.getenv('SECRET_KEY')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    WTF_CSRF_ENABLED = True

    MAIL_SERVER = 'smtp.hostinger.com'
    MAIL_PORT = 587  # 465 Para SSL, o cambia a 587 si es TLS
    MAIL_USE_TLS = True  # Cambia a False si estás usando SSL
    MAIL_USE_SSL = False  # Añade esto si estás usando SSL
    MAIL_USERNAME = 'refacajeme@refacajeme.com'
    MAIL_PASSWORD = os.getenv('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = 'refacajeme@refacajeme.com'