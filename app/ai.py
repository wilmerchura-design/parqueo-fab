"""Asistente de IA del parqueo basado en la API gratuita de Google Gemini.

El asistente responde preguntas en lenguaje natural usando como contexto datos
agregados de la base (ocupación, tarifas, ingresos, vehículos estacionados).
No se envían datos personales de clientes (nombres, C.I., teléfonos, correos).
"""
import datetime

import requests
from flask import current_app

from app import db
from app.models import Espacio, Tarifa, Zona
from app.reports import reporte_ingresos, reporte_ocupacion

API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent"
MODELOS_ALTERNATIVOS = ("gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-2.0-flash")
MAX_PREGUNTA = 500

INSTRUCCION = (
    "Eres el asistente de un sistema de parqueo (estacionamiento) en Bolivia. "
    "Responde en español, de forma breve y clara, usando SOLO los datos del contexto. "
    "Los montos están en bolivianos (Bs). Si el contexto no contiene la información "
    "necesaria, dilo y sugiere en qué sección del sistema consultarla. "
    "No inventes cifras ni placas."
)


def construir_contexto():
    """Resumen textual de la situación actual del parqueo, tomado de la BD."""
    ahora = datetime.datetime.now()
    hoy = ahora.date()
    ocup = reporte_ocupacion()
    ing_hoy = reporte_ingresos(hoy, hoy)
    ing_sem = reporte_ingresos(hoy - datetime.timedelta(days=6), hoy)

    lineas = [f"Fecha y hora actual: {ahora:%d/%m/%Y %H:%M}", "", "OCUPACIÓN POR ZONA:"]
    for z in ocup["zonas"]:
        libres = [e.codigo for e in db.session.query(Espacio).join(Zona)
                  .filter(Zona.nombre == z["zona"], Espacio.estado == "Libre")
                  .order_by(Espacio.codigo).limit(10)]
        lineas.append(
            f"- {z['zona']}: {z['Libre']} libres, {z['Ocupado']} ocupados, "
            f"{z['Mantenimiento']} en mantenimiento ({z['porcentaje']}% ocupación). "
            f"Algunos libres: {', '.join(libres) or 'ninguno'}")
    t = ocup["totales"]
    lineas.append(f"TOTAL: {t['Libre']} libres de {t['total']} espacios ({t['porcentaje']}% ocupación)")

    lineas += ["", "TARIFAS (Bs por hora o fracción, mínimo 1 hora):"]
    for tf in db.session.query(Tarifa).join(Zona).order_by(Zona.nombre, Tarifa.tipo_vehiculo):
        lineas.append(f"- {tf.zona.nombre} / {tf.tipo_vehiculo}: Bs {float(tf.precio_hora):.2f}")

    lineas += ["", "INGRESOS:",
               f"- Hoy: Bs {ing_hoy['total']:.2f} en {ing_hoy['cantidad']} tickets cobrados",
               f"- Últimos 7 días: Bs {ing_sem['total']:.2f} en {ing_sem['cantidad']} tickets "
               f"(promedio Bs {ing_sem['promedio']:.2f})"]
    for zona, c, s in ing_sem["por_zona"]:
        lineas.append(f"  · {zona}: Bs {s:.2f} ({c} tickets)")

    lineas += ["", f"VEHÍCULOS ESTACIONADOS AHORA ({len(ocup['activos'])}):"]
    for a in ocup["activos"]:
        lineas.append(f"- {a['placa']} en {a['espacio']} ({a['zona']}), {a['minutos']} min, "
                      f"monto estimado Bs {a['estimado']:.2f}")
    return "\n".join(lineas)


def _llamar(modelo, pregunta, contexto, api_key, timeout):
    cuerpo = {
        "systemInstruction": {"parts": [{"text": INSTRUCCION}]},
        "contents": [{"role": "user", "parts": [
            {"text": f"CONTEXTO DEL SISTEMA:\n{contexto}\n\nPREGUNTA DEL USUARIO:\n{pregunta}"}]}],
        "generationConfig": {"temperature": 0.3, "maxOutputTokens": 700},
    }
    return requests.post(API_URL.format(modelo=modelo), json=cuerpo, timeout=timeout,
                         headers={"x-goog-api-key": api_key, "Content-Type": "application/json"})


def responder(pregunta, timeout=25):
    """Devuelve {"ok": bool, "respuesta": str, "modelo": str|None}."""
    pregunta = (pregunta or "").strip()
    if not pregunta:
        return {"ok": False, "respuesta": "Escribe una pregunta.", "modelo": None}
    if len(pregunta) > MAX_PREGUNTA:
        return {"ok": False, "respuesta": f"La pregunta supera los {MAX_PREGUNTA} caracteres.", "modelo": None}

    contexto = construir_contexto()
    api_key = current_app.config.get("GEMINI_API_KEY", "")
    if not api_key:
        return {"ok": False, "modelo": None, "respuesta": (
            "La IA no está configurada: define GEMINI_API_KEY en el archivo .env "
            "(clave gratuita en https://aistudio.google.com/apikey). "
            "Mientras tanto, este es el resumen actual del parqueo:\n\n" + contexto)}

    principal = current_app.config.get("GEMINI_MODEL", MODELOS_ALTERNATIVOS[0])
    modelos = [principal] + [m for m in MODELOS_ALTERNATIVOS if m != principal]
    ultimo_error = "sin respuesta"
    for modelo in modelos:
        try:
            r = _llamar(modelo, pregunta, contexto, api_key, timeout)
        except requests.RequestException as e:
            return {"ok": False, "modelo": modelo, "respuesta": f"No se pudo contactar al servicio de IA: {e}"}
        if r.status_code == 200:
            try:
                texto = r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
            except (KeyError, IndexError, ValueError):
                return {"ok": False, "modelo": modelo,
                        "respuesta": "La IA no devolvió una respuesta (posible filtro de contenido)."}
            return {"ok": True, "respuesta": texto, "modelo": modelo}
        if r.status_code == 429:
            return {"ok": False, "modelo": modelo,
                    "respuesta": "Se alcanzó el límite gratuito de la API. Intenta de nuevo en un minuto."}
        if r.status_code in (400, 403):
            return {"ok": False, "modelo": modelo,
                    "respuesta": "La API rechazó la solicitud; revisa que GEMINI_API_KEY sea válida."}
        ultimo_error = f"HTTP {r.status_code}"  # 404 u otro: probar el siguiente modelo
    return {"ok": False, "modelo": None, "respuesta": f"No hay modelo disponible ({ultimo_error})."}
