from typing import Optional, Literal
from pydantic import BaseModel

Category = Literal["BL_COMPARISON", "SI_REQUEST", "INVOICE_QUERY", "GENERAL", "SPAM"]
Status = Literal["OK", "MISMATCH", "NEEDS_REVIEW"]
ReviewReason = Literal["wrong_doc_type", "missing_attachment", "unreadable", "missing_value"]

FIELDS = ["shipper", "consignee", "notify_party", "port_of_loading",
          "port_of_discharge", "container_count", "gross_weight_kg"]

class EmailResult(BaseModel):
    email_id: str
    category: Category
    confidence: float = 1.0
    status: Optional[Status] = None
    has_defect: Optional[bool] = None
    defect_fields: list[str] = []
    review_reason: Optional[ReviewReason] = None
    error: Optional[str] = None
