import datetime

import pytest

from app import db
from app.models import Cliente, Espacio, Ticket, Vehiculo
from app.reports import reporte_historial, reporte_ingresos, reporte_ocupacion

HOY = datetime.date.today()
AMPLIO = (HOY - datetime.timedelta(days=60), HOY + datetime.timedelta(days=1))

RUTAS = ["/reporte-ingresos/", "/reporte-ocupacion/", "/reporte-historial/"]


@pytest.mark.parametrize("ruta", RUTAS)
def test_reportes_protegidos(client, ruta):
    resp = client.get(ruta)
    assert resp.status_code in (302, 401)


@pytest.mark.parametrize("ruta", RUTAS)
def test_reportes_accesibles_admin_y_consulta(admin, ruta):
    assert admin.get(ruta).status_code == 200


@pytest.mark.parametrize("ruta", RUTAS)
def test_reportes_accesibles_consulta(consulta, ruta):
    assert consulta.get(ruta).status_code == 200


def test_ingresos_coincide_con_suma_directa(flask_app):
    with flask_app.app_context():
        esperado = sum(float(t.monto) for t in db.session.query(Ticket).filter_by(estado="Finalizado")
                       if AMPLIO[0] <= t.hora_salida.date() <= AMPLIO[1])
        n = sum(1 for t in db.session.query(Ticket).filter_by(estado="Finalizado")
                if AMPLIO[0] <= t.hora_salida.date() <= AMPLIO[1])
        r = reporte_ingresos(*AMPLIO)
        assert r["cantidad"] == n
        assert r["total"] == pytest.approx(esperado)
        assert sum(x[2] for x in r["por_zona"]) == pytest.approx(esperado)
        assert sum(x[2] for x in r["por_tipo"]) == pytest.approx(esperado)
        assert sum(x[2] for x in r["por_dia"]) == pytest.approx(esperado)


def test_ingresos_filtro_tipo_y_zona(flask_app):
    with flask_app.app_context():
        total = reporte_ingresos(*AMPLIO)
        motos = reporte_ingresos(*AMPLIO, tipo="Moto")
        assert motos["total"] <= total["total"]
        assert all(t == "Moto" for t, _, _ in motos["por_tipo"])
        zona_id = db.session.query(Espacio).first().zona_id
        z = reporte_ingresos(*AMPLIO, zona_id=zona_id)
        assert len(z["por_zona"]) <= 1


def test_ingresos_rango_vacio(flask_app):
    with flask_app.app_context():
        lejos = datetime.date(2000, 1, 1)
        r = reporte_ingresos(lejos, lejos)
        assert r["cantidad"] == 0 and r["total"] == 0 and r["por_dia"] == []


def test_ocupacion_coincide_con_espacios(flask_app):
    with flask_app.app_context():
        r = reporte_ocupacion()
        assert r["totales"]["total"] == db.session.query(Espacio).count()
        assert r["totales"]["Ocupado"] == db.session.query(Espacio).filter_by(estado="Ocupado").count()
        assert len(r["activos"]) == db.session.query(Ticket).filter_by(estado="Activo").count()
        # cada ticket activo ocupa un espacio ocupado
        assert r["totales"]["Ocupado"] == len(r["activos"])
        for z in r["zonas"]:
            assert 0 <= z["porcentaje"] <= 100


def test_historial_filtra_por_placa_y_cliente(flask_app):
    with flask_app.app_context():
        veh = db.session.query(Vehiculo).first()
        r = reporte_historial(*AMPLIO, placa=veh.placa)
        assert r["cantidad"] == db.session.query(Ticket).filter_by(vehiculo_id=veh.id).count()
        assert all(f["placa"] == veh.placa for f in r["filas"])
        cli = db.session.get(Cliente, veh.cliente_id)
        r2 = reporte_historial(*AMPLIO, cliente=cli.ci)
        assert all(f["cliente"] == cli.nombre for f in r2["filas"])
        assert reporte_historial(*AMPLIO, placa="NO-EXISTE")["cantidad"] == 0


def test_pagina_ingresos_muestra_filtros(admin):
    html = admin.get("/reporte-ingresos/?tipo=Moto&desde=2000-01-01&hasta=2000-01-02").get_data(as_text=True)
    assert "Ingreso total" in html and "Sin resultados" in html
