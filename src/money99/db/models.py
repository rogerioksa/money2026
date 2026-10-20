"""Models SQLAlchemy 2.0 (SQLite)."""

from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class AccountRow(Base):
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    type: Mapped[str] = mapped_column(String(20), default="bank")
    initial_balance: Mapped[int] = mapped_column(Integer, default=0)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class CategoryRow(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    kind: Mapped[str] = mapped_column(String(10))  # income | expense
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id"), nullable=True)


class TransactionRow(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
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

    splits: Mapped[list[SplitRow]] = relationship(
        back_populates="transaction", cascade="all, delete-orphan"
    )


class SplitRow(Base):
    __tablename__ = "splits"

    id: Mapped[int] = mapped_column(primary_key=True)
    transaction_id: Mapped[int] = mapped_column(ForeignKey("transactions.id"))
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"))
    amount: Mapped[int] = mapped_column(Integer)

    transaction: Mapped[TransactionRow] = relationship(back_populates="splits")


class BudgetRow(Base):
    __tablename__ = "budgets"

    id: Mapped[int] = mapped_column(primary_key=True)
    year: Mapped[int] = mapped_column(Integer)
    month: Mapped[int] = mapped_column(Integer)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"))
    planned: Mapped[int] = mapped_column(Integer)
