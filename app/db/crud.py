from sqlalchemy.orm import Session
from app.db import models
from datetime import datetime, timedelta
from dateutil import parser
import pytz

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
        date=date if date else datetime.now(pytz.timezone("Asia/Kolkata"))
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

def delete_last_transaction(db: Session, account_id: int):
    txn = db.query(models.Transaction).filter(
        models.Transaction.account_id == account_id
    ).order_by(models.Transaction.date.desc()).first()

    if txn:
        # Reverse balance
        account = db.query(models.Account).filter(models.Account.id == account_id).first()
        if txn.type == 'expense':
            account.balance += txn.amount
        elif txn.type == 'income':
            account.balance -= txn.amount

        db.delete(txn)
        db.commit()
        return txn
    return None

def update_last_transaction(
    db: Session, account_id: int, new_amount: float, new_description: str = None,
    new_type: str = None, new_date: datetime = None
):
    txn = db.query(models.Transaction).filter(
        models.Transaction.account_id == account_id
    ).order_by(models.Transaction.date.desc()).first()

    if not txn:
        return None

    account = db.query(models.Account).filter(models.Account.id == account_id).first()

    # Reverse old transaction impact
    if txn.type == 'expense':
        account.balance += txn.amount
    elif txn.type == 'income':
        account.balance -= txn.amount

    # Apply new values
    txn.amount = new_amount
    txn.description = new_description or txn.description
    txn.type = new_type or txn.type
    txn.date = new_date or txn.date

    # Apply new impact
    if txn.type == 'expense':
        account.balance -= txn.amount
    elif txn.type == 'income':
        account.balance += txn.amount

    db.commit()
    db.refresh(txn)
    return txn

def get_recent_transactions(db: Session, account_id: int, limit: int = 5):
    return db.query(models.Transaction).filter(
        models.Transaction.account_id == account_id
    ).order_by(models.Transaction.date.desc()).limit(limit).all()

def get_transactions_by_account(db: Session, account_id: int, start_date: str = None, end_date: str = None):
    query = db.query(models.Transaction).filter(models.Transaction.account_id == account_id)
    india_tz = pytz.timezone("Asia/Kolkata")
    utc_tz = pytz.utc

    if start_date:
        start_date = parser.isoparse(start_date).astimezone(india_tz)
    else:
        start_date = datetime.now(india_tz) - timedelta(days=30)  # Default: last 30 days

    # Convert end_date from UTC to IST
    if end_date:
        end_date = parser.isoparse(end_date).astimezone(india_tz)
    else:
        end_date = datetime.now(india_tz)

    query = query.filter(models.Transaction.date >= start_date)
    query = query.filter(models.Transaction.date <= end_date)

    return query.order_by(models.Transaction.date.desc()).all()