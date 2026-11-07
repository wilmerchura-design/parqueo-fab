import datetime

from flask import flash, redirect
from flask_appbuilder import ModelView
from flask_appbuilder.actions import action
from flask_appbuilder.models.sqla.interface import SQLAInterface

from app import appbuilder, db
from app.models import Cliente, Espacio, Tarifa, Ticket, Vehiculo, Zona


class ClienteModelView(ModelView):
    datamodel = SQLAInterface(Cliente)
    list_columns = ["nombre", "ci", "telefono", "email"]
    search_columns = ["nombre", "ci", "telefono"]
    label_columns = {"nombre": "Nombre", "ci": "C.I.", "telefono": "Teléfono", "email": "Correo"}
    order_columns = ["nombre", "ci"]


class ZonaModelView(ModelView):
    datamodel = SQLAInterface(Zona)
    list_columns = ["nombre", "descripcion"]
    label_columns = {"nombre": "Nombre", "descripcion": "Descripción"}


class VehiculoModelView(ModelView):
    datamodel = SQLAInterface(Vehiculo)
    list_columns = ["placa", "marca", "modelo", "tipo", "cliente"]
    search_columns = ["placa", "marca", "tipo", "cliente"]
    label_columns = {
        "placa": "Placa", "marca": "Marca", "modelo": "Modelo",
        "tipo": "Tipo", "cliente": "Propietario",
    }

    def pre_add(self, item):
        item.placa = item.placa.strip().upper()

    def pre_update(self, item):
        item.placa = item.placa.strip().upper()


class EspacioModelView(ModelView):
    datamodel = SQLAInterface(Espacio)
    list_columns = ["codigo", "zona", "estado"]
    search_columns = ["codigo", "zona", "estado"]
    label_columns = {"codigo": "Código", "zona": "Zona", "estado": "Estado"}

    def pre_delete(self, item):
        if item.estado == "Ocupado":
            raise Exception("No se puede eliminar un espacio ocupado.")


class TarifaModelView(ModelView):
    datamodel = SQLAInterface(Tarifa)
    list_columns = ["nombre", "tipo_vehiculo", "zona", "precio_hora"]
    label_columns = {
        "nombre": "Nombre", "tipo_vehiculo": "Tipo de vehículo",
        "zona": "Zona", "precio_hora": "Precio por hora (Bs)",
    }

    def pre_add(self, item):
        self._validar(item)

    def pre_update(self, item):
        self._validar(item)

    @staticmethod
    def _validar(item):
        if item.precio_hora is None or float(item.precio_hora) <= 0:
            raise Exception("El precio por hora debe ser mayor a 0.")


class TicketModelView(ModelView):
    datamodel = SQLAInterface(Ticket)
    list_columns = ["id", "vehiculo", "espacio", "tarifa", "hora_entrada", "hora_salida", "monto", "estado"]
    add_columns = ["vehiculo", "espacio", "tarifa", "hora_entrada", "observaciones"]
    edit_columns = ["hora_salida", "observaciones"]
    show_columns = [
        "id", "vehiculo", "espacio", "tarifa", "hora_entrada",
        "hora_salida", "monto", "estado", "observaciones",
    ]
    search_columns = ["vehiculo", "espacio", "estado", "hora_entrada", "hora_salida"]
    base_order = ("id", "desc")
    label_columns = {
        "id": "N°", "vehiculo": "Vehículo", "espacio": "Espacio", "tarifa": "Tarifa",
        "hora_entrada": "Entrada", "hora_salida": "Salida", "monto": "Monto (Bs)",
        "estado": "Estado", "observaciones": "Observaciones",
    }

    # ---- Reglas de negocio ----
    def pre_add(self, item):
        if item.espacio.estado != "Libre":
            raise Exception(f"El espacio {item.espacio.codigo} no está libre ({item.espacio.estado}).")
        if item.tarifa.tipo_vehiculo != item.vehiculo.tipo:
            raise Exception(
                f"La tarifa es para {item.tarifa.tipo_vehiculo} y el vehículo es {item.vehiculo.tipo}."
            )
        if item.tarifa.zona_id != item.espacio.zona_id:
            raise Exception("La tarifa no corresponde a la zona del espacio elegido.")
        activo = (
            db.session.query(Ticket)
            .filter(Ticket.vehiculo_id == item.vehiculo.id, Ticket.estado == "Activo")
            .first()
        )
        if activo:
            raise Exception(f"El vehículo {item.vehiculo.placa} ya tiene un ticket activo (#{activo.id}).")
        item.estado = "Activo"
        item.hora_salida = None
        item.monto = None
        item.espacio.estado = "Ocupado"

    def pre_update(self, item):
        if item.estado == "Finalizado":
            raise Exception("El ticket ya fue finalizado y no puede modificarse.")
        if item.hora_salida:
            self._finalizar(item, item.hora_salida)

    def pre_delete(self, item):
        if item.estado == "Activo":
            item.espacio.estado = "Libre"

    @staticmethod
    def _finalizar(item, salida):
        if salida <= item.hora_entrada:
            raise Exception("La hora de salida debe ser posterior a la entrada.")
        item.hora_salida = salida
        item.monto = item.calcular_monto()
        item.estado = "Finalizado"
        item.espacio.estado = "Libre"

    @action("registrar_salida", "Registrar salida ahora", "¿Registrar la salida de los tickets seleccionados?",
            "fa-sign-out", single=False)
    def registrar_salida(self, items):
        if not isinstance(items, list):
            items = [items]
        ahora = datetime.datetime.now()
        hechos = 0
        for t in items:
            if t.estado != "Activo":
                continue
            try:
                self._finalizar(t, ahora)
                self.datamodel.edit(t, raise_exception=True)
                hechos += 1
            except Exception as e:
                db.session.rollback()
                flash(f"Ticket #{t.id}: {e}", "danger")
        if hechos:
            flash(f"{hechos} ticket(s) finalizados.", "success")
        return redirect(self.get_redirect())


appbuilder.add_view(ClienteModelView, "Clientes", icon="fa-users", category="Gestión")
appbuilder.add_view(VehiculoModelView, "Vehículos", icon="fa-car", category="Gestión")
appbuilder.add_view(ZonaModelView, "Zonas", icon="fa-map", category="Infraestructura")
appbuilder.add_view(EspacioModelView, "Espacios", icon="fa-th", category="Infraestructura")
appbuilder.add_view(TarifaModelView, "Tarifas", icon="fa-money", category="Infraestructura")
appbuilder.add_view(TicketModelView, "Tickets", icon="fa-ticket", category="Operación")
