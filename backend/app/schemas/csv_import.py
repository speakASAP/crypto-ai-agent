from typing import Optional, List, Dict, Any
from pydantic import BaseModel


class CSVUploadResponse(BaseModel):
    success: bool
    message: str
    detected_exchange: Optional[str] = None
    preview_data: List[Dict[str, Any]] = []
    total_rows: int = 0
    aggregated_items: List[Dict[str, Any]] = []
    errors: List[str] = []
    # Portfolio impact analysis
    items_to_add: List[Dict[str, Any]] = []
    items_to_update: List[Dict[str, Any]] = []
    items_to_delete: List[Dict[str, Any]] = []


class CSVExecuteRequest(BaseModel):
    exchange: str
    column_mapping: Optional[Dict[str, str]] = None
