"""File I/O utilities"""

import os
import pandas as pd
from typing import Union, List, Dict, Any
from ..config import Config


def resolve_path(path: str) -> str:
    """
    Resolve a path relative to base path if not absolute

    Args:
        path: File path (absolute or relative)

    Returns:
        Absolute file path
    """
    if os.path.isabs(path):
        return path
    return os.path.join(Config.BASE_PATH, path)


def read_data(file_path: str) -> pd.DataFrame:
    """
    Read data from Excel or CSV file

    Args:
        file_path: Path to data file

    Returns:
        pandas DataFrame
    """
    resolved_path = resolve_path(file_path)

    if not os.path.exists(resolved_path):
        raise FileNotFoundError(f"Data file not found: {resolved_path}")

    # Determine file type by extension
    ext = os.path.splitext(resolved_path)[1].lower()

    if ext in ['.xlsx', '.xls']:
        return pd.read_excel(resolved_path)
    elif ext == '.csv':
        return pd.read_csv(resolved_path)
    else:
        raise ValueError(f"Unsupported file format: {ext}. Use .xlsx, .xls, or .csv")


def write_predictions(
    predictions: Union[pd.DataFrame, List[Dict[str, Any]]],
    output_path: str
) -> str:
    """
    Write predictions to file

    Args:
        predictions: Predictions data (DataFrame or list of dicts)
        output_path: Output file path

    Returns:
        Absolute path to output file
    """
    resolved_path = resolve_path(output_path)

    # Ensure directory exists
    os.makedirs(os.path.dirname(resolved_path), exist_ok=True)

    # Convert to DataFrame if needed
    if isinstance(predictions, list):
        df = pd.DataFrame(predictions)
    else:
        df = predictions

    # Determine output format by extension
    ext = os.path.splitext(resolved_path)[1].lower()

    if ext in ['.xlsx', '.xls']:
        df.to_excel(resolved_path, index=False)
    elif ext == '.csv':
        df.to_csv(resolved_path, index=False)
    else:
        # Default to CSV
        resolved_path = resolved_path + '.csv'
        df.to_csv(resolved_path, index=False)

    return resolved_path
