<template>
  <a-modal
    v-model:open="visible"
    :title="t('tuning.autoTuneDialog.title', { model: modelLabel })"
    width="700px"
    :footer="null"
  >
    <div class="auto-tune-dialog-content">
      <p class="mb-4 text-gray-600">
        {{ t("tuning.autoTuneDialog.description") }}
      </p>
      
      <ModelParamGridForm
        ref="formRef"
        :model="model"
        v-model="formData"
      />
      
      <div class="mt-6 flex justify-end gap-2">
        <a-button @click="handleCancel">
          {{ t("common.cancel") }}
        </a-button>
        <a-button type="primary" @click="handleCreateTask">
          {{ t("tuning.autoTuneDialog.createButton") }}
        </a-button>
      </div>
    </div>
  </a-modal>
</template>

<script setup lang="ts">
import { ref, computed } from "vue";
import { useI18n } from "vue-i18n";
import { AVAILABLE_MODELS } from "~/constants/models";

const { t } = useI18n();

interface AutoTuneDialogProps {
  modelValue: boolean;
  model: string;
}

const props = defineProps<AutoTuneDialogProps>();

const emit = defineEmits<{
  "update:modelValue": [value: boolean];
  "create-task": [values: Record<string, any>];
}>();

const visible = computed({
  get: () => props.modelValue,
  set: (value) => emit("update:modelValue", value),
});

// Compute model label from model value
const modelLabel = computed(() => {
  const found = AVAILABLE_MODELS.find(m => m.value === props.model);
  return found?.label || t(`models.${props.model.replace(".", "_")}`);
});

const formRef = ref();
const formData = ref<Record<string, any>>({});

const handleCreateTask = async () => {
  try {
    await formRef.value?.validate();
    emit("create-task", formData.value);
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
.auto-tune-dialog-content {
  max-height: 600px;
  overflow-y: auto;
}
</style>
