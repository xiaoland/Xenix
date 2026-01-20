"""Random Forest classification model with Pydantic parameter schemas"""

from typing import List, Literal
from pydantic import BaseModel, Field
from sklearn.ensemble import RandomForestClassifier

from .base import ClassificationModel


# Parameter schema for single training
class RandomForestClassificationParams(BaseModel):
    """Parameters for Random Forest Classification"""
    n_estimators: int = Field(default=100, description="Number of trees in forest", ge=1)
    criterion: Literal["gini", "entropy", "log_loss"] = Field(
        default="gini",
        description="Function to measure split quality"
    )
    max_depth: int | None = Field(default=None, description="Maximum depth of trees (None=unlimited)")
    min_samples_split: int = Field(default=2, description="Minimum samples to split node", ge=2)
    min_samples_leaf: int = Field(default=1, description="Minimum samples at leaf node", ge=1)
    max_features: int | float | Literal["sqrt", "log2"] | None = Field(
        default="sqrt",
        description="Number of features to consider for best split"
    )
    bootstrap: bool = Field(default=True, description="Whether to use bootstrap samples")
    random_state: int | None = Field(default=42, description="Random state for reproducibility")
    n_jobs: int | None = Field(default=None, description="Number of parallel jobs (-1=all cores)")


# Parameter grid schema for batch training (GridSearchCV)
class RandomForestClassificationParamGrid(BaseModel):
    """Parameter grid for Random Forest Classification GridSearchCV"""
    n_estimators: List[int] = Field(
        default=[50, 100, 200],
        description="Number of trees values to try"
    )
    max_depth: List[int | None] = Field(
        default=[5, 10, None],
        description="Maximum depth values to try"
    )
    min_samples_split: List[int] = Field(
        default=[2, 5, 10],
        description="Minimum samples to split values to try"
    )
    min_samples_leaf: List[int] = Field(
        default=[1, 2, 4],
        description="Minimum samples at leaf values to try"
    )


class RandomForestClassification(
    ClassificationModel[RandomForestClassifier, RandomForestClassificationParams, RandomForestClassificationParamGrid],
    param_grid=RandomForestClassificationParamGrid,
    model_param=RandomForestClassificationParams
):
    """
    Random Forest Classifier - ensemble of decision trees

    Uses type-safe Pydantic schemas for parameter validation.
    """

    def create_model(self, params: RandomForestClassificationParams) -> RandomForestClassifier:
        """
        Create Random Forest Classifier model instance

        Args:
            params: Validated Random Forest parameters

        Returns:
            Configured RandomForestClassifier model
        """
        return RandomForestClassifier(**params.model_dump(exclude_none=True))
