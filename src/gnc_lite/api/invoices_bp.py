from __future__ import annotations

from datetime import date

from flask import Blueprint, g, jsonify, request

from gnc_lite.domain.invoice import InvoiceError, InvoiceKind
from gnc_lite.domain.money import DEFAULT_CURRENCY, Money
from gnc_lite.domain.party import Party, PartyType
from gnc_lite.services.billing import BillingService

bp = Blueprint("invoices", __name__, url_prefix="/api/invoices")


def _party_json(party: Party) -> dict:
    return {
        "id": party.id,
        "name": party.name,
        "type": party.type.value,
        "document": party.document or "",
        "email": party.email or "",
        "phone": party.phone or "",
    }


def _invoice_json(invoice) -> dict:
    return {
        "id": invoice.id,
        "kind": invoice.kind.value,
        "kind_label": invoice.kind.label,
        "amount_minor": invoice.amount.minor_units,
        "open_minor": invoice.open_amount.minor_units,
        "settled_minor": invoice.settled_amount.minor_units,
        "issue_date": invoice.issue_date.isoformat(),
        "due_date": invoice.due_date.isoformat(),
        "party_id": invoice.party.id if invoice.party is not None else None,
        "party_name": invoice.party_name(),
        "description": invoice.description or "",
        "status": invoice.status.value,
    }


def _billing() -> BillingService | None:
    web = getattr(g, "web", None)
    if web is None:
        return None
    return BillingService(web.ledger)


@bp.get("/parties")
def list_parties() -> tuple:
    billing = _billing()
    if billing is None:
        return jsonify({"parties": []})
    kind = request.args.get("type")
    party_type = None
    if kind:
        try:
            party_type = PartyType(kind)
        except ValueError:
            return jsonify({"error": f"Tipo invalido: {kind}"}), 400
    return jsonify({"parties": [_party_json(p) for p in billing.parties(party_type)]})


@bp.post("/parties")
def create_party() -> tuple:
    web = getattr(g, "web", None)
    if web is None or not web.can_write:
        return jsonify({"error": "forbidden"}), 403
    payload = request.get_json(silent=True) or {}
    name = str(payload.get("name") or "").strip()
    if not name:
        return jsonify({"error": "Informe o nome."}), 400
    try:
        party_type = PartyType(str(payload.get("type") or PartyType.CUSTOMER.value))
    except ValueError:
        return jsonify({"error": "Tipo invalido."}), 400
    billing = BillingService(web.ledger)
    party = billing.create_party(
        name,
        party_type,
        document=str(payload.get("document") or ""),
        email=str(payload.get("email") or ""),
        phone=str(payload.get("phone") or ""),
        notes=str(payload.get("notes") or ""),
    )
    web.dbsession.commit()
    return jsonify({"ok": True, "party": _party_json(party)})


@bp.get("")
def list_invoices() -> tuple:
    billing = _billing()
    if billing is None:
        return jsonify({"invoices": []})
    kind_param = request.args.get("kind")
    kind = None
    if kind_param:
        try:
            kind = InvoiceKind(kind_param)
        except ValueError:
            return jsonify({"error": f"Tipo invalido: {kind_param}"}), 400
    if request.args.get("open_only") == "1":
        invoices = billing.open_invoices(kind)
    elif kind is not None:
        invoices = [i for i in billing.invoices() if i.kind is kind]
    else:
        invoices = billing.invoices()
    return jsonify({"invoices": [_invoice_json(i) for i in invoices]})


def _parse_issue(payload: dict, billing: BillingService):
    try:
        party_id = int(payload.get("party_id"))
    except (TypeError, ValueError):
        return None, jsonify({"error": "Informe a parte (party_id)."}), 400
    party = billing.repo.get_party(party_id)
    if party is None:
        return None, jsonify({"error": "Parte nao encontrada."}), 404
    try:
        minor = int(payload.get("amount_minor", 0))
    except (TypeError, ValueError):
        return None, jsonify({"error": "Valor invalido."}), 400
    if minor <= 0:
        return None, jsonify({"error": "O valor deve ser positivo."}), 400
    try:
        issue = date.fromisoformat(str(payload.get("issue_date") or ""))
        due = date.fromisoformat(str(payload.get("due_date") or ""))
    except ValueError:
        return None, jsonify({"error": "Datas invalidas (AAAA-MM-DD)."}), 400
    currency = str(payload.get("currency") or DEFAULT_CURRENCY)
    return (
        party,
        Money(minor, currency),
        issue,
        due,
        str(payload.get("description") or ""),
        payload,
    ), None, None


