from flask import Blueprint, current_app, g, jsonify, request

from gnc_lite.services import companies

bp = Blueprint("companies", __name__, url_prefix="/api/companies")


@bp.get("")
def list_companies() -> tuple:
    registry = companies.CompanyRegistry()
    result = [
        {"id": item.id, "name": item.name, "db_path": item.db_path} for item in registry.list()
    ]
    return jsonify({"companies": result})


@bp.post("/select")
def select_company() -> tuple:
    payload = request.get_json(silent=True) or {}
    wanted = payload.get("company_id")
    registry = companies.CompanyRegistry()
    company = registry.get(wanted) if wanted else None
    if company is None:
        items = registry.list()
        company = items[0] if items else None
    if company is None:
        return jsonify({"error": "no_company"}), 404
    if current_app.config.get("COMPANY_ID") != company.id:
        current_app.config["COMPANY_ID"] = company.id
        current_app.config["SESSION"] = None
        current_app.config["USER_ID"] = None
    return jsonify({"ok": True, "company": {"id": company.id, "name": company.name}})


@bp.post("")
def create_company() -> tuple:
    payload = request.get_json(silent=True) or {}
    name = str(payload.get("name") or "").strip()
    admin_user = str(payload.get("admin_user") or "admin").strip()
    admin_pass = str(payload.get("admin_pass") or "")
    if not name:
        return jsonify({"error": "Informe o nome da empresa."}), 400
    if not admin_pass:
        return jsonify({"error": "Informe a senha do administrador."}), 400
    try:
        company = companies.create_company(
            companies.CompanyRegistry(), name, admin_user, admin_pass
        )
    except Exception as exc:  # noqa: BLE001 - devolve o motivo ao frontend
        return jsonify({"error": str(exc)}), 400
    current_app.config["COMPANY_ID"] = company.id
    current_app.config["SESSION"] = None
    current_app.config["USER_ID"] = None
    return jsonify({"ok": True, "company": {"id": company.id, "name": company.name}})


@bp.post("/reset")
def reset_company() -> tuple:
    """Zera lancamentos/titulos/contas, mantendo os usuarios logaveis."""
    web = getattr(g, "web", None)
    if web is None:
        return jsonify({"error": "no_company_open"}), 400
    user = getattr(web, "user", None)
    if user is None or not user.role.is_admin:
        return jsonify({"error": "forbidden"}), 403
    user_id = user.id
    try:
        web.dbsession.close()
    except Exception:  # noqa: BLE001 - reset precisa continuar mesmo se fechar falhar
        pass
    companies.reset_company_db(web.company)
    current_app.config["SESSION"] = None
    current_app.config["USER_ID"] = user_id
    return jsonify({"ok": True})
