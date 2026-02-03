<template>
  <div class="ml-backend-deployment-selector">
    <a-select
      :value="modelValue"
      :options="selectOptions"
      placeholder="Select ML Backend Deployment"
      :disabled="disabled || isLoading"
      :loading="isLoading"
      @change="handleChange"
      allow-clear
      @clear="handleClear"
    />

    <a-alert
      v-if="error"
      message="Failed to load deployments"
      type="error"
      show-icon
      class="mt-2"
    />

    <a-alert
      v-if="datasetStorage && filteredDeployments.length === 0 && !isLoading"
      :message="`No ${datasetStorage} deployments available`"
      type="info"
      show-icon
      class="mt-2"
    />

    <a-alert
      v-if="modelValue && selectedDeployment"
      :message="`Selected: ${selectedDeployment.name}${
        selectedDeployment.apiUrl ? ` (${selectedDeployment.apiUrl})` : ''
      }`"
      type="success"
      show-icon
      class="mt-2"
    />
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue";
import type { MLBackendDeployment } from "@xenix/shared";
import { useMLBackendDeployments } from "@/features/ml/queries";

interface Props {
  modelValue?: number | null;
  datasetStorage?: "local" | "oss" | null;
  disabled?: boolean;
}

const props = withDefaults(defineProps<Props>(), {
  modelValue: null,
  datasetStorage: null,
  disabled: false,
});

const emit = defineEmits<{
  "update:modelValue": [value: number | null];
}>();

const { data: deployments, isLoading, error } = useMLBackendDeployments();

const filteredDeployments = computed(() => {
  if (!deployments.value) return [];

  if (!props.datasetStorage) {
    return deployments.value;
  }

  return deployments.value.filter(
    (deployment: MLBackendDeployment) =>
      deployment.storage === props.datasetStorage,
  );
});

const selectOptions = computed(() => {
  return filteredDeployments.value.map((deployment: MLBackendDeployment) => ({
    label: `${deployment.name} (${deployment.storage})`,
    value: deployment.id,
  }));
});

const selectedDeployment = computed(() => {
  if (!props.modelValue || !deployments.value) return null;
  return (
    deployments.value.find(
      (d: MLBackendDeployment) => d.id === props.modelValue,
    ) || null
  );
});

function handleChange(value: number | null) {
  emit("update:modelValue", value);
}

function handleClear() {
  emit("update:modelValue", null);
}
</script>

<style scoped>
.ml-backend-deployment-selector {
  margin-bottom: 1.5rem;
}

:deep(.ant-select) {
  width: 100%;
}
</style>
