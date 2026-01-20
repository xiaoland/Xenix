/**
 * Task Formatting Composable
 * Centralized formatting utilities for task display
 */
import type { TaskStatus } from "@xenix/shared";

import { useGroupedModels } from "./useModels";

export interface TaskFormatting {
  formatModelName: (modelValue?: string) => string;
  formatMetricKey: (key: string) => string;
  formatMetric: (value: any) => string;
  formatParamValue: (value: any) => string;
  getDisplayMetrics: (metrics: Record<string, any>) => Record<string, any>;
  getStatusColor: (
    status: TaskStatus
  ) => "success" | "error" | "processing" | "default";
}

export function useTaskFormatting(): TaskFormatting {
  const { data: availableModels } = useGroupedModels();

  /**
   * Format model name for display
   */
  const formatModelName = (modelValue?: string) => {
    if (!modelValue) return "-";
    // Search through all groups to find the model
    for (const group of availableModels.value || []) {
      const model = group.options.find((m) => m.value === modelValue);
      if (model) return model.label;
    }
    return modelValue;
  };

  /**
   * Format metric key (convert snake_case to Title Case)
   */
  const formatMetricKey = (key: string) => {
    return key
      .replace(/_/g, " ")
      .split(" ")
      .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
      .join(" ");
  };

  /**
   * Format metric value
   */
  const formatMetric = (value: any) => {
    if (typeof value === "number") {
      return value.toFixed(4);
    }
    return value;
  };

  /**
   * Format parameter value
   */
  const formatParamValue = (value: any): string => {
    if (Array.isArray(value)) {
      return `[${value.join(", ")}]`;
    }
    if (typeof value === "object" && value !== null) {
      return JSON.stringify(value);
    }
    return String(value);
  };

  /**
   * Get display metrics from result (top metrics to show in table)
   */
  const getDisplayMetrics = (metrics: Record<string, any>) => {
    if (!metrics) return {};

    // Priority metrics to display
    const priorityKeys = ["r2", "rmse", "mae", "mse"];
    const display: Record<string, any> = {};

    // Add priority metrics first
    priorityKeys.forEach((key) => {
      if (key in metrics) {
        display[key] = metrics[key];
      }
    });

    // If we have less than 3 metrics, add others
    const otherKeys = Object.keys(metrics).filter(
      (k) => !priorityKeys.includes(k)
    );
    let count = Object.keys(display).length;
    for (const key of otherKeys) {
      if (count >= 3) break;
      display[key] = metrics[key];
      count++;
    }

    return display;
  };

  /**
   * Get status color for Ant Design tags
   */
  const getStatusColor = (
    status: TaskStatus
  ): "success" | "error" | "processing" | "default" => {
    switch (status) {
      case "completed":
        return "success";
      case "failed":
        return "error";
      case "running":
        return "processing";
      case "pending":
        return "default";
      default:
        return "default";
    }
  };

  return {
    formatModelName,
    formatMetricKey,
    formatMetric,
    formatParamValue,
    getDisplayMetrics,
    getStatusColor,
  };
}
