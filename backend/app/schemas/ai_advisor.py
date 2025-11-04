from typing import Optional, Dict, Any
from pydantic import BaseModel, ConfigDict


class AIPrediction(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    id: int
    symbol: str
    prediction_type: str
    predicted_price: float
    confidence_percent: float
    prediction_reasoning: Optional[str] = None
    model_name: str
    created_at: str
    is_verified: bool = False
    actual_price_at_target: Optional[float] = None
    accuracy_percent: Optional[float] = None


class PredictionResponse(BaseModel):
    """Response format for predictions"""
    symbol: str
    predictions: Dict[str, Dict[str, Any]]

    class Config:
        json_encoders = {
            float: lambda v: round(v, 8) if v is not None else None
        }


class NewsAnalysis(BaseModel):
    id: int
    symbol: str
    news_date: str
    title: str
    summary: Optional[str] = None
    sentiment_score: Optional[float] = None
    relevance_score: Optional[float] = None
    source: Optional[str] = None
    created_at: str


class ChartDataPoint(BaseModel):
    timestamp: int
    price: float
    date: str


class ChartData(BaseModel):
    symbol: str
    data: list[ChartDataPoint]


class PerformanceStats(BaseModel):
    total_predictions: int
    average_accuracy: float
    by_model: Dict[str, Dict[str, Any]]
    by_symbol: Dict[str, Dict[str, Any]]


class PredictionRequest(BaseModel):
    symbol: str
    force_regenerate: bool = False
