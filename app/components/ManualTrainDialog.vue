<template>
  <a-modal
    v-model:open="visible"
    :title="t('tuning.manualTrainDialog.title', { model: modelLabel })"
    width="700px"
    @ok="handleOk"
    @cancel="handleCancel"
  >
    <div class="mb-4 text-gray-600">
      {{ t("tuning.manualTrainDialog.description") }}
    </div>
    <AutoForm
      ref="autoFormRef"
      v-model="formData"
      :schema="schema"
      mode="manual"
    />
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

const autoFormRef = ref();
const formData = ref<Record<string, any>>({});

// Initialize form data when initial values change
watch(
  () => props.initialValues,
  () => {
    if (props.initialValues) {
      formData.value = { ...props.initialValues };
    }
  },
  { immediate: true }
);

const handleOk = async () => {
  try {
    await autoFormRef.value?.validate();
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


