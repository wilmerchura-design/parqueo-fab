import pytest

from tests.conftest import login


@pytest.fixture()
def operador(client):
    login(client, "operador", "operador123")
    return client


def test_operador_no_administra_usuarios(operador):
    for ruta in ("/users/list/", "/roles/list/"):
        assert operador.get(ruta).status_code in (302, 403, 404)
        assert "Lista de Usuarios" not in operador.get(ruta, follow_redirects=True).get_data(as_text=True)


def test_operador_puede_crear_clientes(operador, flask_app):
    from app import db
    from app.models import Cliente

    operador.post("/clientemodelview/add", data={"nombre": "Nuevo Cliente", "ci": "9999999"},
                  follow_redirects=True)
    with flask_app.app_context():
        assert db.session.query(Cliente).filter_by(ci="9999999").count() == 1


def test_operador_no_modifica_infraestructura(operador):
    resp = operador.post("/zonamodelview/add", data={"nombre": "Zona X"})
    assert resp.status_code in (302, 403)


def test_login_incorrecto(client):
    resp = login(client, "admin", "mala-clave")
    assert "/login" in resp.request.path
