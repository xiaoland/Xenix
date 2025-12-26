<template>
  <div class="space-y-4">
    <a-alert
      :message="$t('columns.title')"
      :description="$t('columns.description')"
      type="info"
      show-icon
      class="mb-4"
    />

    <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
      <!-- Feature Columns Selection -->
      <div>
        <h3 class="text-lg font-semibold mb-3 flex items-center">
          <span class="i-mdi-table-column text-blue-500 mr-2" />
          {{ $t("columns.featureColumns") }}
        </h3>
        <p class="text-sm text-gray-600 mb-3">
          {{ $t("columns.featureDescription") }}
        </p>
        <a-checkbox-group
          v-model:value="localFeatureColumns"
          class="w-full"
          @change="handleFeatureColumnsChange"
        >
          <div class="space-y-2">
            <a-checkbox
              v-for="column in availableColumns"
              :key="column"
              :value="column"
              :disabled="column === localTargetColumn"
              class="w-full p-2 rounded hover:bg-gray-50 border border-transparent hover:border-gray-200"
            >
              <span class="font-mono text-sm">{{ column }}</span>
            </a-checkbox>
          </div>
        </a-checkbox-group>
        <div class="mt-3 text-sm text-gray-500">
          {{
            $t("columns.selectedFeatures", {
              count: localFeatureColumns.length,
            })
          }}
        </div>
      </div>

      <!-- Target Column Selection -->
      <div>
        <h3 class="text-lg font-semibold mb-3 flex items-center">
          <span class="i-mdi-target text-green-500 mr-2" />
          {{ $t("columns.targetColumn") }}
        </h3>
        <p class="text-sm text-gray-600 mb-3">
          {{ $t("columns.targetDescription") }}
        </p>
        <a-radio-group
          v-model:value="localTargetColumn"
          class="w-full"
          @change="handleTargetColumnChange"
        >
          <div class="space-y-2">
            <a-radio
              v-for="column in availableColumns"
              :key="column"
              :value="column"
              :disabled="localFeatureColumns.includes(column)"
              class="w-full p-2 rounded hover:bg-gray-50 border border-transparent hover:border-gray-200"
            >
              <span class="font-mono text-sm">{{ column }}</span>
            </a-radio>
          </div>
        </a-radio-group>
        <div
          v-if="localTargetColumn"
          class="mt-3 text-sm text-green-600 flex items-center"
        >
          <span class="i-mdi-check-circle mr-1"></span>
          {{ $t("columns.targetSelected", { column: localTargetColumn }) }}
        </div>
      </div>
    </div>

    <a-divider />

    <div class="flex justify-between items-center">
      <a-button @click="$emit('back')">
        <template #icon>
          <span class="i-mdi-arrow-left" />
        </template>
        {{ $t("columns.backToUpload") }}
      </a-button>

      <a-space>
        <a-tag v-if="localFeatureColumns.length > 0" color="blue">
          {{ $t("columns.featuresTag", { count: localFeatureColumns.length }) }}
        </a-tag>
        <a-tag v-if="localTargetColumn" color="green">
          {{ $t("columns.targetSetTag") }}
        </a-tag>
      </a-space>

      <a-button
        type="primary"
        :disabled="!isValid"
        @click="
          $emit('confirm', {
            featureColumns: localFeatureColumns,
            targetColumn: localTargetColumn,
          })
        "
        class="inline-flex items-center"
      >
        {{ $t("columns.confirmSelection") }}
        <span class="i-mdi-arrow-right ml-1" />
      </a-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from "vue";

const props = defineProps<{
  columns: string[];
  featureColumns?: string[];
  targetColumn?: string;
}>();

const emit = defineEmits<{
  back: [];
  confirm: [{ featureColumns: string[]; targetColumn: string }];
}>();

const localFeatureColumns = ref<string[]>(props.featureColumns || []);
const localTargetColumn = ref<string | undefined>(props.targetColumn);

const availableColumns = computed(() => props.columns);

const isValid = computed(() => {
  return (
    localFeatureColumns.value.length > 0 &&
    localTargetColumn.value !== undefined
  );
});

const handleFeatureColumnsChange = () => {
  // If target column is selected in features, deselect it
  if (
    localTargetColumn.value &&
    localFeatureColumns.value.includes(localTargetColumn.value)
  ) {
    localTargetColumn.value = undefined;
  }
};

const handleTargetColumnChange = () => {
  // If target column was in features, remove it
  if (
    localTargetColumn.value &&
    localFeatureColumns.value.includes(localTargetColumn.value)
  ) {
    localFeatureColumns.value = localFeatureColumns.value.filter(
      (c) => c !== localTargetColumn.value
    );
  }
};

// Watch for prop changes
watch(
  () => props.columns,
  () => {
    // Reset selections if columns change
    if (localFeatureColumns.value.some((col) => !props.columns.includes(col))) {
      localFeatureColumns.value = [];
    }
    if (
      localTargetColumn.value &&
      !props.columns.includes(localTargetColumn.value)
    ) {
      localTargetColumn.value = undefined;
    }
  }
);
</script>

<style scoped>
.ant-checkbox-wrapper,
.ant-radio-wrapper {
  display: flex;
  align-items: center;
  width: 100%;
  margin: 0 !important;
}
</style>
