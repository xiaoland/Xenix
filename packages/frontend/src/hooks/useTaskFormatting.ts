/**
 * Task Formatting Hook
 * Centralized formatting utilities for task display
 */
import type { TaskStatus } from "@xenix/shared";

import { useGroupedModels } from "@/features/ml/queries/useModels";

export interface TaskFormatting {
  formatModelName: (modelValue?: string) => string;
  formatMetricKey: (key: string) => string;
  formatMetric: (value: any) => string;
  formatParamValue: (value: any) => string;
  getDisplayMetrics: (metrics: Record<string, any>) => Record<string, any>;
  getStatusColor: (
    status: TaskStatus,
  ) => "success" | "error" | "processing" | "default";
}

export function useTaskFormatting(): TaskFormatting {
  const { data: availableModels } = useGroupedModels();

  const formatModelName = (modelValue?: string) => {
    if (!modelValue) return "-";
    for (const group of availableModels.value || []) {
      const model = group.options.find((m) => m.value === modelValue);
      if (model) return model.label;
    }
    return modelValue;
  };

  const formatMetricKey = (key: string) => {
    return key
      .replace(/_/g, " ")
      .split(" ")
      .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
      .join(" ");
  };

  const formatMetric = (value: any) => {
    if (typeof value === "number") {
      return value.toFixed(4);
    }
    return value;
  };

  const formatParamValue = (value: any): string => {
    if (Array.isArray(value)) {
      return `[${value.join(", ")}]`;
    }
    if (typeof value === "object" && value !== null) {
      return JSON.stringify(value);
    }
    return String(value);
  };

  const getDisplayMetrics = (metrics: Record<string, any>) => {
    if (!metrics) return {};

    const priorityKeys = ["r2", "rmse", "mae", "mse"];
    const display: Record<string, any> = {};

    priorityKeys.forEach((key) => {
      if (key in metrics) {
        display[key] = metrics[key];
      }
    });

    const otherKeys = Object.keys(metrics).filter(
      (k) => !priorityKeys.includes(k),
    );
    let count = Object.keys(display).length;
    for (const key of otherKeys) {
      if (count >= 3) break;
      display[key] = metrics[key];
      count++;
    }

    return display;
  };

  const getStatusColor = (
    status: TaskStatus,
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
