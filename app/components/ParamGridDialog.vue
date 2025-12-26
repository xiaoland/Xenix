<template>
  <a-modal
    v-model:open="visible"
    :title="t('tuning.paramGrid.title', { model: modelLabel })"
    width="700px"
    @ok="handleOk"
    @cancel="handleCancel"
  >
    <a-form
      ref="formRef"
      :model="formData"
      layout="vertical"
      class="param-grid-form"
    >
      <div v-if="!schema || !schema.properties" class="text-center py-4">
        <a-spin />
        <p class="mt-2">{{ t("tuning.paramGrid.loading") }}</p>
      </div>
      <div v-else>
        <p class="mb-4 text-gray-600">
          {{ t("tuning.paramGrid.description") }}
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
                {{ propSchema.description || t("tuning.paramGrid.noDescription") }}
              </div>
              <div class="text-xs text-gray-400">
                {{ t("tuning.paramGrid.defaultValue") }}:
                <code class="bg-gray-100 px-1 py-0.5 rounded">{{
                  JSON.stringify(propSchema.default)
                }}</code>
              </div>
            </template>
            <ArrayInput
              v-model="formData[propName as string]"
              :item-type="getArrayItemType(propSchema)"
              :placeholder="t('tuning.paramGrid.arrayPlaceholder')"
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

interface ParamGridDialogProps {
  modelValue: boolean;
  modelName: string;
  modelLabel: string;
  schema: any;
  initialValues?: Record<string, any>;
}

const props = defineProps<ParamGridDialogProps>();

const emit = defineEmits<{
  "update:modelValue": [value: boolean];
  save: [values: Record<string, any>];
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
      // Use initial values if provided, otherwise use schema defaults
      if (props.initialValues && props.initialValues[propName] !== undefined) {
        data[propName] = props.initialValues[propName];
      } else if (schema.default !== undefined) {
        data[propName] = Array.isArray(schema.default)
          ? [...schema.default]
          : schema.default;
      } else {
        // Create empty array as fallback
        data[propName] = [];
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

const getArrayItemType = (propSchema: any): string => {
  // Determine the type of items in the array
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

const handleOk = async () => {
  try {
    await formRef.value?.validate();
    emit("save", formData.value);
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
.param-grid-form :deep(.ant-form-item) {
  margin-bottom: 16px;
}

.param-grid-form :deep(.ant-form-item-label) {
  font-weight: 500;
}
</style>
