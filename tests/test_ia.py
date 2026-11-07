import pytest

from app import ai, db
from app.models import Cliente


class FakeResp:
    def __init__(self, status=200, texto="Hay 5 espacios libres."):
        self.status_code = status
        self._texto = texto

    def json(self):
        return {"candidates": [{"content": {"parts": [{"text": self._texto}]}}]}


@pytest.fixture()
def con_clave(flask_app, monkeypatch):
    monkeypatch.setitem(flask_app.config, "GEMINI_API_KEY", "clave-falsa")
    monkeypatch.setitem(flask_app.config, "GEMINI_MODEL", "gemini-2.5-flash")


def test_endpoint_protegido(client):
    assert client.post("/asistente/preguntar", json={"pregunta": "hola"}).status_code in (302, 401)


def test_pagina_asistente(admin):
    assert admin.get("/asistente/").status_code == 200


def test_sin_clave_devuelve_resumen(flask_app, monkeypatch):
    monkeypatch.setitem(flask_app.config, "GEMINI_API_KEY", "")
    with flask_app.app_context():
        r = ai.responder("¿Cuántos espacios libres hay?")
    assert r["ok"] is False
    assert "GEMINI_API_KEY" in r["respuesta"] and "OCUPACIÓN POR ZONA" in r["respuesta"]


def test_pregunta_vacia_o_larga(flask_app):
    with flask_app.app_context():
        assert ai.responder("   ")["ok"] is False
        assert ai.responder("x" * 501)["ok"] is False


def test_respuesta_ok_y_contexto_sin_datos_personales(flask_app, con_clave, monkeypatch):
    capturado = {}

    def fake_post(url, json=None, headers=None, timeout=None):
        capturado.update(url=url, json=json, headers=headers)
        return FakeResp()

    monkeypatch.setattr(ai.requests, "post", fake_post)
    with flask_app.app_context():
        r = ai.responder("¿Qué espacios libres hay?")
        clientes = db.session.query(Cliente).all()
        enviado = str(capturado["json"])
        for c in clientes:
            assert c.nombre not in enviado and c.ci not in enviado and c.email not in enviado
    assert r == {"ok": True, "respuesta": "Hay 5 espacios libres.", "modelo": "gemini-2.5-flash"}
    assert "gemini-2.5-flash:generateContent" in capturado["url"]
    assert capturado["headers"]["x-goog-api-key"] == "clave-falsa"
    assert "TARIFAS" in enviado and "PREGUNTA DEL USUARIO" in enviado


def test_fallback_de_modelo_en_404(flask_app, con_clave, monkeypatch):
    usados = []

    def fake_post(url, **kw):
        usados.append(url)
        return FakeResp(404) if len(usados) == 1 else FakeResp(200, "ok")

    monkeypatch.setattr(ai.requests, "post", fake_post)
    with flask_app.app_context():
        r = ai.responder("hola")
    assert r["ok"] and len(usados) == 2 and r["modelo"] != "gemini-2.5-flash"


def test_limite_de_cuota(flask_app, con_clave, monkeypatch):
    monkeypatch.setattr(ai.requests, "post", lambda *a, **k: FakeResp(429))
    with flask_app.app_context():
        r = ai.responder("hola")
    assert not r["ok"] and "límite" in r["respuesta"]


def test_endpoint_json(admin, con_clave, monkeypatch):
    monkeypatch.setattr(ai.requests, "post", lambda *a, **k: FakeResp(200, "Respuesta de prueba"))
    resp = admin.post("/asistente/preguntar", json={"pregunta": "¿Cuánto se recaudó hoy?"})
    assert resp.status_code == 200 and resp.get_json()["respuesta"] == "Respuesta de prueba"
