"""Repository — mapeamento entre rows SQLAlchemy e objetos de domínio.

Escopo por perfil: instancie `Repository(session, profile_id)` para que todas as
consultas de contas/categorias/transações/orçamentos fiquem restritas ao perfil.
`profile_id=None` opera sem filtro (uso interno/migração e testes de baixo nível).
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from money99.db.models import (
    AccountRow,
    BudgetRow,
    CategoryRow,
    ProfileRow,
    SplitRow,
    TransactionRow,
    UserRow,
)
from money99.domain.account import Account, AccountType
from money99.domain.profile import Profile, ProfileKind
from money99.domain.transaction import Split, Transaction

_SCOPED_TABLES = (AccountRow, CategoryRow, TransactionRow, BudgetRow)


def _activity_value(activity) -> str:
    if isinstance(activity, (list, tuple)):
        values = [getattr(item, "value", item) or "servicos" for item in activity]
        return ",".join(values) if values else "servicos"
    return getattr(activity, "value", activity) or "servicos"


class Repository:
    def __init__(self, session: Session, profile_id: int | None = None):
        self.session = session
        self.profile_id = profile_id

    def _scope(self, stmt, model):
        if self.profile_id is not None and model in _SCOPED_TABLES:
            stmt = stmt.where(model.profile_id == self.profile_id)
        return stmt

    # --- perfis ---

    def list_profiles(self, *, active_only: bool = False) -> list[Profile]:
        stmt = select(ProfileRow).order_by(ProfileRow.name)
        if active_only:
            stmt = stmt.where(ProfileRow.active.is_(True))
        return [self._to_profile(row) for row in self.session.scalars(stmt)]

    def get_profile(self, profile_id: int) -> Profile:
        row = self.session.get(ProfileRow, profile_id)
        if row is None:
            raise LookupError(f"perfil {profile_id} não encontrado")
        return self._to_profile(row)

    def add_profile(self, profile: Profile) -> Profile:
        row = ProfileRow(
            name=profile.name,
            kind=profile.kind.value,
            cnpj=profile.cnpj,
            legal_name=profile.legal_name,
            trade_name=profile.trade_name,
            opened_on=profile.opened_on,
            annual_limit=profile.annual_limit,
            activity=_activity_value(profile.activity),
            active=profile.active,
        )
        self.session.add(row)
        self.session.flush()
        return self._to_profile(row)

    def update_profile(self, profile: Profile) -> Profile:
        if profile.id is None:
            raise ValueError("perfil sem id")
        row = self.session.get(ProfileRow, profile.id)
        if row is None:
            raise LookupError(f"perfil {profile.id} não encontrado")
        row.name = profile.name
        row.kind = profile.kind.value
        row.cnpj = profile.cnpj
        row.legal_name = profile.legal_name
        row.trade_name = profile.trade_name
        row.opened_on = profile.opened_on
        row.annual_limit = profile.annual_limit
        row.activity = _activity_value(profile.activity)
        row.active = profile.active
        return self._to_profile(row)

    def delete_profile(self, profile_id: int) -> None:
        row = self.session.get(ProfileRow, profile_id)
        if row is None:
            raise LookupError(f"perfil {profile_id} não encontrado")
        if self.session.scalar(select(func.count()).select_from(ProfileRow)) <= 1:
            raise ValueError("não é possível excluir o único perfil")
        used = self.session.scalar(
            select(func.count()).select_from(AccountRow).where(
                AccountRow.profile_id == profile_id
            )
        ) or 0
        used += self.session.scalar(
            select(func.count()).select_from(TransactionRow).where(
                TransactionRow.profile_id == profile_id
            )
        ) or 0
        if used:
            raise ValueError("perfil possui dados; desative em vez de excluir")
        for model in (BudgetRow, CategoryRow):
            self.session.query(model).filter(model.profile_id == profile_id).delete()
        self.session.delete(row)

    # --- contas ---

    def list_accounts(self, *, active_only: bool = False) -> list[Account]:
        stmt = select(AccountRow).order_by(AccountRow.name)
        stmt = self._scope(stmt, AccountRow)
        if active_only:
            stmt = stmt.where(AccountRow.active.is_(True))
        return [self._to_account(row) for row in self.session.scalars(stmt)]

    def get_account(self, account_id: int) -> Account:
        row = self.session.get(AccountRow, account_id)
        if row is None:
            raise LookupError(f"conta {account_id} não encontrada")
        return self._to_account(row)

    def add_account(self, account: Account) -> Account:
        row = AccountRow(
            profile_id=self.profile_id,
            name=account.name,
            type=account.type.value,
            initial_balance=account.initial_balance,
            active=account.active,
            credit_limit=account.credit_limit,
        )
        self.session.add(row)
        self.session.flush()
        return self._to_account(row)

    def update_account(self, account: Account) -> Account:
        if account.id is None:
            raise ValueError("conta sem id")
        row = self.session.get(AccountRow, account.id)
        if row is None:
            raise LookupError(f"conta {account.id} não encontrada")
        row.name = account.name
        row.type = account.type.value
        row.initial_balance = account.initial_balance
        row.active = account.active
        row.credit_limit = account.credit_limit
        return self._to_account(row)

    def delete_account(self, account_id: int) -> None:
        row = self.session.get(AccountRow, account_id)
        if row is None:
            raise LookupError(f"conta {account_id} não encontrada")
        used = self.session.scalar(
            select(func.count())
            .select_from(TransactionRow)
            .where(
                (TransactionRow.account_id == account_id)
                | (TransactionRow.transfer_account_id == account_id)
            )
        )
        if used:
            raise ValueError("conta possui transações; desative em vez de excluir")
        self.session.delete(row)

    def account_balances(self, account_id: int, *, as_of: str | None = None) -> dict:
        """Saldo até `as_of` (padrão: hoje) e lançamentos futuros.

        `balance` considera apenas transações com data <= hoje; `future` é o
        efeito líquido das transações com data posterior (transferências entram
        com o sinal invertido na conta de destino).
        """
        account = self.get_account(account_id)
        cutoff = as_of or date.today().isoformat()

        def totals(column) -> tuple[int, int]:
            current = func.coalesce(func.sum(
                case((TransactionRow.date <= cutoff, TransactionRow.amount), else_=0)
            ), 0)
            future = func.coalesce(func.sum(
                case((TransactionRow.date > cutoff, TransactionRow.amount), else_=0)
            ), 0)
            row = self.session.execute(select(current, future).where(column)).one()
            return int(row[0] or 0), int(row[1] or 0)

        outgoing_current, outgoing_future = totals(TransactionRow.account_id == account_id)
        incoming_current, incoming_future = totals(
            TransactionRow.transfer_account_id == account_id
        )
        return {
            "balance": account.initial_balance + outgoing_current - incoming_current,
            "future": outgoing_future - incoming_future,
        }

    def account_balance(self, account_id: int, *, as_of: str | None = None) -> int:
        return self.account_balances(account_id, as_of=as_of)["balance"]

    def account_future_balance(self, account_id: int, *, as_of: str | None = None) -> int:
        return self.account_balances(account_id, as_of=as_of)["future"]

    # --- categorias ---

    def list_categories(self, kind: str | None = None) -> list[CategoryRow]:
        stmt = select(CategoryRow).order_by(CategoryRow.kind, CategoryRow.name)
        stmt = self._scope(stmt, CategoryRow)
        if kind:
            stmt = stmt.where(CategoryRow.kind == kind)
        return list(self.session.scalars(stmt))

    def get_category(self, category_id: int) -> CategoryRow:
        row = self.session.get(CategoryRow, category_id)
        if row is None:
            raise LookupError(f"categoria {category_id} não encontrada")
        return row

    def add_category(self, name: str, kind: str, parent_id: int | None = None) -> CategoryRow:
        if kind not in ("income", "expense"):
            raise ValueError(f"kind inválido: {kind!r}")
        row = CategoryRow(
            profile_id=self.profile_id, name=name, kind=kind, parent_id=parent_id
        )
        self.session.add(row)
        self.session.flush()
        return row

    def seed_default_categories(self, profile_id: int) -> None:
        """Insere as categorias padrão para um perfil recém-criado."""
        from money99.db.session import DEFAULT_CATEGORIES

        existing = self.session.scalar(
            select(func.count())
            .select_from(CategoryRow)
            .where(CategoryRow.profile_id == profile_id)
        ) or 0
        if existing:
            return
        for name, kind in DEFAULT_CATEGORIES:
            self.session.add(
                CategoryRow(profile_id=profile_id, name=name, kind=kind, parent_id=None)
            )
        self.session.flush()

    # --- transações ---

    def add_transaction(self, txn: Transaction) -> Transaction:
        txn.validate()
        self._check_refs(txn)
        row = TransactionRow(
            profile_id=self.profile_id,
            date=txn.date,
            description=txn.description,
            account_id=txn.account_id,
            amount=txn.amount,
            category_id=txn.category_id,
            transfer_account_id=txn.transfer_account_id,
            notes=txn.notes,
            reconciled=txn.reconciled,
            doc_issued=txn.doc_issued,
        )
        for split in txn.splits:
            row.splits.append(
                SplitRow(category_id=split.category_id, amount=split.amount)
            )
        self.session.add(row)
        self.session.flush()
        return self._to_transaction(row)

    def update_transaction(self, txn: Transaction) -> Transaction:
        if txn.id is None:
            raise ValueError("transação sem id")
        txn.validate()
        self._check_refs(txn)
        row = self.session.get(TransactionRow, txn.id)
        if row is None:
            raise LookupError(f"transação {txn.id} não encontrada")
        row.date = txn.date
        row.description = txn.description
        row.account_id = txn.account_id
        row.amount = txn.amount
        row.category_id = txn.category_id
        row.transfer_account_id = txn.transfer_account_id
        row.notes = txn.notes
        row.reconciled = txn.reconciled
        row.doc_issued = txn.doc_issued
        row.splits.clear()
        for split in txn.splits:
            row.splits.append(
                SplitRow(category_id=split.category_id, amount=split.amount)
            )
        return self._to_transaction(row)

    def delete_transaction(self, txn_id: int) -> None:
        row = self.session.get(TransactionRow, txn_id)
        if row is None:
            raise LookupError(f"transação {txn_id} não encontrada")
        self.session.delete(row)

    def get_transaction(self, txn_id: int) -> Transaction:
        row = self.session.get(TransactionRow, txn_id)
        if row is None:
            raise LookupError(f"transação {txn_id} não encontrada")
        return self._to_transaction(row)

    def list_transactions(
        self,
        *,
        account_id: int | None = None,
        category_id: int | None = None,
        start: str | None = None,
        end: str | None = None,
        reconciled: bool | None = None,
    ) -> list[Transaction]:
        stmt = select(TransactionRow).order_by(TransactionRow.date.desc(), TransactionRow.id.desc())
        stmt = self._scope(stmt, TransactionRow)
        if account_id is not None:
            stmt = stmt.where(
                (TransactionRow.account_id == account_id)
                | (TransactionRow.transfer_account_id == account_id)
            )
        if category_id is not None:
            stmt = stmt.where(
                (TransactionRow.category_id == category_id)
                | (TransactionRow.id.in_(select(SplitRow.transaction_id).where(
                    SplitRow.category_id == category_id
                )))
            )
        if start:
            stmt = stmt.where(TransactionRow.date >= start)
        if end:
            stmt = stmt.where(TransactionRow.date <= end)
        if reconciled is not None:
            stmt = stmt.where(TransactionRow.reconciled.is_(reconciled))
        return [self._to_transaction(row) for row in self.session.scalars(stmt)]

    def set_reconciled(self, txn_id: int, reconciled: bool) -> None:
        row = self.session.get(TransactionRow, txn_id)
        if row is None:
            raise LookupError(f"transação {txn_id} não encontrada")
        row.reconciled = reconciled

    def _check_refs(self, txn: Transaction) -> None:
        self.get_account(txn.account_id)
        if txn.transfer_account_id is not None:
            self.get_account(txn.transfer_account_id)
        if txn.category_id is not None:
            self.get_category(txn.category_id)
        for split in txn.splits:
            self.get_category(split.category_id)

    # --- orçamentos ---

    def set_budget(self, year: int, month: int, category_id: int, planned: int) -> None:
        stmt = select(BudgetRow).where(
            BudgetRow.year == year,
            BudgetRow.month == month,
            BudgetRow.category_id == category_id,
        )
        stmt = self._scope(stmt, BudgetRow)
        row = self.session.scalar(stmt)
        if row is None:
            self.session.add(
                BudgetRow(
                    profile_id=self.profile_id,
                    year=year,
                    month=month,
                    category_id=category_id,
                    planned=planned,
                )
            )
        else:
            row.planned = planned

    def list_budget(self, year: int, month: int) -> list[BudgetRow]:
        stmt = select(BudgetRow).where(BudgetRow.year == year, BudgetRow.month == month)
        stmt = self._scope(stmt, BudgetRow)
        return list(self.session.scalars(stmt))

    # --- usuários ---

    def count_users(self) -> int:
        return self.session.scalar(select(func.count()).select_from(UserRow)) or 0

    def get_user(self, username: str) -> UserRow | None:
        return self.session.scalar(
            select(UserRow).where(UserRow.username == username)
        )

    def add_user(self, username: str, password_hash: str, salt: str) -> UserRow:
        row = UserRow(username=username, password_hash=password_hash, salt=salt)
        self.session.add(row)
        self.session.flush()
        return row

    # --- serialização ---

    @staticmethod
    def _to_profile(row: ProfileRow) -> Profile:
        return Profile(
            id=row.id,
            name=row.name,
            kind=ProfileKind(row.kind or "personal"),
            cnpj=row.cnpj or "",
            legal_name=row.legal_name or "",
            trade_name=row.trade_name or "",
            opened_on=row.opened_on or "",
            annual_limit=row.annual_limit or 0,
            activity=row.activity or "servicos",
            active=bool(row.active),
        )

    @staticmethod
    def _to_account(row: AccountRow) -> Account:
        return Account(
            id=row.id,
            name=row.name,
            type=AccountType(row.type),
            initial_balance=row.initial_balance,
            active=row.active,
            credit_limit=row.credit_limit or 0,
        )

    @staticmethod
    def _to_transaction(row: TransactionRow) -> Transaction:
        return Transaction(
            id=row.id,
            date=row.date,
            description=row.description,
            account_id=row.account_id,
            amount=row.amount,
            category_id=row.category_id,
            transfer_account_id=row.transfer_account_id,
            splits=[Split(category_id=s.category_id, amount=s.amount) for s in row.splits],
            notes=row.notes,
            reconciled=row.reconciled,
            doc_issued=bool(row.doc_issued),
        )
