<template>
  <div class="space-y-6">
    <!-- Feature Columns Selection -->
    <div>
      <label class="block text-sm font-medium mb-2">
        {{ $t("components.ml.columnSelector.featureColumns") }}
        <span class="text-red-500">*</span>
      </label>
      <p class="text-sm text-gray-600 mb-3">
        {{ $t("components.ml.columnSelector.featureColumnsRequired") }}
      </p>
      <a-select
        v-model:value="localFeatureColumns"
        mode="multiple"
        :placeholder="$t('components.ml.columnSelector.featurePlaceholder')"
        :options="availableFeatureOptions"
        class="w-full"
        @change="handleFeatureColumnsChange"
      />
      <p class="text-xs text-gray-500 mt-1">
        {{
          $t("components.ml.columnSelector.selectedCount", {
            count: localFeatureColumns.length,
          })
        }}
      </p>
    </div>

    <!-- Target Column Selection -->
    <div>
      <label class="block text-sm font-medium mb-2">
        {{ $t("components.ml.columnSelector.targetColumn") }}
        <span class="text-red-500">*</span>
      </label>
      <p class="text-sm text-gray-600 mb-3">
        {{ $t("components.ml.columnSelector.targetColumnRequired") }}
      </p>
      <a-select
        v-model:value="localTargetColumn"
        :placeholder="$t('components.ml.columnSelector.targetPlaceholder')"
        :options="availableTargetOptions"
        class="w-full"
        @change="handleTargetColumnChange"
      />
    </div>

    <!-- Summary -->
    <div
      v-if="localFeatureColumns.length > 0 && localTargetColumn"
      class="bg-blue-50 border border-blue-200 rounded p-4"
    >
      <h4 class="font-medium mb-2">
        {{ $t("components.ml.columnSelector.summary") }}
      </h4>
      <ul class="text-sm space-y-1">
        <li>
          <strong>{{ $t("components.ml.columnSelector.features") }}:</strong>
          {{ localFeatureColumns.join(", ") }}
        </li>
        <li>
          <strong>{{ $t("components.ml.columnSelector.target") }}:</strong>
          {{ localTargetColumn }}
        </li>
      </ul>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue";

const props = defineProps<{
  columns: string[];
  featureColumns: string[];
  targetColumn?: string;
}>();

const emit = defineEmits<{
  "update:featureColumns": [value: string[]];
  "update:targetColumn": [value: string];
}>();

const localFeatureColumns = ref<string[]>([...props.featureColumns]);
const localTargetColumn = ref<string | undefined>(props.targetColumn);

// Available feature columns (exclude target if selected)
const availableFeatureOptions = computed(() => {
  return props.columns
    .filter((col) => col !== localTargetColumn.value)
    .map((col) => ({ label: col, value: col }));
});

// Available target columns (exclude selected features)
const availableTargetOptions = computed(() => {
  return props.columns
    .filter((col) => !localFeatureColumns.value.includes(col))
    .map((col) => ({ label: col, value: col }));
});

const handleFeatureColumnsChange = () => {
  emit("update:featureColumns", localFeatureColumns.value);
};

const handleTargetColumnChange = () => {
  if (localTargetColumn.value) {
    emit("update:targetColumn", localTargetColumn.value);
  }
};

// Watch for external changes
watch(
  () => props.featureColumns,
  (newVal) => {
    localFeatureColumns.value = [...newVal];
  }
);

watch(
  () => props.targetColumn,
  (newVal) => {
    localTargetColumn.value = newVal;
  }
);
</script>
