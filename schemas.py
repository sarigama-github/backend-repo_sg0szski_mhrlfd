"""
Database Schemas for Personal Finance Assistant

Each Pydantic model maps to a MongoDB collection (lowercased class name).
"""

from pydantic import BaseModel, Field
from typing import Optional, Literal

class Transaction(BaseModel):
    """
    Personal finance transactions
    Collection: "transaction"
    """
    amount: float = Field(..., description="Transaction amount (positive for income, negative for expense)")
    category: str = Field(..., description="Category (e.g., groceries, rent, salary)")
    date: str = Field(..., description="ISO date string, e.g., 2025-01-31")
    notes: Optional[str] = Field(None, description="Optional notes")
    account: Optional[str] = Field(None, description="Account name or source")

class Budget(BaseModel):
    """
    Category budgets
    Collection: "budget"
    """
    category: str = Field(..., description="Budget category")
    amount: float = Field(..., ge=0, description="Budgeted amount for the period")
    period: Literal["monthly", "weekly"] = Field("monthly", description="Budget period")

class Message(BaseModel):
    """
    Chat messages (optional persistence)
    Collection: "message"
    """
    role: Literal["user", "assistant"] = Field(...)
    content: str = Field(...)
    context: Optional[str] = Field(None)
