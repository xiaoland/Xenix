/**
 * Schema utilities for form generation
 */

/**
 * Convert field name to human-readable label
 */
export function formatFieldLabel(fieldName: string): string {
  return fieldName
    .replace(/_/g, " ")
    .replace(/([A-Z])/g, " $1")
    .replace(/^./, (str) => str.toUpperCase())
    .trim();
}

/**
 * Determine the type of items in an array schema
 */
export function getArrayItemType(propSchema: any): string {
  if (propSchema.items) {
    return propSchema.items.type || "string";
  }
  
  // Try to infer from default values
  if (Array.isArray(propSchema.default) && propSchema.default.length > 0) {
    const firstItem = propSchema.default[0];
    return typeof firstItem;
  }
  
  return "string";
}

/**
 * Determine the type of a single item (extracts from array schema if needed)
 */
export function getItemType(propSchema: any): string {
  if (propSchema.items) {
    return propSchema.items.type || "string";
  }
  
  // Try to infer from default values
  if (Array.isArray(propSchema.default) && propSchema.default.length > 0) {
    const firstItem = propSchema.default[0];
    return typeof firstItem;
  }
  
  // Fallback to propSchema type if directly specified
  if (propSchema.type) {
    return propSchema.type;
  }
  
  return "string";
}

/**
 * Get default value from schema based on mode
 */
export function getDefaultValue(propSchema: any, mode: "paramGrid" | "parameters"): any {
  if (propSchema.default !== undefined) {
    if (mode === "paramGrid") {
      return propSchema.default;
    } else {
      // For parameters mode, show first value from array
      return Array.isArray(propSchema.default)
        ? propSchema.default[0]
        : propSchema.default;
    }
  }
  return "";
}

/**
 * Create appropriate default value based on type and mode
 */
export function createDefaultValue(itemType: string, mode: "paramGrid" | "parameters"): any {
  if (mode === "paramGrid") {
    return [];
  }
  
  switch (itemType) {
    case "boolean":
      return false;
    case "number":
    case "integer":
      return 0;
    default:
      return "";
  }
}
