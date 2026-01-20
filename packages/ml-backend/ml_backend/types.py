"""Type definitions using Pydantic"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class BatchTrainInput(BaseModel):
    """Input for batch training (GridSearchCV auto-tuning)"""
    task_id: int
    train_data_path: str = Field(description="Path to training data (Excel/CSV)")
    model: str = Field(description="Model name (e.g., 'regression.ridge')")
    feature_columns: List[str] = Field(description="Feature column names")
    target_columns: List[str] = Field(description="Target column names (supports multi-target)")
    param_grid: Dict[str, List[Any]] = Field(description="Parameter grid for GridSearchCV")


class BatchTrainOutput(BaseModel):
    """Output from batch training (NO model_path - models saved in predict only)"""
    best_params: Dict[str, Any]
    metrics: Dict[str, Any]  # r2, mse, mae, cv_scores (can include lists)


class SingleTrainInput(BaseModel):
    """Input for single training (specific parameters)"""
    task_id: int
    train_data_path: str = Field(description="Path to training data (Excel/CSV)")
    model: str = Field(description="Model name (e.g., 'regression.ridge')")
    feature_columns: List[str] = Field(description="Feature column names")
    target_columns: List[str] = Field(description="Target column names (supports multi-target)")
    params: Dict[str, Any] = Field(description="Single parameter set")
    parent_task_id: Optional[int] = None


class SingleTrainOutput(BaseModel):
    """Output from single training (NO model_path - models saved in predict only)"""
    metrics: Dict[str, float]  # r2, mse, mae


class PredictFileInput(BaseModel):
    """Input for file-based prediction"""
    task_id: int
    model: str = Field(description="Model name (e.g., 'regression.ridge')")
    params: Dict[str, Any] = Field(description="Model parameters")
    train_data_path: str = Field(description="Path to training data")
    to_predict_data_path: str = Field(description="Path to prediction input data file")
    feature_columns: List[str] = Field(description="Feature column names")
    target_columns: List[str] = Field(description="Target column names")


class PredictFileOutput(BaseModel):
    """Output from file-based prediction"""
    fitted_model_path: str = Field(description="Relative path to saved model file")
    predicted_data_path: str = Field(description="Relative path to prediction results file")


class PredictInlineInput(BaseModel):
    """Input for inline prediction"""
    task_id: int
    model: str = Field(description="Model name (e.g., 'regression.ridge')")
    params: Dict[str, Any] = Field(description="Model parameters")
    train_data_path: str = Field(description="Path to training data")
    to_predict_data: List[Dict[str, Any]] = Field(description="Inline prediction data (JSON array)")
    feature_columns: List[str] = Field(description="Feature column names")
    target_columns: List[str] = Field(description="Target column names")


class PredictInlineOutput(BaseModel):
    """Output from inline prediction"""
    fitted_model_path: str = Field(description="Relative path to saved model file")
    predicted_data: List[Dict[str, Any]] = Field(description="Prediction results (inline JSON)")


class OperationRequest(BaseModel):
    """Generic operation request wrapper"""
    operation: str = Field(description="Operation type: batch-train, single-train, predict-file, predict-inline")
    data: Dict[str, Any] = Field(description="Operation-specific data")
