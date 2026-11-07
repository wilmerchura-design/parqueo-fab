import datetime

from flask import request
from flask_appbuilder import BaseView, expose, has_access

from app import appbuilder, db
from app.models import TIPOS_VEHICULO, Zona
from app.reports import parse_fecha, reporte_historial, reporte_ocupacion, reporte_ingresos


def _zonas():
    return db.session.query(Zona).order_by(Zona.nombre).all()


def _zona_id():
    try:
        return int(request.args.get("zona") or 0) or None
    except ValueError:
        return None


class IngresosReportView(BaseView):
    route_base = "/reporte-ingresos"
    default_view = "index"

    @expose("/")
    @has_access
    def index(self):
        hoy = datetime.date.today()
        desde = parse_fecha(request.args.get("desde"), hoy - datetime.timedelta(days=30))
        hasta = parse_fecha(request.args.get("hasta"), hoy)
        tipo = request.args.get("tipo") or None
        if tipo not in TIPOS_VEHICULO:
            tipo = None
        zona_id = _zona_id()
        datos = reporte_ingresos(desde, hasta, zona_id, tipo)
        return self.render_template(
            "reportes/ingresos.html", base_template=appbuilder.base_template, appbuilder=appbuilder,
            datos=datos, zonas=_zonas(), tipos=TIPOS_VEHICULO,
            f={"desde": desde, "hasta": hasta, "tipo": tipo, "zona": zona_id})


class OcupacionReportView(BaseView):
    route_base = "/reporte-ocupacion"
    default_view = "index"

    @expose("/")
    @has_access
    def index(self):
        zona_id = _zona_id()
        datos = reporte_ocupacion(zona_id)
        return self.render_template(
            "reportes/ocupacion.html", base_template=appbuilder.base_template, appbuilder=appbuilder,
            datos=datos, zonas=_zonas(), f={"zona": zona_id})


class HistorialReportView(BaseView):
    route_base = "/reporte-historial"
    default_view = "index"

    @expose("/")
    @has_access
    def index(self):
        hoy = datetime.date.today()
        desde = parse_fecha(request.args.get("desde"), hoy - datetime.timedelta(days=30))
        hasta = parse_fecha(request.args.get("hasta"), hoy)
        placa = request.args.get("placa", "")
        cliente = request.args.get("cliente", "")
        datos = reporte_historial(desde, hasta, placa, cliente)
        return self.render_template(
            "reportes/historial.html", base_template=appbuilder.base_template, appbuilder=appbuilder,
            datos=datos, f={"desde": desde, "hasta": hasta, "placa": placa, "cliente": cliente})


appbuilder.add_view(IngresosReportView, "Ingresos", icon="fa-line-chart", category="Reportes")
appbuilder.add_view(OcupacionReportView, "Ocupación por zona", icon="fa-bar-chart", category="Reportes")
appbuilder.add_view(HistorialReportView, "Historial de vehículos", icon="fa-history", category="Reportes")
