from typing import Optional, Literal
from pydantic import BaseModel

Category = Literal[
    "document_comparison", "new_si_request",
    "invoice_query", "general_message", "spam",
]

# The 7 fields to compare (from the brief)
FIELDS = [
    "shipper", "consignee", "notify_party",
    "port_of_loading", "port_of_discharge",
    "container_count", "gross_weight_kg",
]


class FieldCheck(BaseModel):
    field: str
    si_value: Optional[str] = None
    bl_value: Optional[str] = None
    match: bool


class EmailResult(BaseModel):
    email_id: str
    category: Category
    confidence: float = 1.0
    needs_review: bool = False          # human-in-the-loop flag
    review_reason: Optional[str] = None
    mismatch_found: Optional[bool] = None   # only for document_comparison
    fields: list[FieldCheck] = []
    error: Optional[str] = None
