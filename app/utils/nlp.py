from google import genai
from typing import Optional, Literal
from dotenv import load_dotenv
from pydantic import BaseModel
from datetime import datetime 
import json
import os
import pytz

load_dotenv()
india = pytz.timezone("Asia/Kolkata")

class ExpenseParsed(BaseModel):
    type: Literal["income", "expense", "transfer", "balance", "balance_adjustment", "transaction","unknown"]
    action: Literal["create", "update", "delete", "read"]
    amount: float
    account: str = "Cash"
    description: str = "Miscellaneous"
    date: Optional[str] = None
    from_account: Optional[str] = None
    limit: Optional[int] = None 

class TimeRange(BaseModel):
    start: Optional[datetime] = None
    end: Optional[datetime] = None

class UpdateFields(BaseModel):
    amount: Optional[float] = None
    description: Optional[str] = None
    type: Optional[Literal["income", "expense"]] = None
    date: Optional[datetime] = None  # ISO format


# Set up Gemini
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") 
MODEL= os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

client = genai.Client(api_key=GEMINI_API_KEY)

def parse_message(text: str) -> dict:
    prompt = f"""
You are a finance assistant bot. Extract structured data in the following JSON format:

{{
  "type": "income | expense | transfer | balance | balance_adjustment | transaction | unknown",
  "action": "create | update | delete | read",
  "amount": float (₹),
  "account": string (e.g., 'Cash', 'HDFC', 'SBI'),
  "description": string (e.g., 'Groceries', 'Salary'),
  "date": YYYY-MM-DD or null,
  "from_account": string (only for transfers),
  "limit": int (optional, for transaction history requests)
}}

Instructions:
1. Types:
- "income": Money received (e.g., salary, gifts).
- "expense": Money spent (e.g., groceries, bills).
- "transfer": **ONLY WHEN `TRANSFER` or `t:` IS MENTIONED in the input text** (e.g., transfer 200 from Cash to HDFC,t: 1111 from HDFC to SBI, t: ATM withdrawal).
- "balance": Request for current balance of an account.
- "balance_adjustment": Directly setting a value to an account (e.g., "Cash is 1000", "HDFC = 0").
- "transaction": for displaying transaction history. (action="read")
- "unknown": If the type cannot be determined.
2. Actions:
- "create": Adding a new income or expense.
- "update": Modifying an existing income or expense.
- "delete": Removing an income or expense.
- "read": Fetching details about the account.
3. "account" is Compulsory for all types except "balance".
4. "from_account" is only required for transfers.

Defaults:
- "account": "Cash"
- "description": "Miscellaneous"
- "date": None
- "amount": 0.0
- "limit": None
- "from_account": None
"from_account" only appears for transfers.

Parse this: "{text}"
"""

    try:
        response = client.models.generate_content(
            model=MODEL,
            contents=[prompt],
            config={
                "response_mime_type": "application/json",
                "response_schema": ExpenseParsed
            }
        )

        return json.loads(response.text)

    except Exception as e:
        print("Gemini parsing error:", e)
        return ExpenseParsed(type="unknown", action="create", amount=0.0).dict()


def parse_time_range(msg: str):
    prompt = f"""
Extract the start and end date from the following message. 
Today's date is {datetime.now(pytz.timezone("Asia/Kolkata")).strftime('%Y-%m-%d')}.
The format should be:
{{
start: YYYY-MM-DD,
end: YYYY-MM-DD
}}
Message: "{msg}"
Reply only with start and end in the format:
start: YYYY-MM-DD
end: YYYY-MM-DD
"""
    try:
        response = client.models.generate_content(
            model=MODEL,
            contents=[prompt],
            config={
                "response_mime_type": "application/json",
                "response_schema": TimeRange
            }
        )
        print("Raw Response:", response.text)
        res = json.loads(response.text)
        res['start'] = res['start'].replace("_", "T") if res['start'] else None
        res['end'] = res['end'].replace("_", "T") if res['end'] else None
        return res
    except Exception as e:
        print("Gemini time range parsing error:", e)
        return {"start": None, "end": None}


def extract_update_fields_from_msg(msg: str) -> dict:
    prompt = f"""
You are a finance assistant. Extract ONLY the fields that the user intends to update from the message below.

The response must be in JSON format like:
{{
  "amount": float or null,
  "description": string or null,
  "type": "income" | "expense" or null,
  "date": "YYYY-MM-DD" or null
}}

If a field is not meant to be updated, return null for that field.

Message: "{msg}"
"""

    try:
        response = client.models.generate_content(
            model=MODEL,
            contents=[prompt],
            config={
                "response_mime_type": "application/json",
                "response_schema": UpdateFields
            }
        )
        return json.loads(response.text)
    except Exception as e:
        print("Gemini update field extraction error:", e)
        return {}

# Test cases
test_cases = [
    # "cash is 0",
    # "cash = 0",
    # "hdfc = 2000",
    # "sent 500 from cash",
    # "got 1000 from grandma",
    # "200.459 on ram from hdfc",
    # "10,200.459 salary in hdfc",
    # "spent 500 on groceries",
    # "received 500 from client on 25 May",
    # "earned 1000 from freelancing yesterday",
    # "added 250 to savings a week ago",
    # "delete last expense",
    # "balance of card",
    # "update last income to 600",
    # "transfer 1500 from cash to sb",
    # "moved 2000 from hdfc to icici",
    "give me the last 5 transactions from hdfc",
    "show me the last 15 transactions from hdfc",
    "last 10 transactions",
]

# print(parse_time_range("export last week"))
# print(parse_time_range("export"))
# print(type(parse_time_range("export this month")['start']))

# for message in test_cases:
# parsed = extract_update_fields_from_msg("Update date of last transaction to 5th June 25")
# print(f"Message: Update date of last transaction to 5th June 25\nParsed: {parsed}\n")
# print(type(parsed))