def _optional_account(billing: BillingService, payload: dict, key: str):
    raw = payload.get(key)
    if raw in (None, ""):
        return None
    try:
        account = billing.repo.get_account(int(raw))
    except (TypeError, ValueError):
        account = None
    return account


@bp.post("/receivable")
def issue_receivable() -> tuple:
    web = getattr(g, "web", None)
    if web is None or not web.can_write:
        return jsonify({"error": "forbidden"}), 403
    billing = BillingService(web.ledger)
    payload = request.get_json(silent=True) or {}
    parsed, err, code = _parse_issue(payload, billing)
    if err is not None:
        return err, code
    party, amount, issue, due, description, full = parsed
    try:
        invoice = billing.issue_receivable(
            party,
            amount,
            issue,
            due,
            income_account=_optional_account(billing, full, "income_account_id"),
            receivable_account=_optional_account(billing, full, "receivable_account_id"),
            description=description,
        )
        web.dbsession.commit()
    except InvoiceError as exc:
        web.dbsession.rollback()
        return jsonify({"error": str(exc)}), 400
    return jsonify({"ok": True, "invoice": _invoice_json(invoice)})


@bp.post("/payable")
def issue_payable() -> tuple:
    web = getattr(g, "web", None)
    if web is None or not web.can_write:
        return jsonify({"error": "forbidden"}), 403
    billing = BillingService(web.ledger)
    payload = request.get_json(silent=True) or {}
    parsed, err, code = _parse_issue(payload, billing)
    if err is not None:
        return err, code
    party, amount, issue, due, description, full = parsed
    try:
        invoice = billing.issue_payable(
            party,
            amount,
            issue,
            due,
            expense_account=_optional_account(billing, full, "expense_account_id"),
            payable_account=_optional_account(billing, full, "payable_account_id"),
            description=description,
        )
        web.dbsession.commit()
    except InvoiceError as exc:
        web.dbsession.rollback()
        return jsonify({"error": str(exc)}), 400
    return jsonify({"ok": True, "invoice": _invoice_json(invoice)})


@bp.post("/<int:invoice_id>/settle")
def settle(invoice_id: int) -> tuple:
    web = getattr(g, "web", None)
    if web is None or not web.can_write:
        return jsonify({"error": "forbidden"}), 403
    billing = BillingService(web.ledger)
    invoice = billing.repo.get_invoice(invoice_id)
    if invoice is None:
        return jsonify({"error": "Titulo nao encontrado."}), 404
    payload = request.get_json(silent=True) or {}
    try:
        settle_date = date.fromisoformat(str(payload.get("date") or ""))
    except ValueError:
        return jsonify({"error": "Data invalida (AAAA-MM-DD)."}), 400
    try:
        cash = billing.repo.get_account(int(payload.get("cash_account_id")))
    except (TypeError, ValueError):
        cash = None
    if cash is None:
        return jsonify({"error": "Informe a conta caixa/banco."}), 400
    amount = None
    if payload.get("amount_minor") not in (None, ""):
        try:
            amount = Money(int(payload["amount_minor"]), invoice.amount.currency)
        except (TypeError, ValueError):
            return jsonify({"error": "Valor invalido."}), 400
    try:
        billing.settle(invoice, settle_date, cash, amount)
        web.dbsession.commit()
    except InvoiceError as exc:
        web.dbsession.rollback()
        return jsonify({"error": str(exc)}), 400
    return jsonify({"ok": True, "invoice": _invoice_json(invoice)})
