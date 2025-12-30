<template>
  <div>
    <div class="flex items-center gap-3 mb-4">
      <a-select
        v-model:value="selectedModelToAdd"
        :placeholder="$t('ml.modelSelector.selectModel')"
        style="min-width: 220px"
      >
        <a-select-option
          v-for="model in availableModels"
          :key="model.value"
          :value="model.value"
        >
          {{ model.label }}
        </a-select-option>
      </a-select>

      <a-button
        type="primary"
        @click="addSelectedModel"
        :disabled="!selectedModelToAdd"
      >
        {{ $t("common.add") }}
      </a-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";

const props = defineProps<{
  availableModels: Array<{ label: string; value: string }>;
  tuningStatus?: Record<string, string>;
  selectedModels?: string[];
}>();

const emit = defineEmits<{
  (e: "update:selectedModels", value: string[]): void;
  (e: "toggle", modelValue: string): void;
}>();

const selectedModels = computed<string[]>({
  get: () => props.selectedModels || [],
  set: (val: string[]) => emit("update:selectedModels", val),
});

const selectedModelToAdd = ref<string | undefined>();

const addSelectedModel = () => {
  if (!selectedModelToAdd.value) return;
  if (!selectedModels.value.includes(selectedModelToAdd.value)) {
    selectedModels.value = [...selectedModels.value, selectedModelToAdd.value];
    emit("toggle", selectedModelToAdd.value);
  }
  selectedModelToAdd.value = undefined;
};

const removeModel = (modelValue: string) => {
  if (!selectedModels.value.includes(modelValue)) return;
  selectedModels.value = selectedModels.value.filter((v) => v !== modelValue);
  emit("toggle", modelValue);
};

const findLabel = (value: string) => {
  const m = props.availableModels.find((x) => x.value === value);
  return m ? m.label : value;
};

const getStatusColor = (status: string) => {
  switch (status) {
    case "completed":
      return "green";
    case "running":
      return "blue";
    case "failed":
      return "red";
    default:
      return "default";
  }
};
</script>
