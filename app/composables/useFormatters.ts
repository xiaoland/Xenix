import { useI18n } from "vue-i18n";

/**
 * Composable for formatting utilities
 */
export function useFormatters() {
  const { t } = useI18n();

  const formatModelName = (name: string) => {
    return name.replace(/_/g, " ");
  };

  const formatTimestamp = (timestamp: any) => {
    if (!timestamp) return "";
    const date = new Date(timestamp);
    return date.toLocaleString();
  };

  const formatMetric = (value: string | number) => {
    if (!value) return t("common.na");
    const num = typeof value === "string" ? parseFloat(value) : value;
    return num.toFixed(4);
  };

  const getStatusColor = (status: string) => {
    const colors: Record<string, string> = {
      completed: "green",
      running: "blue",
      pending: "orange",
      failed: "red",
    };
    return colors[status?.toLowerCase()] || "default";
  };

  return {
    formatModelName,
    formatTimestamp,
    formatMetric,
    getStatusColor,
  };
}
