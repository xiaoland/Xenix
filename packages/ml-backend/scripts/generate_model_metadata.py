#!/usr/bin/env python3
"""
Generate model_metadata.json for database migration

This script introspects all model classes and extracts their parameter schemas,
generating a JSON file that can be used for database migration of the model_metadata table.
"""

import json
import sys
from pathlib import Path
from typing import Any, Dict, List
from pydantic import BaseModel

# Add ml_backend to path
sys.path.insert(0, str(Path(__file__).parent))

from ml_backend.services.regression import REGRESSION_MODELS
from ml_backend.services.classification import CLASSIFICATION_MODELS


def pydantic_schema_to_db_schema(pydantic_schema: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert Pydantic JSON schema to database-friendly format

    Args:
        pydantic_schema: Pydantic model JSON schema

    Returns:
        Simplified schema for database storage
    """
    properties = pydantic_schema.get("properties", {})
    required = set(pydantic_schema.get("required", []))

    fields = {}
    for field_name, field_info in properties.items():
        field_type = field_info.get("type", "any")
        field_desc = field_info.get("description", "")
        field_default = field_info.get("default")

        # Handle array types (for param grids)
        if field_type == "array":
            items = field_info.get("items", {})
            item_type = items.get("type", "any")
            field_type = f"array<{item_type}>"

        # Handle enums/literals
        if "enum" in field_info:
            enum_values = field_info["enum"]
            field_type = f"enum({','.join(map(str, enum_values))})"

        fields[field_name] = {
            "type": field_type,
            "description": field_desc,
            "required": field_name in required,
            "default": field_default
        }

    return fields


def generate_model_metadata() -> List[Dict[str, Any]]:
    """
    Generate metadata for all models

    Returns:
        List of model metadata dictionaries
    """
    metadata = []

    # Combine all models
    all_models = {**REGRESSION_MODELS, **CLASSIFICATION_MODELS}

    for model_name, model_class in all_models.items():
        try:
            # Instantiate model to access schemas
            model_instance = model_class()

            # Determine model type (regression or classification)
            model_type = "regression" if model_name.startswith("regression.") else "classification"

            # Get parameter and param grid schemas
            param_schema = None
            param_grid_schema = None

            if hasattr(model_class, "__modelparam__"):
                param_model = model_class.__modelparam__
                param_schema = pydantic_schema_to_db_schema(param_model.model_json_schema())

            if hasattr(model_class, "__paramgrid__"):
                param_grid_model = model_class.__paramgrid__
                param_grid_schema = pydantic_schema_to_db_schema(param_grid_model.model_json_schema())

            # Get default values
            default_params = {}
            default_param_grid = {}

            try:
                default_params_model = model_instance.get_default_params()
                default_params = default_params_model.model_dump(exclude_none=True)
            except:
                pass

            try:
                default_grid_model = model_instance.get_default_param_grid()
                default_param_grid = default_grid_model.model_dump(exclude_none=True)
            except:
                pass

            # Build metadata entry
            model_metadata = {
                "name": model_name,
                "display_name": model_name.replace(".", " ").replace("_", " ").title(),
                "type": model_type,
                "description": model_class.__doc__.strip() if model_class.__doc__ else "",
                "param_schema": param_schema,
                "param_grid_schema": param_grid_schema,
                "default_params": default_params,
                "default_param_grid": default_param_grid,
                "available": True
            }

            metadata.append(model_metadata)
            print(f"✓ Generated metadata for {model_name}")

        except Exception as e:
            print(f"✗ Failed to generate metadata for {model_name}: {e}", file=sys.stderr)
            continue

    return metadata


def main():
    """Main entry point"""
    print("Generating model metadata...")
    print()

    metadata = generate_model_metadata()

    # Sort by model name
    metadata.sort(key=lambda x: x["name"])

    # Write to file
    output_file = Path(__file__).parent / "model_metadata.json"
    with open(output_file, "w") as f:
        json.dump(metadata, f, indent=2)

    print()
    print(f"✓ Generated metadata for {len(metadata)} models")
    print(f"✓ Written to: {output_file}")
    print()
    print("Next steps:")
    print("1. Review model_metadata.json")
    print("2. Use this file for database migration")
    print("3. Backend can import models from this metadata")


if __name__ == "__main__":
    main()
