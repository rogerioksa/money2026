"""Models SQLAlchemy 2.0 (SQLite)."""

from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class ProfileRow(Base):
    __tablename__ = "profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    kind: Mapped[str] = mapped_column(String(20), default="personal")  # personal | business
    cnpj: Mapped[str] = mapped_column(String(20), default="")
    legal_name: Mapped[str] = mapped_column(String(200), default="")  # razão social
    trade_name: Mapped[str] = mapped_column(String(200), default="")  # nome fantasia
    opened_on: Mapped[str] = mapped_column(String(10), default="")  # ISO
    annual_limit: Mapped[int] = mapped_column(Integer, default=8100000)  # R$ 81.000,00
    activity: Mapped[str] = mapped_column(String(20), default="servicos")  # MEI
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class AccountRow(Base):
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int | None] = mapped_column(ForeignKey("profiles.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(120))
    type: Mapped[str] = mapped_column(String(20), default="bank")
    initial_balance: Mapped[int] = mapped_column(Integer, default=0)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    credit_limit: Mapped[int] = mapped_column(Integer, default=0)


class CategoryRow(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int | None] = mapped_column(ForeignKey("profiles.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(120))
    kind: Mapped[str] = mapped_column(String(10))  # income | expense
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id"), nullable=True)


class TransactionRow(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int | None] = mapped_column(ForeignKey("profiles.id"), nullable=True)
    date: Mapped[str] = mapped_column(String(10))  # ISO AAAA-MM-DD
    description: Mapped[str] = mapped_column(String(240), default="")
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"))
    amount: Mapped[int] = mapped_column(Integer)  # centavos, assinado
    category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id"), nullable=True)
    transfer_account_id: Mapped[int | None] = mapped_column(
        ForeignKey("accounts.id"), nullable=True
    )
    notes: Mapped[str] = mapped_column(Text, default="")
    reconciled: Mapped[bool] = mapped_column(Boolean, default=False)
    doc_issued: Mapped[bool] = mapped_column(Boolean, default=False)  # MEI: NF emitida
    cost_center_id: Mapped[int | None] = mapped_column(ForeignKey("cost_centers.id"), nullable=True)

    splits: Mapped[list[SplitRow]] = relationship(
        back_populates="transaction", cascade="all, delete-orphan"
    )


class SplitRow(Base):
    __tablename__ = "splits"

    id: Mapped[int] = mapped_column(primary_key=True)
    transaction_id: Mapped[int] = mapped_column(ForeignKey("transactions.id"))
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"))
    amount: Mapped[int] = mapped_column(Integer)
    cost_center_id: Mapped[int | None] = mapped_column(ForeignKey("cost_centers.id"), nullable=True)

    transaction: Mapped[TransactionRow] = relationship(back_populates="splits")


class FavorecidoRow(Base):
    __tablename__ = "favorecidos"

    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int | None] = mapped_column(ForeignKey("profiles.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(160))
    kind: Mapped[str] = mapped_column(String(12), default="supplier")
    document: Mapped[str] = mapped_column(String(20), default="")
    phone: Mapped[str] = mapped_column(String(40), default="")
    email: Mapped[str] = mapped_column(String(160), default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class TitleRow(Base):
    __tablename__ = "titles"

    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int | None] = mapped_column(ForeignKey("profiles.id"), nullable=True)
    type: Mapped[str] = mapped_column(String(12), default="payable")  # receivable | payable
    description: Mapped[str] = mapped_column(String(240), default="")
    amount: Mapped[int] = mapped_column(Integer)  # centavos
    due_date: Mapped[str] = mapped_column(String(10))  # ISO
    status: Mapped[str] = mapped_column(String(12), default="open")  # open | paid | cancelled
    account_id: Mapped[int | None] = mapped_column(ForeignKey("accounts.id"), nullable=True)
    category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id"), nullable=True)
    cost_center_id: Mapped[int | None] = mapped_column(
        ForeignKey("cost_centers.id"), nullable=True
    )
    favorecido: Mapped[str] = mapped_column(String(160), default="")
    favorecido_id: Mapped[int | None] = mapped_column(ForeignKey("favorecidos.id"), nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    paid_date: Mapped[str] = mapped_column(String(10), default="")
    paid_amount: Mapped[int] = mapped_column(Integer, default=0)


class CostCenterRow(Base):
    __tablename__ = "cost_centers"

    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int | None] = mapped_column(ForeignKey("profiles.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(120))
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class BudgetRow(Base):
    __tablename__ = "budgets"

    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int | None] = mapped_column(ForeignKey("profiles.id"), nullable=True)
    year: Mapped[int] = mapped_column(Integer)
    month: Mapped[int] = mapped_column(Integer)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"))
    planned: Mapped[int] = mapped_column(Integer)


class AnnualBudgetRow(Base):
    __tablename__ = "annual_budgets"

    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int | None] = mapped_column(ForeignKey("profiles.id"), nullable=True)
    year: Mapped[int] = mapped_column(Integer)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"))
    annual_planned: Mapped[int] = mapped_column(Integer, default=0)


class UserRow(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(120), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    salt: Mapped[str] = mapped_column(String(64))
