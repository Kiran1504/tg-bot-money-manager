# app/main.py
from fastapi import FastAPI
from app.bot_handler import telegram_webhook
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

# Add webhook route
app.include_router(telegram_webhook, prefix="/webhook")

@app.get("/")
def greet():
    return {"message": "Welcome to the Telegram Bot API!"}
