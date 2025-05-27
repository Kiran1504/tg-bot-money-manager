import re
from typing import Dict
from datetime import datetime
import dateparser

def extract_date(text: str) -> str:
    text_clean = text.lower().replace(",", "")
    date_phrases = ["today", "yesterday", "a week ago"]
    date_match = re.search(r"on\s+(\d{1,2}(?:st|nd|rd|th)?(?:\s+\w+)?|\w+\s+\d{1,2})", text_clean)
    if date_match:
        date_phrase = date_match.group(1)
    else:
        for phrase in date_phrases:
            if phrase in text_clean:
                date_phrase = phrase
                break
        else:
            return ""
    parsed_date = dateparser.parse(date_phrase)
    if parsed_date:
        return parsed_date.strftime("%Y-%m-%d")
    return ""

def parse_message(text: str) -> Dict:
    text = text.lower().strip()
    result = {
        "type": "unknown",
        "action": "create",
        "amount": 0.0,
        "account": "Cash",
        "description": "Miscellaneous",
        "date": None
    }

    result["date"] = extract_date(text)

    # CRUD commands
    if "balance" in text and "of" not in text:
        result["type"] = "balance"
        result["action"] = "read"
        return result
    if "delete" in text:
        result["action"] = "delete"
    elif "update" in text:
        result["action"] = "update"

    # Balance adjustment
    balance_set_match = re.search(r"(\w+)\s*(?:is|=)\s*(-?\d+(?:\.\d{1,2})?)", text)
    if balance_set_match:
        print("Balance set match found:", balance_set_match.groups())
        account = balance_set_match.group(1).capitalize()
        amount = float(balance_set_match.group(2))
        result.update({
            "type": "balance_adjustment",
            "account": account,
            "amount": amount,
            "description": f"Set {account} balance to {amount}"
        })
        return result

    # Transfer detection
    if any(word in text for word in ["transfer", "moved", "move", "shifted"]):
        result["type"] = "transfer"
        from_match = re.search(r"from\s+(\w+)", text)
        to_match = re.search(r"to\s+(\w+)", text)
        if from_match:
            result["from_account"] = from_match.group(1).capitalize()
        if to_match:
            result["account"] = to_match.group(1).capitalize()
        amt_match = re.search(r"(\d+(?:,\d{3})*(?:\.\d{1,2})?)", text)
        if amt_match:
            result["amount"] = float(amt_match.group(1).replace(',', ''))
        result["description"] = f"Transfer from {result.get('from_account', '')} to {result.get('account', '')}"
        return result

    # Income with 'in' or 'to' account
    if any(word in text for word in ["received", "got", "credited", "income", "earned", "added", "from"]):
        result["type"] = "income"
        amt_match = re.search(r"(\d+(?:,\d{3})*(?:\.\d{1,2})?)", text)
        if amt_match:
            result["amount"] = float(amt_match.group(1).replace(',', ''))
        acc_match = re.search(r"(?:in|to|into)\s+(\w+)", text)
        if acc_match:
            result["account"] = acc_match.group(1).capitalize()
        else:
            result["account"] = "Cash"

    # Expense keywords
    elif any(word in text for word in ["spent", "paid", "gave", "bought", "sent", "debited", "purchased", "to"]):
        result["type"] = "expense"
        amt_match = re.search(r"(\d+(?:,\d{3})*(?:\.\d{1,2})?)", text)
        if amt_match:
            result["amount"] = float(amt_match.group(1).replace(',', ''))
        acc_match = re.search(r"(?:from|via|using|in)\s+(\w+)", text)
        if acc_match:
            result["account"] = acc_match.group(1).capitalize()

    # Fallback amount extraction if still not set
    if result["amount"] == 0.0:
        amt_match = re.search(r"(\d+(?:,\d{3})*(?:\.\d{1,2})?)", text)
        if amt_match:
            result["amount"] = float(amt_match.group(1).replace(',', ''))

    # Description extraction
    desc_match = re.search(r"(?:on|for|as|for buying)\s+([\w\s]+?)(?=$|from|using|via|in)", text)
    if desc_match:
        result["description"] = desc_match.group(1).strip().capitalize()
    else:
        tail_match = re.search(r"(?:spent|paid|received|got|bought|sent|earned|added)\s+\d+(?:\.\d+)?\s+(?:on|for)\s+(.+)", text)
        if tail_match:
            result["description"] = tail_match.group(1).strip().capitalize()

    return result

# Test cases
test_cases = [
    "cash is 0",
    "cash = 0",
    "hdfc = 2000",
    "sent 500 from cash",
    "got 1000 from gpay",
    "spent 500 on groceries",
    "received 500 from client on 25 May",
    "earned 1000 from freelancing yesterday",
    "added 250 to savings a week ago",
    "delete last expense",
    "balance of card",
    "update last income to 600",
    "transfer 1500 from cash to sb",
    "moved 2000 from hdfc to icici"
]

# # Show results
# for msg in test_cases:
#     print(f">>> {msg}")
#     print(parse_message(msg), "\n")
