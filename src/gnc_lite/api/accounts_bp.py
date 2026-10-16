from flask import Blueprint, g, jsonify, request

from gnc_lite.domain.account import (
    ACCOUNT_KIND_LABELS,
    ACCOUNT_KIND_NORMAL,
    ACCOUNT_KIND_TYPE,
    ACCOUNT_KINDS,
    AccountType,
)
from gnc_lite.domain.errors import GncLiteError

bp = Blueprint("accounts", __name__, url_prefix="/api/accounts")


def _serialize(ledger, a) -> dict:
    bal = ledger.balance(a)
    raw = ledger.raw_balance(a).minor_units
    available = a.available_credit_minor(raw)
    return {
        "id": a.id,
        "code": a.code,
        "name": a.name,
        "type": a.type.value,
        "type_label": a.type.label,
        "placeholder": a.placeholder,
        "parent_id": a.parent.id if a.parent is not None else None,
        "currency": bal.currency,
        "balance_minor": bal.minor_units,
        "description": a.description or "",
        "kind": a.kind,
        "kind_label": ACCOUNT_KIND_LABELS.get(a.kind, a.kind),
        "limit_minor": a.credit_limit_minor,
        "used_minor": a.used_credit_minor(raw) if a.is_special else 0,
        "available_minor": available,
    }


@bp.get("")
def list_accounts() -> tuple:
    web = getattr(g, "web", None)
    if web is None:
        return jsonify({"accounts": []})
    ledger = web.ledger
    out = [_serialize(ledger, a) for a in ledger.list_accounts()]
    out.sort(key=lambda x: (x["code"] or "", x["name"]))
    return jsonify({"accounts": out})


@bp.post("")
def create_account() -> tuple:
    web = getattr(g, "web", None)
    if web is None or not web.can_write:
        return jsonify({"error": "forbidden"}), 403
    payload = request.get_json(silent=True) or {}
    code = str(payload.get("code") or "").strip()
    name = str(payload.get("name") or "").strip()
    kind = str(payload.get("kind") or ACCOUNT_KIND_NORMAL)
    if kind not in ACCOUNT_KINDS:
        return jsonify({"error": f"Natureza invalida: {kind}"}), 400
    try:
        limit_minor = int(payload.get("limit_minor") or 0)
    except (TypeError, ValueError):
        return jsonify({"error": "Limite invalido."}), 400
    if limit_minor < 0:
        return jsonify({"error": "Limite deve ser positivo."}), 400
    type_value = str(payload.get("type") or "")
    parent_id = payload.get("parent_id")
    description = str(payload.get("description") or "")
    placeholder = bool(payload.get("placeholder", False))
    if not code or not name:
        return jsonify({"error": "Informe codigo e nome."}), 400
    if kind in ACCOUNT_KIND_TYPE:
        # Cartao e passivo, cheque especial e ativo: tratamento diferencial fixo.
        acc_type = ACCOUNT_KIND_TYPE[kind]
    else:
        try:
            acc_type = AccountType(type_value)
        except ValueError:
            return jsonify({"error": f"Tipo invalido: {type_value}"}), 400
    ledger = web.ledger
    if ledger.repo.get_account_by_code(code) is not None:
        return jsonify({"error": f"Codigo ja existe: {code}"}), 400
    parent = None
    if parent_id is not None:
        parent = ledger.repo.get_account(int(parent_id))
        if parent is None:
            return jsonify({"error": "Conta pai nao encontrada."}), 400
    try:
        account = ledger.create_account(
            code, name, acc_type, parent=parent, description=description,
            placeholder=placeholder, kind=kind, credit_limit_minor=limit_minor,
        )
        web.dbsession.commit()
    except GncLiteError as exc:
        web.dbsession.rollback()
        return jsonify({"error": str(exc)}), 400
    return jsonify({"ok": True, "account": _serialize(ledger, account)})


@bp.patch("/<int:account_id>")
def update_account(account_id: int) -> tuple:
    web = getattr(g, "web", None)
    if web is None or not web.can_write:
        return jsonify({"error": "forbidden"}), 403
    ledger = web.ledger
    account = ledger.repo.get_account(account_id)
    if account is None:
        return jsonify({"error": "Conta nao encontrada."}), 404
    payload = request.get_json(silent=True) or {}
    if "name" in payload:
        account.name = str(payload["name"] or "").strip() or account.name
    if "description" in payload:
        account.description = str(payload["description"] or "")
    if "placeholder" in payload:
        account.placeholder = bool(payload["placeholder"])
    if "kind" in payload:
        kind = str(payload["kind"] or ACCOUNT_KIND_NORMAL)
        if kind not in ACCOUNT_KINDS:
            return jsonify({"error": f"Natureza invalida: {kind}"}), 400
        account.kind = kind
        if kind in ACCOUNT_KIND_TYPE:
            account.type = ACCOUNT_KIND_TYPE[kind]
    if "limit_minor" in payload:
        try:
            limit_minor = int(payload["limit_minor"] or 0)
        except (TypeError, ValueError):
            return jsonify({"error": "Limite invalido."}), 400
        if limit_minor < 0:
            return jsonify({"error": "Limite deve ser positivo."}), 400
        account.credit_limit_minor = limit_minor
    try:
        ledger.update_account(account)
        web.dbsession.commit()
    except GncLiteError as exc:
        web.dbsession.rollback()
        return jsonify({"error": str(exc)}), 400
    return jsonify({"ok": True, "account": _serialize(ledger, account)})
