"""Comandos de línea (flask <comando>) para inicializar y poblar el sistema."""
import datetime
import random

import click
from flask_appbuilder import Model

from app import app, appbuilder, db
from app.models import Cliente, Espacio, Tarifa, Ticket, Vehiculo, Zona

VISTAS_OPERADOR = {"ClienteModelView", "VehiculoModelView", "TicketModelView"}
VISTAS_LECTURA = {"ZonaModelView", "EspacioModelView", "TarifaModelView"}
VISTAS_REPORTES = {"IngresosReportView", "OcupacionReportView", "HistorialReportView", "AsistenteView"}
CATEGORIAS_MENU = {"Gestión", "Infraestructura", "Operación", "Reportes", "Asistente IA"}
VISTAS_COMUNES = {"MenuApi", "IndexView"}
PERMISOS_PERFIL = {"can_userinfo", "resetmypassword", "userinfoedit"}


def _permisos_para(rol):
    """Devuelve True si el par (permiso, vista) corresponde al rol dado."""
    def check(perm, vista):
        if vista in VISTAS_COMUNES or vista in CATEGORIAS_MENU:
            return True
        if vista == "UserDBModelView":
            return perm in PERMISOS_PERFIL
        if vista in VISTAS_REPORTES:
            return True
        if vista in VISTAS_OPERADOR:
            if rol == "Operador":
                return True
            return perm in {"can_list", "can_show", "menu_access"}
        if vista in VISTAS_LECTURA:
            return perm in {"can_list", "can_show", "menu_access"}
        return False
    return check


def crear_roles():
    sm = appbuilder.sm
    for rol in ("Operador", "Consulta"):
        role = sm.add_role(rol) or sm.find_role(rol)
        check = _permisos_para(rol)
        for pv in sm.session.query(sm.permissionview_model).all():
            if check(pv.permission.name, pv.view_menu.name):
                sm.add_permission_role(role, pv)


def crear_usuarios():
    sm = appbuilder.sm
    usuarios = [
        ("admin", "Administrador", "Sistema", "admin@parqueo.com", "Admin", "admin123"),
        ("operador", "Operador", "Parqueo", "operador@parqueo.com", "Operador", "operador123"),
        ("consulta", "Consulta", "Parqueo", "consulta@parqueo.com", "Consulta", "consulta123"),
    ]
    for user, nombre, apellido, email, rol, pwd in usuarios:
        if not sm.find_user(username=user):
            sm.add_user(user, nombre, apellido, email, sm.find_role(rol), pwd)


def cargar_datos(semilla=7):
    """Datos de ejemplo coherentes (idempotente: no hace nada si ya hay zonas)."""
    if db.session.query(Zona).count():
        return
    rnd = random.Random(semilla)

    zonas = [Zona(nombre=n, descripcion=d) for n, d in [
        ("Zona A", "Planta baja, cerca de la entrada"),
        ("Zona B", "Primer piso"),
        ("Zona C", "Exterior techado"),
    ]]
    db.session.add_all(zonas)
    db.session.flush()

    espacios = []
    for z, prefijo in zip(zonas, "ABC"):
        for n in range(1, 9):
            espacios.append(Espacio(codigo=f"{prefijo}-{n:02d}", zona=z, estado="Libre"))
    db.session.add_all(espacios)

    precios = {"Auto": 5, "Moto": 3, "Camioneta": 7}
    extra = {"Zona A": 2, "Zona B": 1, "Zona C": 0}
    tarifas = []
    for z in zonas:
        for tipo, base in precios.items():
            tarifas.append(Tarifa(nombre=f"{tipo} {z.nombre}", tipo_vehiculo=tipo,
                                  precio_hora=base + extra[z.nombre], zona=z))
    db.session.add_all(tarifas)

    nombres = ["Carlos Mamani", "Lucía Quispe", "Jorge Flores", "María Condori",
               "Pedro Choque", "Ana Rojas", "Luis Vargas", "Rosa Limachi"]
    clientes = [Cliente(nombre=n, ci=str(4000000 + i * 137), telefono=f"7{rnd.randint(1000000, 9999999)}",
                        email=f"{n.split()[0].lower()}@mail.com") for i, n in enumerate(nombres)]
    db.session.add_all(clientes)
    db.session.flush()

    marcas = [("Toyota", "Corolla", "Auto"), ("Suzuki", "Swift", "Auto"), ("Honda", "CB125", "Moto"),
              ("Yamaha", "FZ", "Moto"), ("Toyota", "Hilux", "Camioneta"), ("Nissan", "Frontier", "Camioneta"),
              ("Kia", "Rio", "Auto"), ("Hyundai", "Tucson", "Camioneta")]
    vehiculos = []
    for i, (marca, modelo, tipo) in enumerate(marcas):
        vehiculos.append(Vehiculo(placa=f"{1000 + i * 111}-{rnd.choice(['ABC', 'XYZ', 'LPZ'])}",
                                  marca=marca, modelo=modelo, tipo=tipo, cliente=clientes[i]))
    db.session.add_all(vehiculos)
    db.session.flush()

    # Historial: 40 tickets finalizados en los últimos 14 días
    ahora = datetime.datetime.now().replace(microsecond=0)
    for _ in range(40):
        v = rnd.choice(vehiculos)
        esp = rnd.choice(espacios)
        tarifa = next(t for t in tarifas if t.tipo_vehiculo == v.tipo and t.zona_id == esp.zona.id)
        entrada = (ahora - datetime.timedelta(days=rnd.randint(1, 14))).replace(
            hour=rnd.randint(7, 18), minute=rnd.choice([0, 15, 30, 45]), second=0)
        salida = entrada + datetime.timedelta(minutes=rnd.randint(25, 420))
        t = Ticket(vehiculo=v, espacio=esp, tarifa=tarifa, hora_entrada=entrada,
                   hora_salida=salida, estado="Finalizado")
        t.monto = t.calcular_monto()
        db.session.add(t)

    # Tickets activos hoy (ocupan espacios)
    for v, esp in zip(vehiculos[:3], [espacios[0], espacios[9], espacios[17]]):
        tarifa = next(t for t in tarifas if t.tipo_vehiculo == v.tipo and t.zona_id == esp.zona.id)
        esp.estado = "Ocupado"
        db.session.add(Ticket(vehiculo=v, espacio=esp, tarifa=tarifa, estado="Activo",
                              hora_entrada=ahora - datetime.timedelta(minutes=rnd.randint(20, 150))))
    db.session.commit()


@app.cli.command("init-db")
def init_db():
    """Crea las tablas, roles, usuarios demo y datos de ejemplo."""
    Model.metadata.create_all(db.engine)
    crear_roles()
    crear_usuarios()
    cargar_datos()
    click.echo("Base de datos lista. Usuarios: admin/admin123, operador/operador123, consulta/consulta123")


@app.cli.command("crear-roles")
def crear_roles_cmd():
    """Vuelve a asignar permisos a los roles Operador y Consulta (útil tras agregar vistas)."""
    crear_roles()
    click.echo("Roles actualizados.")
