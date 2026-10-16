from flask import Blueprint, g, jsonify, request

from gnc_lite.services import importer

bp = Blueprint("import", __name__, url_prefix="/api/import")


def _save_upload(file_storage):
    import os
    import tempfile

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".csv")
    try:
        file_storage.save(tmp.name)
        return tmp.name
    except Exception:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass
        raise


def _cleanup(path: str) -> None:
    import os

    try:
        os.unlink(path)
    except OSError:
        pass


@bp.post("/csv")
def import_csv() -> tuple:
    web = getattr(g, "web", None)
    if web is None or not web.can_write:
        return jsonify({"error": "forbidden"}), 403
    f = request.files.get("file")
    if f is None:
        return jsonify({"error": "no_file"}), 400
    path = _save_upload(f)
    try:
        try:
            txs = importer.import_csv_file(web.ledger, path)
        except importer.ImportParseError as exc:
            return jsonify({"error": str(exc)}), 400
        new, skipped = importer.partition_new(web.ledger, txs)
        if new:
            web.ledger.post_many(new)
            web.dbsession.commit()
        return jsonify(
            {
                "posted": len(new),
                "skipped": skipped,
                "transaction_ids": [t.id for t in new],
            }
        )
    finally:
        _cleanup(path)


@bp.post("/qif")
def import_qif() -> tuple:
    web = getattr(g, "web", None)
    if web is None or not web.can_write:
        return jsonify({"error": "forbidden"}), 403
    f = request.files.get("file")
    if f is None:
        return jsonify({"error": "no_file"}), 400
    account_id = request.form.get("account_id", type=int)
    if account_id is None:
        return jsonify({"error": "Informe a conta destino (account_id)."}), 400
    account = web.ledger.repo.get_account(account_id)
    if account is None:
        return jsonify({"error": "Conta nao encontrada."}), 400
    path = _save_upload(f)
    try:
        try:
            txs = importer.import_qif_file(web.ledger, path, account)
        except importer.ImportParseError as exc:
            return jsonify({"error": str(exc)}), 400
        new, skipped = importer.partition_new(web.ledger, txs)
        if new:
            web.ledger.post_many(new)
            web.dbsession.commit()
        return jsonify(
            {
                "posted": len(new),
                "skipped": skipped,
                "transaction_ids": [t.id for t in new],
            }
        )
    finally:
        _cleanup(path)


@bp.post("/ofx")
def import_ofx() -> tuple:
    web = getattr(g, "web", None)
    if web is None or not web.can_write:
        return jsonify({"error": "forbidden"}), 403
    f = request.files.get("file")
    if f is None:
        return jsonify({"error": "no_file"}), 400
    account_id = request.form.get("account_id", type=int)
    counter_id = request.form.get("counter_account_id", type=int)
    if account_id is None or counter_id is None:
        return jsonify({"error": "Informe conta destino e contrapartida."}), 400
    account = web.ledger.repo.get_account(account_id)
    counter = web.ledger.repo.get_account(counter_id)
    if account is None or counter is None:
        return jsonify({"error": "Conta nao encontrada."}), 400
    path = _save_upload(f)
    try:
        try:
            txs = importer.import_ofx_file(web.ledger, path, account, counter)
        except importer.ImportParseError as exc:
            return jsonify({"error": str(exc)}), 400
        new, skipped = importer.partition_new(web.ledger, txs)
        if new:
            web.ledger.post_many(new)
            web.dbsession.commit()
        return jsonify(
            {
                "posted": len(new),
                "skipped": skipped,
                "transaction_ids": [t.id for t in new],
            }
        )
    finally:
        _cleanup(path)
