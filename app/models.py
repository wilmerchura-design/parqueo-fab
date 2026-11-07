import datetime
import math

from flask_appbuilder import Model
from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import relationship

TIPOS_VEHICULO = ("Auto", "Moto", "Camioneta")
ESTADOS_ESPACIO = ("Libre", "Ocupado", "Mantenimiento")
ESTADOS_TICKET = ("Activo", "Finalizado")


class Cliente(Model):
    __tablename__ = "cliente"
    id = Column(Integer, primary_key=True)
    nombre = Column(String(100), nullable=False)
    ci = Column(String(20), unique=True, nullable=False)
    telefono = Column(String(20))
    email = Column(String(120))

    def __repr__(self):
        return f"{self.nombre} ({self.ci})"


class Vehiculo(Model):
    __tablename__ = "vehiculo"
    id = Column(Integer, primary_key=True)
    placa = Column(String(15), unique=True, nullable=False)
    marca = Column(String(50))
    modelo = Column(String(50))
    tipo = Column(Enum(*TIPOS_VEHICULO), nullable=False, default="Auto")
    cliente_id = Column(Integer, ForeignKey("cliente.id"), nullable=False)
    cliente = relationship("Cliente", backref="vehiculos")

    def __repr__(self):
        return f"{self.placa} - {self.tipo}"


class Zona(Model):
    __tablename__ = "zona"
    id = Column(Integer, primary_key=True)
    nombre = Column(String(50), unique=True, nullable=False)
    descripcion = Column(String(200))

    def __repr__(self):
        return self.nombre


class Espacio(Model):
    __tablename__ = "espacio"
    id = Column(Integer, primary_key=True)
    codigo = Column(String(10), unique=True, nullable=False)
    estado = Column(Enum(*ESTADOS_ESPACIO), nullable=False, default="Libre")
    zona_id = Column(Integer, ForeignKey("zona.id"), nullable=False)
    zona = relationship("Zona", backref="espacios")

    def __repr__(self):
        return f"{self.codigo} ({self.zona})"


class Tarifa(Model):
    __tablename__ = "tarifa"
    id = Column(Integer, primary_key=True)
    nombre = Column(String(60), nullable=False)
    tipo_vehiculo = Column(Enum(*TIPOS_VEHICULO), nullable=False)
    precio_hora = Column(Numeric(8, 2), nullable=False)
    zona_id = Column(Integer, ForeignKey("zona.id"), nullable=False)
    zona = relationship("Zona", backref="tarifas")

    def __repr__(self):
        return f"{self.nombre} - Bs {self.precio_hora}/h"


class Ticket(Model):
    __tablename__ = "ticket"
    id = Column(Integer, primary_key=True)
    vehiculo_id = Column(Integer, ForeignKey("vehiculo.id"), nullable=False)
    vehiculo = relationship("Vehiculo", backref="tickets")
    espacio_id = Column(Integer, ForeignKey("espacio.id"), nullable=False)
    espacio = relationship("Espacio", backref="tickets")
    tarifa_id = Column(Integer, ForeignKey("tarifa.id"), nullable=False)
    tarifa = relationship("Tarifa", backref="tickets")
    hora_entrada = Column(DateTime, nullable=False, default=datetime.datetime.now)
    hora_salida = Column(DateTime)
    monto = Column(Numeric(10, 2))
    estado = Column(Enum(*ESTADOS_TICKET), nullable=False, default="Activo")
    observaciones = Column(Text)

    def calcular_monto(self):
        """Cobro por hora o fracción (mínimo 1 hora)."""
        if not self.hora_salida:
            return None
        segundos = (self.hora_salida - self.hora_entrada).total_seconds()
        horas = max(1, math.ceil(segundos / 3600))
        return round(horas * float(self.tarifa.precio_hora), 2)

    def __repr__(self):
        return f"Ticket #{self.id}"
