# app/bot_handler.py
from fastapi import APIRouter, Request, Depends
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.utils.nlp import parse_message, parse_time_range
from app.utils.generate_pdf import generate_pdf_report
from tempfile import NamedTemporaryFile
from app.db import crud
import httpx
import os

telegram_webhook = APIRouter()

@telegram_webhook.post("/")
async def handle_telegram_webhook(req: Request, db: Session = Depends(get_db)):
    payload = await req.json()
    message = None
    if "message" in payload:
        message = payload["message"]
    elif "edited_message" in payload:
        message = payload["edited_message"]
    elif "callback_query" in payload:
        message = payload["callback_query"]["message"]
    else:
        print("Unhandled update type:", payload)
        return {"ok": True}

    chat_id = message["chat"]["id"]
    text = message.get("text", "")
    telegram_id = str(message["from"]["id"])
    name = message["from"].get("first_name", "User")
    BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

    user = crud.get_user(db, telegram_id)
    if not user:
        user = crud.create_user(db, telegram_id, name)

    if "export" in text.lower():
        start, end = parse_time_range(message)
        print(start, end)
        with NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            generate_pdf_report(user.id, db, tmp.name, start, end)
            try:
                with open(tmp.name, "rb") as f:
                    await client.post(
                        f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument",
                        files={"document": f},
                        data={"chat_id": chat_id, "caption": f"📄 Expense Report"}
                    )
            finally:
                os.remove(tmp.name)
        return {"ok": True}

    parsed = parse_message(text)
    reply = "Sorry, I couldn't understand that."
    print("-" * 40,"\n")
    print(f"Received message from {name} ({telegram_id}): {text}")
    print(f"Parsed message: {parsed}")
    print("-" * 40,"\n")

    

    # CREATE income/expense
    if parsed["type"] in ["income", "expense"] and parsed["action"] == "create":
        acc_name = parsed["account"]
        acc = crud.get_account_by_name(db, user.id, acc_name)
        if not acc:
            acc = crud.create_account(db, user.id, acc_name, 0.0)

        txn = crud.add_transaction(
            db, acc.id, parsed["amount"], parsed["description"], parsed["type"], parsed["date"] if parsed["date"] else None
        )

        reply = f"{parsed['type'].title()} of ₹{parsed['amount']} recorded in {acc_name}."
        if parsed["description"] != "Miscellaneous":
            reply += f"\nDescription: {parsed['description']}"
        if parsed["date"]:
            reply += f"\nDate: {parsed['date']}"

    # BALANCE
    elif parsed["type"] == "balance" and parsed["action"] == "read":
        accounts = crud.get_all_balances(db, user.id)
        summary = "\n".join([f"<b>{a.name}:</b> ₹{a.balance:.2f}" for a in accounts])
        reply = f"<b>Current balances:</b>\n\n{summary}"

    # BALANCE SET
    elif parsed["type"] == "balance_adjustment":
        acc_name = parsed["account"]
        acc = crud.get_account_by_name(db, user.id, acc_name)
        if not acc:
            acc = crud.create_account(db, user.id, acc_name, 0.0)

        diff = parsed["amount"] - acc.balance
        txn_type = "income" if diff > 0 else "expense"
        txn = crud.add_transaction(
            db, acc.id, abs(diff), "Balance correction", txn_type
        )
        reply = f"{acc_name} balance set to <b>₹{parsed['amount']}</b> <i>(adjusted by {txn_type} of ₹{abs(diff):.2f})</i>"

    # TRANSFER
    elif parsed["type"] == "transfer":
        from_acc_name = parsed.get("from_account", "Cash")
        to_acc_name = parsed.get("account", "Cash")
        amt = parsed["amount"]

        from_acc = crud.get_account_by_name(db, user.id, from_acc_name)
        to_acc = crud.get_account_by_name(db, user.id, to_acc_name)
        if not from_acc:
            from_acc = crud.create_account(db, user.id, from_acc_name, 0.0)
        if not to_acc:
            to_acc = crud.create_account(db, user.id, to_acc_name, 0.0)

        crud.add_transaction(db, from_acc.id, amt, parsed["description"], "expense")
        crud.add_transaction(db, to_acc.id, amt, parsed["description"], "income")

        reply = f"Transferred <b>₹{amt}</b> from <i>{from_acc_name}</i> to <i>{to_acc_name}</i>."

    elif parsed["action"] == "delete":
        acc_name = parsed.get("account", "Cash")
        acc = crud.get_account_by_name(db, user.id, acc_name)
        if acc:
            deleted_txn = crud.delete_last_transaction(db, acc.id)
            if deleted_txn:
                reply = f"Deleted last {deleted_txn.type} of <b>₹{deleted_txn.amount}</b> from {acc_name}."
            else:
                reply = f"No transactions found in {acc_name} to delete."
        else:
            reply = f"Account {acc_name} does not exist."

    # UPDATE last transaction
    elif parsed["action"] == "update":
        acc_name = parsed.get("account", "Cash")
        acc = crud.get_account_by_name(db, user.id, acc_name)
        if acc:
            updated_txn = crud.update_last_transaction(
                db, acc.id,
                new_amount=parsed["amount"],
                new_description=parsed["description"],
                new_type=parsed["type"],
                new_date=parsed["date"]
            )
            if updated_txn:
                reply = f"Updated last transaction in {acc_name} to ₹{parsed['amount']} ({parsed['description']})."
            else:
                reply = f"No transactions found in {acc_name} to update."
        else:
            reply = f"Account {acc_name} does not exist."

    elif parsed["action"] == "read" and parsed["type"] == "transaction":
        acc_name = parsed.get("account", "Cash")
        limit = parsed.get("limit", 5)

        acc = crud.get_account_by_name(db, user.id, acc_name)
        if not acc:
            reply = f"No account found with name {acc_name}."
        else:
            txns = crud.get_recent_transactions(db, acc.id, limit)
            if not txns:
                reply = f"No transactions found in {acc_name}."
            else:
                lines = [
                    f"• {txn.date.strftime('%d-%b')}: <b>₹{txn.amount:.2f}</b> - <i>{txn.type.title()} ({txn.description})</i>"
                    for txn in txns
                ]
                reply = f"<b>Last {len(txns)} transactions in {acc_name}:</b>\n\n" + "\n".join(lines)

    async with httpx.AsyncClient() as client:
        await client.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={"chat_id": chat_id, "text": reply, "parse_mode": "HTML"}
        )

    return {"ok": True}
