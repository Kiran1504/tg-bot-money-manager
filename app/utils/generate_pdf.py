from fpdf import FPDF
from dateutil.parser import parse as date_parse
from app.db import crud

class PDF(FPDF):
    def header(self):
        self.set_font("Arial", "B", 14)
        self.cell(0, 10, "Expense Report", border=False, ln=True, align="C")
        self.ln(3)

    def add_summary_line(self, total_expense, total_income):
        # Summary: One line, red and green values side by side, centered
        self.set_font("Arial", "B", 12)
        
        # Calculate starting position to center the content
        page_width = self.w - 2 * self.l_margin  # Available width
        content_width = 140  # Total width for both items
        start_x = self.l_margin + (page_width - content_width) / 2
        
        # Position cursor at calculated start position
        self.set_x(start_x)
        
        # Red for expense
        self.set_text_color(200, 0, 0)
        self.cell(70, 10, f"Total Expense: Rs.{round(total_expense, 2)}", ln=0, align="C")
        
        # Green for income
        self.set_text_color(0, 150, 0)
        self.cell(70, 10, f"Total Income: Rs.{round(total_income, 2)}", ln=1, align="C")
        
        self.set_text_color(0, 0, 0)  # Reset color
        self.ln(5)

    def add_account_table(self, title, transactions):
        self.set_font("Arial", "B", 11)
        self.cell(0, 10, title, ln=True)

        self.set_font("Arial", "B", 9)
        self.cell(30, 8, "Date", 1)
        self.cell(25, 8, "Spent", 1)
        self.cell(25, 8, "Credited", 1)
        self.cell(35, 8, "Balance", 1)
        self.cell(75, 8, "Description", 1)
        self.ln()

        self.set_font("Arial", "", 9)
        balance = 0
        for txn in transactions:
            date = txn.date.strftime("%Y-%m-%d")
            spent = txn.amount if txn.type == "expense" else ""
            credited = txn.amount if txn.type == "income" else ""
            balance += txn.amount if txn.type == "income" else -txn.amount
            desc = txn.description or ""

            self.cell(30, 8, str(date), 1)
            self.cell(25, 8, str(spent), 1)
            self.cell(25, 8, str(credited), 1)
            self.cell(35, 8, str(balance), 1)
            self.cell(75, 8, desc[:50], 1)
            self.ln()
        self.ln(5)

    def add_combined_sheet(self, all_transactions):
        self.set_font("Arial", "B", 12)
        self.cell(0, 10, "All Accounts Combined", ln=True)

        self.set_font("Arial", "B", 9)
        self.cell(30, 8, "Account", 1)
        self.cell(30, 8, "Date", 1)
        self.cell(25, 8, "Spent", 1)
        self.cell(25, 8, "Credited", 1)
        self.cell(80, 8, "Description", 1)
        self.ln()

        self.set_font("Arial", "", 9)
        for acc_name, txn in sorted(all_transactions, key=lambda x: x[1].date):
            date = txn.date.strftime("%Y-%m-%d")
            spent = txn.amount if txn.type == "expense" else ""
            credited = txn.amount if txn.type == "income" else ""
            desc = txn.description or ""

            self.cell(30, 8, acc_name, 1)
            self.cell(30, 8, date, 1)
            self.cell(25, 8, str(spent), 1)
            self.cell(25, 8, str(credited), 1)
            self.cell(80, 8, desc[:60], 1)
            self.ln()

def generate_pdf_report(user_id, db, output_path="expense_report.pdf", start=None, end=None):
    accounts = crud.get_all_balances(db, user_id)
    all_transactions = []

    pdf = PDF()
    pdf.add_page()

    total_expense, total_income = 0, 0

    # First, calculate totals by iterating through all transactions
    for acc in accounts:
        txns = crud.get_transactions_by_account(db, acc.id, start, end)
        if txns:
            all_transactions.extend([(acc.name, t) for t in txns])
            for t in txns:
                if not t.description.lower() == "balance correction":
                    if t.type == "income":
                        total_income += t.amount
                    else:
                        total_expense += t.amount

    # ✅ Add summary at the top, right after header
    pdf.add_summary_line(total_expense, total_income)

    # Then add account tables
    for acc in accounts:
        txns = crud.get_transactions_by_account(db, acc.id, start, end)
        if txns:
            pdf.add_account_table(acc.name, txns)

    # ✅ Add combined sheet (n+1)
    if all_transactions:
        pdf.add_page()
        pdf.add_combined_sheet(all_transactions)

    pdf.output(output_path)
    return output_path