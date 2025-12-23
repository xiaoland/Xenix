#!/usr/bin/env python3
"""
Scan ML models and extract ParamGrid schemas for database synchronization.
This script discovers all models in the business/ml directory and extracts
their ParamGrid JSON schemas for storage in the database.
"""
import json
import sys
import importlib
import inspect
from pathlib import Path
from typing import Dict, List, Any

# Add current directory to path
sys.path.append(str(Path(__file__).parent))

from base import import_model


def get_param_grid_class(model_class):
    """
    Extract the ParamGrid class from a model class's type hints.
    
    Args:
        model_class: The model class to inspect
        
    Returns:
        The ParamGrid class if found, None otherwise
    """
    # Get the class's __orig_bases__ to access Generic parameters
    if hasattr(model_class, '__orig_bases__'):
        for base in model_class.__orig_bases__:
            # Check if this is a Generic type with parameters
            if hasattr(base, '__args__') and len(base.__args__) >= 2:
                # Second type parameter is ParamGridType
                return base.__args__[1]
    return None


def scan_models_in_directory(category: str, directory: Path) -> List[Dict[str, Any]]:
    """
    Scan all model files in a directory and extract metadata.
    
    Args:
        category: Model category (e.g., 'regression', 'classification')
        directory: Path to the directory containing model files
        
    Returns:
        List of model metadata dictionaries
    """
    models = []
    
    # Iterate through all Python files in the directory
    for file_path in directory.glob('*.py'):
        # Skip __init__.py and base.py
        if file_path.name in ['__init__.py', 'base.py']:
            continue
            
        # Extract module name without .py extension
        module_name = file_path.stem
        full_model_name = f"{category}.{module_name}"
        
        try:
            # Import the model
            Model = import_model(full_model_name)
            
            # Get the ParamGrid class from type hints
            param_grid_class = get_param_grid_class(Model)
            
            if param_grid_class is None:
                print(f"Warning: Could not find ParamGrid class for {full_model_name}", file=sys.stderr)
                continue
            
            # Get JSON schema from the ParamGrid pydantic model
            param_grid_schema = param_grid_class.model_json_schema()
            
            # Generate a human-readable label
            # Convert snake_case to Title Case
            label = module_name.replace('_', ' ').title()
            
            # Create metadata entry
            model_metadata = {
                'category': category,
                'name': full_model_name,
                'label': label,
                'param_grid_schema': param_grid_schema
            }
            
            models.append(model_metadata)
            print(f"Scanned: {full_model_name}", file=sys.stderr)
            
        except Exception as e:
            print(f"Error scanning {full_model_name}: {str(e)}", file=sys.stderr)
            continue
    
    return models


def scan_all_models() -> List[Dict[str, Any]]:
    """
    Scan all model categories and return complete metadata.
    
    Returns:
        List of all model metadata dictionaries
    """
    all_models = []
    
    # Get the base ML directory
    ml_dir = Path(__file__).parent
    
    # Scan regression models
    regression_dir = ml_dir / 'regression'
    if regression_dir.exists():
        regression_models = scan_models_in_directory('regression', regression_dir)
        all_models.extend(regression_models)
    
    # Future: Add other categories
    # classification_dir = ml_dir / 'classification'
    # if classification_dir.exists():
    #     classification_models = scan_models_in_directory('classification', classification_dir)
    #     all_models.extend(classification_models)
    
    return all_models


def main():
    """
    Main function that scans models and outputs JSON to stdout.
    """
    try:
        models = scan_all_models()
        
        # Output as JSON to stdout
        result = {
            'success': True,
            'models': models,
            'count': len(models)
        }
        
        print(json.dumps(result, indent=2))
        
    except Exception as e:
        import traceback
        error_result = {
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }
        print(json.dumps(error_result, indent=2))
        sys.exit(1)


if __name__ == '__main__':
    main()
