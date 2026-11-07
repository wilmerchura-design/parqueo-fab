from flask import jsonify, request
from flask_appbuilder import BaseView, expose, has_access

from app import appbuilder
from app.ai import responder


class AsistenteView(BaseView):
    route_base = "/asistente"
    default_view = "index"

    @expose("/")
    @has_access
    def index(self):
        return self.render_template("asistente.html", base_template=appbuilder.base_template,
                                    appbuilder=appbuilder)

    @expose("/preguntar", methods=["POST"])
    @has_access
    def preguntar(self):
        datos = request.get_json(silent=True) or {}
        return jsonify(responder(datos.get("pregunta", "")))


appbuilder.add_view(AsistenteView, "Asistente del parqueo", icon="fa-comments", category="Asistente IA")
