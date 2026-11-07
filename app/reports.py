"""Consultas de los 3 reportes (sin dependencias de Flask para poder probarlas)."""
import datetime
import math

from sqlalchemy import func

from app import db
from app.models import Cliente, Espacio, Ticket, Vehiculo, Zona


def parse_fecha(texto, defecto):
    try:
        return datetime.datetime.strptime(texto, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return defecto


def _rango(desde, hasta):
    """Inicio inclusivo y fin exclusivo (para incluir todo el día 'hasta')."""
    return (datetime.datetime.combine(desde, datetime.time.min),
            datetime.datetime.combine(hasta + datetime.timedelta(days=1), datetime.time.min))


# --------------------------------------------------------------------------
# Reporte 1: Ingresos por período, zona y tipo de vehículo
# --------------------------------------------------------------------------
def reporte_ingresos(desde, hasta, zona_id=None, tipo=None):
    ini, fin = _rango(desde, hasta)

    def base(*cols):
        q = (db.session.query(*cols)
             .select_from(Ticket)
             .join(Espacio, Ticket.espacio_id == Espacio.id)
             .join(Zona, Espacio.zona_id == Zona.id)
             .join(Vehiculo, Ticket.vehiculo_id == Vehiculo.id)
             .filter(Ticket.estado == "Finalizado",
                     Ticket.hora_salida >= ini, Ticket.hora_salida < fin))
        if zona_id:
            q = q.filter(Zona.id == zona_id)
        if tipo:
            q = q.filter(Vehiculo.tipo == tipo)
        return q

    cantidad, total = base(func.count(Ticket.id), func.coalesce(func.sum(Ticket.monto), 0)).one()
    por_dia = [(str(d), c, float(s or 0)) for d, c, s in
               base(func.date(Ticket.hora_salida), func.count(Ticket.id), func.sum(Ticket.monto))
               .group_by(func.date(Ticket.hora_salida)).order_by(func.date(Ticket.hora_salida)).all()]
    por_zona = [(n, c, float(s or 0)) for n, c, s in
                base(Zona.nombre, func.count(Ticket.id), func.sum(Ticket.monto))
                .group_by(Zona.nombre).order_by(func.sum(Ticket.monto).desc()).all()]
    por_tipo = [(t, c, float(s or 0)) for t, c, s in
                base(Vehiculo.tipo, func.count(Ticket.id), func.sum(Ticket.monto))
                .group_by(Vehiculo.tipo).order_by(func.sum(Ticket.monto).desc()).all()]
    total = float(total or 0)
    return {
        "cantidad": cantidad, "total": total,
        "promedio": round(total / cantidad, 2) if cantidad else 0,
        "por_dia": por_dia, "por_zona": por_zona, "por_tipo": por_tipo,
    }


# --------------------------------------------------------------------------
# Reporte 2: Ocupación actual por zona
# --------------------------------------------------------------------------
def reporte_ocupacion(zona_id=None):
    q = (db.session.query(Zona.id, Zona.nombre, Espacio.estado, func.count(Espacio.id))
         .join(Espacio, Espacio.zona_id == Zona.id).group_by(Zona.id, Zona.nombre, Espacio.estado))
    if zona_id:
        q = q.filter(Zona.id == zona_id)
    zonas = {}
    for zid, nombre, estado, n in q.all():
        z = zonas.setdefault(zid, {"zona": nombre, "Libre": 0, "Ocupado": 0, "Mantenimiento": 0})
        z[estado] = n
    filas = []
    for z in sorted(zonas.values(), key=lambda x: x["zona"]):
        z["total"] = z["Libre"] + z["Ocupado"] + z["Mantenimiento"]
        habilitados = z["Libre"] + z["Ocupado"]
        z["porcentaje"] = round(100 * z["Ocupado"] / habilitados, 1) if habilitados else 0
        filas.append(z)

    ahora = datetime.datetime.now()
    activos_q = (db.session.query(Ticket).join(Espacio, Ticket.espacio_id == Espacio.id)
                 .filter(Ticket.estado == "Activo").order_by(Ticket.hora_entrada))
    if zona_id:
        activos_q = activos_q.filter(Espacio.zona_id == zona_id)
    activos = []
    for t in activos_q.all():
        minutos = int((ahora - t.hora_entrada).total_seconds() // 60)
        horas = max(1, math.ceil(minutos / 60))
        activos.append({
            "id": t.id, "placa": t.vehiculo.placa, "espacio": t.espacio.codigo,
            "zona": t.espacio.zona.nombre, "entrada": t.hora_entrada,
            "minutos": minutos, "estimado": round(horas * float(t.tarifa.precio_hora), 2),
        })
    totales = {k: sum(f[k] for f in filas) for k in ("Libre", "Ocupado", "Mantenimiento", "total")}
    habil = totales["Libre"] + totales["Ocupado"]
    totales["porcentaje"] = round(100 * totales["Ocupado"] / habil, 1) if habil else 0
    return {"zonas": filas, "totales": totales, "activos": activos}


# --------------------------------------------------------------------------
# Reporte 3: Historial por vehículo / cliente
# --------------------------------------------------------------------------
def reporte_historial(desde, hasta, placa="", cliente=""):
    ini, fin = _rango(desde, hasta)
    q = (db.session.query(Ticket)
         .join(Vehiculo, Ticket.vehiculo_id == Vehiculo.id)
         .join(Cliente, Vehiculo.cliente_id == Cliente.id)
         .filter(Ticket.hora_entrada >= ini, Ticket.hora_entrada < fin))
    if placa:
        q = q.filter(Vehiculo.placa.ilike(f"%{placa.strip()}%"))
    if cliente:
        like = f"%{cliente.strip()}%"
        q = q.filter((Cliente.nombre.ilike(like)) | (Cliente.ci.ilike(like)))
    tickets = q.order_by(Ticket.hora_entrada.desc()).all()

    filas, total, minutos_tot, n_fin = [], 0.0, 0, 0
    for t in tickets:
        minutos = None
        if t.hora_salida:
            minutos = int((t.hora_salida - t.hora_entrada).total_seconds() // 60)
            minutos_tot += minutos
            n_fin += 1
        monto = float(t.monto) if t.monto is not None else 0.0
        total += monto
        filas.append({
            "id": t.id, "placa": t.vehiculo.placa, "cliente": t.vehiculo.cliente.nombre,
            "espacio": t.espacio.codigo, "entrada": t.hora_entrada, "salida": t.hora_salida,
            "minutos": minutos, "monto": monto if t.monto is not None else None, "estado": t.estado,
        })
    return {
        "filas": filas, "cantidad": len(filas), "total": round(total, 2),
        "promedio_min": round(minutos_tot / n_fin) if n_fin else 0,
    }
