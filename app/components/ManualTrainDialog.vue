<template>
  <a-modal
    v-model:open="visible"
    :title="t('tuning.manualTrainDialog.title', { model: modelLabel })"
    width="700px"
    @ok="handleOk"
    @cancel="handleCancel"
  >
    <a-form
      ref="formRef"
      :model="formData"
      layout="vertical"
      class="manual-train-form"
    >
      <div v-if="!schema || !schema.properties" class="text-center py-4">
        <a-spin />
        <p class="mt-2">{{ t("tuning.manualTrainDialog.loading") }}</p>
      </div>
      <div v-else>
        <p class="mb-4 text-gray-600">
          {{ t("tuning.manualTrainDialog.description") }}
        </p>
        <template
          v-for="(propSchema, propName) in schema.properties"
          :key="propName"
        >
          <a-form-item
            :label="formatFieldLabel(propName as string)"
            :name="propName"
          >
            <template #extra>
              <div class="text-xs text-gray-500">
                {{ propSchema.description || t("tuning.manualTrainDialog.noDescription") }}
              </div>
              <div class="text-xs text-gray-400">
                {{ t("tuning.manualTrainDialog.defaultValue") }}:
                <code class="bg-gray-100 px-1 py-0.5 rounded">{{
                  getDefaultValue(propSchema)
                }}</code>
              </div>
            </template>
            <a-input-number
              v-if="getItemType(propSchema) === 'number' || getItemType(propSchema) === 'integer'"
              v-model:value="formData[propName as string]"
              :placeholder="getDefaultValue(propSchema).toString()"
              class="w-full"
            />
            <a-input
              v-else
              v-model:value="formData[propName as string]"
              :placeholder="getDefaultValue(propSchema).toString()"
            />
          </a-form-item>
        </template>
      </div>
    </a-form>
  </a-modal>
</template>

<script setup lang="ts">
import { ref, computed, watch } from "vue";

const { t } = useI18n();

interface ManualTrainDialogProps {
  modelValue: boolean;
  modelName: string;
  modelLabel: string;
  schema: any;
  initialValues?: Record<string, any>;
}

const props = defineProps<ManualTrainDialogProps>();

const emit = defineEmits<{
  "update:modelValue": [value: boolean];
  train: [values: Record<string, any>];
}>();

const visible = computed({
  get: () => props.modelValue,
  set: (value) => emit("update:modelValue", value),
});

const formRef = ref();
const formData = ref<Record<string, any>>({});

// Initialize form data when dialog opens or initial values change
watch(
  () => [props.modelValue, props.initialValues, props.schema],
  () => {
    if (props.modelValue && props.schema) {
      initializeFormData();
    }
  },
  { immediate: true }
);

const initializeFormData = () => {
  const data: Record<string, any> = {};

  if (props.schema && props.schema.properties) {
    for (const [propName, propSchema] of Object.entries(
      props.schema.properties
    )) {
      const schema = propSchema as any;
      // Use initial values if provided, otherwise use first default value from array
      if (props.initialValues && props.initialValues[propName] !== undefined) {
        data[propName] = props.initialValues[propName];
      } else if (schema.default !== undefined) {
        // For manual training, convert array to single value
        data[propName] = Array.isArray(schema.default)
          ? schema.default[0]
          : schema.default;
      } else {
        // Create default value based on type
        const itemType = getItemType(schema);
        data[propName] = itemType === "number" || itemType === "integer" ? 0 : "";
      }
    }
  }

  formData.value = data;
};

const formatFieldLabel = (fieldName: string): string => {
  // Convert snake_case or camelCase to Title Case
  return fieldName
    .replace(/_/g, " ")
    .replace(/([A-Z])/g, " $1")
    .replace(/^./, (str) => str.toUpperCase())
    .trim();
};

const getItemType = (propSchema: any): string => {
  // Determine the type of the item (for manual training, we extract from array schema)
  if (propSchema.items) {
    return propSchema.items.type || "string";
  }
  // Try to infer from default values
  if (Array.isArray(propSchema.default) && propSchema.default.length > 0) {
    const firstItem = propSchema.default[0];
    return typeof firstItem;
  }
  return "string";
};

const getDefaultValue = (propSchema: any): any => {
  if (propSchema.default !== undefined) {
    // For manual training, show first value from array
    return Array.isArray(propSchema.default)
      ? propSchema.default[0]
      : propSchema.default;
  }
  return "";
};

const handleOk = async () => {
  try {
    await formRef.value?.validate();
    emit("train", formData.value);
    visible.value = false;
  } catch (error) {
    console.error("Validation failed:", error);
  }
};

const handleCancel = () => {
  visible.value = false;
};
</script>

<style scoped>
.manual-train-form :deep(.ant-form-item) {
  margin-bottom: 16px;
}

.manual-train-form :deep(.ant-form-item-label) {
  font-weight: 500;
}
</style>
