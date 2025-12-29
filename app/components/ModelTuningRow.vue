<template>
  <div>
    <template v-if="column.key === 'select'">
      <!-- Only show radio button in sub-rows (history items) -->
      <a-radio
        v-if="record.isHistory"
        :checked="selectedTaskId === record.taskId"
        @click="$emit('update:selectedTaskId', record.taskId)"
      />
    </template>

    <template v-else-if="column.key === 'model'">
      <span class="font-medium" :class="{ 'pl-2': record.isHistory }">
        {{
          record.isHistory
            ? `${formatTimestamp(record.createdAt)}`
            : record.label
        }}
      </span>
    </template>

    <template v-else-if="column.key === 'tuneType'">
      <!-- Show tune type and parameters for sub-rows -->
      <div v-if="record.isHistory" class="text-sm">
        <div class="font-medium mb-1">
          <a-tag v-if="record.trainingType === 'auto-tune'" color="blue">
            {{ t("tuning.autoTune") }}
          </a-tag>
          <a-tag v-else-if="record.trainingType === 'train'" color="green">
            {{ t("tuning.manualTrain") }}
          </a-tag>
        </div>
        <div v-if="record.params" class="text-xs text-gray-600">
          <div
            v-for="(value, key) in record.params"
            :key="key"
            class="truncate"
          >
            <span class="font-medium">{{ key }}:</span>
            {{ formatParamValue(value) }}
          </div>
        </div>
      </div>
    </template>

    <template v-else-if="column.key === 'action'">
      <!-- Parent row: Only show Auto Tune and Train buttons -->
      <div v-if="!record.isHistory" class="flex gap-2">
        <a-button
          type="primary"
          size="small"
          :disabled="isTuning"
          @click="$emit('auto-tune', record.model, record.label)"
          class="inline-flex items-center"
        >
          <span class="i-mdi-tune mr-1" />
          {{ t("tuning.autoTune") }}
        </a-button>
        <a-button
          size="small"
          :disabled="isTuning"
          @click="$emit('manual-train', record.model, record.label)"
          class="inline-flex items-center"
        >
          <span class="i-mdi-pencil mr-1" />
          {{ t("tuning.manualTrain") }}
        </a-button>
      </div>
      <!-- Sub-row: Show View Logs button and status tag for each training task -->
      <div v-else class="flex gap-2 items-center">
        <a-button
          v-if="record.taskId"
          size="small"
          @click="$emit('view-logs', record.taskId, record.label)"
          class="inline-flex items-center"
        >
          <span class="i-mdi-text-box-outline mr-1" />
          {{ t("tuning.viewLogs") }}
        </a-button>
        <a-tag v-if="record.status" :color="getStatusColor(record.status)">
          {{ record.status }}
        </a-tag>
      </div>
    </template>

    <template v-else-if="column.key === 'metrics'">
      <div v-if="record.metrics" class="text-sm">
        <div>
          <span class="font-medium">{{ t("metrics.r2") }}:</span>
          {{ formatMetric(record.metrics.r2_test) }}
        </div>
        <div>
          <span class="font-medium">{{ t("metrics.mse") }}:</span>
          {{ formatMetric(record.metrics.mse_test) }}
        </div>
        <div>
          <span class="font-medium">{{ t("metrics.mae") }}:</span>
          {{ formatMetric(record.metrics.mae_test) }}
        </div>
      </div>
      <span v-else class="text-gray-400">{{ t("common.na") }}</span>
    </template>
  </div>
</template>

<script setup lang="ts">
import { useI18n } from "vue-i18n";

const { t } = useI18n();

const props = defineProps<{
  column: any;
  record: any;
  selectedTaskId: number | null;
  isTuning: boolean;
}>();

const emit = defineEmits<{
  (e: "update:selectedTaskId", value: number | null): void;
  (e: "auto-tune", modelName: string, modelLabel: string): void;
  (e: "manual-train", modelName: string, modelLabel: string): void;
  (e: "view-logs", taskId: number, modelName: string): void;
}>();

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

const formatParamValue = (value: any): string => {
  if (Array.isArray(value)) {
    return `[${value.join(", ")}]`;
  }
  if (typeof value === "object" && value !== null) {
    return JSON.stringify(value);
  }
  return String(value);
};
</script>
