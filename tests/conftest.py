import os
import tempfile

import pytest

_db = os.path.join(tempfile.mkdtemp(), "test_parqueo.db")
os.environ["DATABASE_URI"] = f"sqlite:///{_db}"
os.environ["GEMINI_API_KEY"] = ""


@pytest.fixture(scope="session")
def flask_app():
    from flask_appbuilder import Model

    from app import app, db
    from app.cli import cargar_datos, crear_roles, crear_usuarios

    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    with app.app_context():
        Model.metadata.create_all(db.engine)
        crear_roles()
        crear_usuarios()
        cargar_datos()
    return app


@pytest.fixture()
def client(flask_app):
    return flask_app.test_client()


def login(client, usuario, clave):
    return client.post("/login/", data={"username": usuario, "password": clave}, follow_redirects=True)


@pytest.fixture()
def admin(client):
    login(client, "admin", "admin123")
    return client


@pytest.fixture()
def consulta(client):
    login(client, "consulta", "consulta123")
    return client
