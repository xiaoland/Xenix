"""ML operations"""

from .batch_train import batch_train
from .single_train import single_train
from .predict import predict

__all__ = ["batch_train", "single_train", "predict"]
