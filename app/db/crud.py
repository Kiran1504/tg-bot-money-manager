from sqlalchemy.orm import Session
from app.db import models
from datetime import datetime

def create_user(db: Session, telegram_id: int, name: str):
    user = models.User(telegram_id=telegram_id, name=name)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

def get_user(db: Session, telegram_id: int):
    return db.query(models.User).filter(models.User.telegram_id == telegram_id).first()

def create_account(db: Session, user_id: int, account_name: str, initial_balance: float):
    account = models.Account(user_id=user_id, name=account_name, balance=initial_balance)
    db.add(account)
    db.commit()
    db.refresh(account)
    return account

def get_account_by_name(db: Session, user_id: int, account_name: str):
    return db.query(models.Account).filter(
        models.Account.user_id == user_id,
        models.Account.name.ilike(account_name)
    ).first()

def add_transaction(db: Session, account_id: int, amount: float, description: str, type: str, date: datetime =  datetime.utcnow()):
    transaction = models.Transaction(
        account_id=account_id,
        amount=amount,
        description=description,
        type=type,
        date=date
    )
    db.add(transaction)

    # Update balance
    account = db.query(models.Account).filter(models.Account.id == account_id).first()
    if type == 'expense':
        account.balance -= amount
    elif type == 'income':
        account.balance += amount

    db.commit()
    db.refresh(transaction)
    return transaction

def get_all_balances(db: Session, user_id: int):
    return db.query(models.Account).filter(models.Account.user_id == user_id).all()
