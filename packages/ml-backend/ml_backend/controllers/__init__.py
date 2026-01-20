"""ML operations"""

from .batch_train import batch_train
from .single_train import single_train
from .predict_file import predict_file
from .predict_inline import predict_inline

__all__ = ["batch_train", "single_train", "predict_file", "predict_inline"]
