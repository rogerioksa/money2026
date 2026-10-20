"""Repository — mapeamento entre rows SQLAlchemy e objetos de domínio."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from money99.db.models import AccountRow, BudgetRow, CategoryRow, SplitRow, TransactionRow
from money99.domain.account import Account, AccountType
from money99.domain.transaction import Split, Transaction


class Repository:
    def __init__(self, session: Session):
        self.session = session

    # --- contas ---

    def list_accounts(self, *, active_only: bool = False) -> list[Account]:
        stmt = select(AccountRow).order_by(AccountRow.name)
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
            name=account.name,
            type=account.type.value,
            initial_balance=account.initial_balance,
            active=account.active,
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

    def account_balance(self, account_id: int) -> int:
        account = self.get_account(account_id)
        outgoing = self.session.scalar(
            select(func.coalesce(func.sum(TransactionRow.amount), 0)).where(
                TransactionRow.account_id == account_id
            )
        )
        incoming = self.session.scalar(
            select(func.coalesce(func.sum(-TransactionRow.amount), 0)).where(
                TransactionRow.transfer_account_id == account_id
            )
        )
        return account.initial_balance + outgoing + incoming

    # --- categorias ---

    def list_categories(self, kind: str | None = None) -> list[CategoryRow]:
        stmt = select(CategoryRow).order_by(CategoryRow.kind, CategoryRow.name)
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
        row = CategoryRow(name=name, kind=kind, parent_id=parent_id)
        self.session.add(row)
        self.session.flush()
        return row

    # --- transações ---

    def add_transaction(self, txn: Transaction) -> Transaction:
        txn.validate()
        self._check_refs(txn)
        row = TransactionRow(
            date=txn.date,
            description=txn.description,
            account_id=txn.account_id,
            amount=txn.amount,
            category_id=txn.category_id,
            transfer_account_id=txn.transfer_account_id,
            notes=txn.notes,
            reconciled=txn.reconciled,
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
        row = self.session.scalar(
            select(BudgetRow).where(
                BudgetRow.year == year,
                BudgetRow.month == month,
                BudgetRow.category_id == category_id,
            )
        )
        if row is None:
            self.session.add(
                BudgetRow(year=year, month=month, category_id=category_id, planned=planned)
            )
        else:
            row.planned = planned

    def list_budget(self, year: int, month: int) -> list[BudgetRow]:
        return list(
            self.session.scalars(
                select(BudgetRow).where(BudgetRow.year == year, BudgetRow.month == month)
            )
        )

    # --- serialização ---

    @staticmethod
    def _to_account(row: AccountRow) -> Account:
        return Account(
            id=row.id,
            name=row.name,
            type=AccountType(row.type),
            initial_balance=row.initial_balance,
            active=row.active,
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
        )
