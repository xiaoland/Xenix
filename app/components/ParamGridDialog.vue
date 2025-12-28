<template>
  <a-modal
    v-model:open="visible"
    :title="t('tuning.paramGrid.title', { model: modelLabel })"
    width="700px"
    @ok="handleOk"
    @cancel="handleCancel"
  >
    <div v-if="!schema || !schema.properties" class="text-center py-4">
      <a-spin />
      <p class="mt-2">{{ t("tuning.paramGrid.loading") }}</p>
    </div>
    <div v-else>
      <p class="mb-4 text-gray-600">
        {{ t("tuning.paramGrid.description") }}
      </p>
      <AutoForm
        ref="autoFormRef"
        v-model="formData"
        :schema="schema"
        mode="paramGrid"
      />
    </div>
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

const autoFormRef = ref();
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

const handleOk = async () => {
  try {
    await autoFormRef.value?.validate();
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
</style>
