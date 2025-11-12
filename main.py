import os
from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional

from database import db, create_document, get_documents
from schemas import Transaction, Budget, Message

app = FastAPI(title="Personal Finance Assistant API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str
    history: Optional[List[Message]] = None


@app.get("/")
def root():
    return {"status": "ok", "service": "Personal Finance Assistant API"}


@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }

    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Configured"
            response["database_name"] = db.name if hasattr(db, 'name') else "✅ Connected"
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"

    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"

    return response


# --- Transactions ---
@app.post("/api/transactions")
def add_transaction(tx: Transaction):
    try:
        inserted_id = create_document("transaction", tx)
        return {"id": inserted_id, "ok": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/transactions")
def list_transactions(limit: int = 100):
    try:
        docs = get_documents("transaction", {}, limit)
        # Convert ObjectId to str
        for d in docs:
            if "_id" in d:
                d["id"] = str(d.pop("_id"))
        return {"items": docs}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# --- Budgets ---
@app.post("/api/budgets")
def add_budget(b: Budget):
    try:
        inserted_id = create_document("budget", b)
        return {"id": inserted_id, "ok": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/budgets")
def list_budgets(limit: int = 100):
    try:
        docs = get_documents("budget", {}, limit)
        for d in docs:
            if "_id" in d:
                d["id"] = str(d.pop("_id"))
        return {"items": docs}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# --- Simple rule-based Chatbot ---
def analyze_finances(transactions: List[dict], budgets: List[dict]):
    # Basic insights without external AI dependencies
    total_income = sum(t.get("amount", 0) for t in transactions if t.get("amount", 0) > 0)
    total_expense = -sum(min(t.get("amount", 0), 0) for t in transactions)
    net = total_income - total_expense

    by_category = {}
    for t in transactions:
        cat = t.get("category", "uncategorized").lower()
        by_category[cat] = by_category.get(cat, 0) + t.get("amount", 0)

    overs = []
    for b in budgets:
        spent = -sum(v for k, v in by_category.items() if k == b.get("category", "").lower() and v < 0)
        if spent > b.get("amount", 0):
            overs.append({"category": b["category"], "spent": spent, "budget": b["amount"]})

    tips = []
    if total_expense > 0 and total_income > 0:
        savings_rate = max((total_income - total_expense) / total_income, 0)
        tips.append(f"Your savings rate is {savings_rate:.0%}. Aim for 20%+ where possible.")
    if overs:
        for o in overs:
            tips.append(f"You're over budget in {o['category']} by ${o['spent'] - o['budget']:.2f}. Consider reducing spend or increasing the budget.")
    top_exp_cat = None
    max_spend = 0
    for cat, val in by_category.items():
        if val < 0 and -val > max_spend:
            max_spend = -val
            top_exp_cat = cat
    if top_exp_cat:
        tips.append(f"Largest expense category is {top_exp_cat} at ${max_spend:.2f}. See if there are ways to trim this.")

    return {
        "summary": {
            "income": total_income,
            "expense": total_expense,
            "net": net
        },
        "overs": overs,
        "tips": tips
    }


@app.post("/api/chat")
def chat(req: ChatRequest):
    # Pull latest data to ground responses
    txs = get_documents("transaction", {}, 500)
    buds = get_documents("budget", {}, 100)
    for d in txs:
        if "_id" in d:
            d.pop("_id")
    for d in buds:
        if "_id" in d:
            d.pop("_id")

    insights = analyze_finances(txs, buds)

    user_q = req.message.lower()
    reply_parts: List[str] = []

    if any(k in user_q for k in ["summary", "overview", "how am i doing", "net"]):
        s = insights["summary"]
        reply_parts.append(
            f"Here's your overview: Income ${s['income']:.2f}, Expenses ${s['expense']:.2f}, Net ${s['net']:.2f}."
        )
    if any(k in user_q for k in ["budget", "over budget", "overspent", "overspending"]):
        if insights["overs"]:
            for o in insights["overs"]:
                reply_parts.append(
                    f"Over budget in {o['category']}: spent ${o['spent']:.2f} vs budget ${o['budget']:.2f}."
                )
        else:
            reply_parts.append("You're within all budgets based on current data.")
    if any(k in user_q for k in ["tip", "save", "improve", "advice"]):
        reply_parts += insights["tips"] or ["Keep tracking your spending to build trends."]

    if not reply_parts:
        # Default helpful response
        s = insights["summary"]
        reply_parts.append(
            "I can summarize your finances, track budgets, and give tips. "
            f"Currently: income ${s['income']:.2f}, expenses ${s['expense']:.2f}. Ask 'show budget' or 'give tips'."
        )

    return {
        "reply": " ".join(reply_parts),
        "insights": insights
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
