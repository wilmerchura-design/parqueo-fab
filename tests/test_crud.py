import datetime

import pytest

from app import db
from app.models import Espacio, Tarifa, Ticket, Vehiculo

RUTAS = ["/clientemodelview/list/", "/vehiculomodelview/list/", "/zonamodelview/list/",
         "/espaciomodelview/list/", "/tarifamodelview/list/", "/ticketmodelview/list/"]


def test_vistas_requieren_login(client):
    for r in RUTAS:
        resp = client.get(r)
        assert resp.status_code in (302, 401)
        assert "/login" in resp.headers.get("Location", "/login")


@pytest.mark.parametrize("ruta", RUTAS)
def test_admin_lista(admin, ruta):
    assert admin.get(ruta).status_code == 200


def test_consulta_solo_lectura(consulta):
    assert consulta.get("/ticketmodelview/list/").status_code == 200
    resp = consulta.get("/ticketmodelview/add")
    assert resp.status_code in (302, 403)
    resp = consulta.post("/clientemodelview/add", data={"nombre": "X", "ci": "1"})
    assert resp.status_code in (302, 403)


def _datos_ticket(flask_app, tipo="Auto"):
    with flask_app.app_context():
        esp = db.session.query(Espacio).filter_by(estado="Libre").first()
        tarifa = db.session.query(Tarifa).filter_by(tipo_vehiculo=tipo, zona_id=esp.zona_id).first()
        activos = db.session.query(Ticket.vehiculo_id).filter_by(estado="Activo")
        veh = (db.session.query(Vehiculo).filter_by(tipo=tipo)
               .filter(~Vehiculo.id.in_(activos)).first())
        return esp.id, esp.codigo, tarifa.id, veh.id


def test_ticket_ciclo_completo(flask_app, admin):
    esp_id, esp_cod, tarifa_id, veh_id = _datos_ticket(flask_app)
    entrada = (datetime.datetime.now() - datetime.timedelta(minutes=130)).strftime("%Y-%m-%d %H:%M:%S")
    resp = admin.post("/ticketmodelview/add", follow_redirects=True, data={
        "vehiculo": veh_id, "espacio": esp_id, "tarifa": tarifa_id,
        "hora_entrada": entrada, "observaciones": "prueba"})
    assert resp.status_code == 200
    with flask_app.app_context():
        t = db.session.query(Ticket).filter_by(vehiculo_id=veh_id, estado="Activo").one()
        assert t.espacio.estado == "Ocupado"
        tid = t.id

    # Mismo espacio ocupado -> rechazado
    resp = admin.post("/ticketmodelview/add", follow_redirects=True, data={
        "vehiculo": veh_id, "espacio": esp_id, "tarifa": tarifa_id, "hora_entrada": entrada})
    assert "no est" in resp.get_data(as_text=True)

    # Finalizar -> calcula monto (130 min = 3 horas) y libera espacio
    salida = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    admin.post(f"/ticketmodelview/edit/{tid}", follow_redirects=True, data={"hora_salida": salida})
    with flask_app.app_context():
        t = db.session.get(Ticket, tid)
        assert t.estado == "Finalizado"
        assert t.espacio.estado == "Libre"
        assert float(t.monto) == 3 * float(t.tarifa.precio_hora)


def test_tarifa_debe_coincidir_con_tipo(flask_app, admin):
    esp_id, _, _, _ = _datos_ticket(flask_app)
    with flask_app.app_context():
        esp = db.session.get(Espacio, esp_id)
        tarifa_moto = db.session.query(Tarifa).filter_by(tipo_vehiculo="Moto", zona_id=esp.zona_id).first().id
        activos = db.session.query(Ticket.vehiculo_id).filter_by(estado="Activo")
        auto = db.session.query(Vehiculo).filter_by(tipo="Auto").filter(~Vehiculo.id.in_(activos)).first().id
    resp = admin.post("/ticketmodelview/add", follow_redirects=True, data={
        "vehiculo": auto, "espacio": esp_id, "tarifa": tarifa_moto,
        "hora_entrada": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")})
    assert "La tarifa es para" in resp.get_data(as_text=True)
