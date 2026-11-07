import os

from dotenv import load_dotenv
from flask_appbuilder.const import AUTH_DB

basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, ".env"))

SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")

# Base de datos (MySQL por defecto, configurable por .env)
SQLALCHEMY_DATABASE_URI = os.environ.get(
    "DATABASE_URI", "mysql+pymysql://root:@localhost:3306/parqueo"
)
SQLALCHEMY_TRACK_MODIFICATIONS = False

# Autenticación y seguridad
AUTH_TYPE = AUTH_DB
AUTH_ROLE_ADMIN = "Admin"
AUTH_USER_REGISTRATION = False
AUTH_ROLE_PUBLIC = "Public"  # sin permisos: obliga a iniciar sesión
WTF_CSRF_ENABLED = True

# Interfaz
APP_NAME = "Sistema de Parqueo"
BABEL_DEFAULT_LOCALE = "es"
LANGUAGES = {"es": {"flag": "es", "name": "Español"}, "en": {"flag": "gb", "name": "English"}}

# IA (Gemini, capa gratuita)
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")
