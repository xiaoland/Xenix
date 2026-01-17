"""Type definitions using Pydantic"""

from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field


class BatchTrainInput(BaseModel):
    """Input for batch training (GridSearchCV auto-tuning)"""
    task_id: int
    input_file: str = Field(description="Path to training data (Excel/CSV)")
    model: str = Field(description="Model name (e.g., 'regression.ridge')")
    feature_columns: List[str] = Field(description="Feature column names")
    target_column: str = Field(description="Target column name")
    param_grid: Dict[str, List[Any]] = Field(description="Parameter grid for GridSearchCV")


class BatchTrainOutput(BaseModel):
    """Output from batch training"""
    task_id: int
    best_params: Dict[str, Any]
    metrics: Dict[str, Any]  # r2, mse, mae, cv_scores (can include lists)
    model_path: str
    timestamp: str


class SingleTrainInput(BaseModel):
    """Input for single training (specific parameters)"""
    task_id: int
    input_file: str
    model: str
    feature_columns: List[str]
    target_column: str
    params: Dict[str, Any] = Field(description="Single parameter set")
    parent_task_id: Optional[int] = None


class SingleTrainOutput(BaseModel):
    """Output from single training"""
    task_id: int
    metrics: Dict[str, float]  # r2, mse, mae
    model_path: str
    timestamp: str


class PredictInput(BaseModel):
    """Input for prediction"""
    task_id: int
    train_data: str = Field(description="Path to training data")
    predict_data: Union[str, List[Dict[str, Any]]] = Field(
        description="Path to prediction data OR inline JSON array"
    )
    output_path: str = Field(description="Where to save predictions")
    model: str
    params: Dict[str, Any]
    feature_columns: List[str]
    target_column: str


class PredictOutput(BaseModel):
    """Output from prediction"""
    task_id: int
    predictions_path: str
    record_count: int
    metrics: Optional[Dict[str, float]] = None  # Optional if test data available
    timestamp: str


class OperationRequest(BaseModel):
    """Generic operation request wrapper"""
    operation: str = Field(description="Operation type: batch-train, single-train, predict")
    data: Dict[str, Any] = Field(description="Operation-specific data")
