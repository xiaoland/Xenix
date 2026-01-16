<template>
  <a-modal
    v-model:open="visible"
    :title="$t('ml.tuning.manualTuneDialog.title')"
    width="700px"
    :footer="null"
  >
    <div class="manual-tune-dialog-content">
      <p class="mb-4 text-gray-600">
        {{ $t("ml.tuning.manualTuneDialog.description") }}
      </p>

      <!-- Model Selection -->
      <a-form-item :label="$t('ml.tuning.selectModel')" class="mb-4">
        <a-select
          v-model:value="selectedModel"
          :placeholder="$t('ml.tuning.selectPlaceholder')"
          style="width: 100%"
          @change="handleModelChange"
        >
          <a-select-option
            v-for="model in availableModels"
            :key="model.value"
            :value="model.value"
          >
            {{ model.label }}
          </a-select-option>
        </a-select>
      </a-form-item>

      <!-- Parameter Form -->
      <div v-if="selectedModel" class="mb-4">
        <h4 class="text-sm font-medium mb-2">
          {{ $t("ml.tuning.modelParameters") }}
        </h4>
        <ModelParamForm
          ref="formRef"
          :model="selectedModel"
          v-model="formData"
        />
      </div>

      <!-- Actions -->
      <div class="mt-6 flex justify-end gap-2">
        <a-button @click="handleCancel">
          {{ $t("common.cancel") }}
        </a-button>
        <a-button
          type="primary"
          :disabled="!selectedModel"
          :loading="loading"
          @click="handleTune"
        >
          <span class="i-mdi-play mr-1"></span>
          {{ $t("ml.tuning.manualTuneDialog.tuneButton") }}
        </a-button>
      </div>
    </div>
  </a-modal>
</template>

<script setup lang="ts">
import { ref, computed } from "vue";
import { AVAILABLE_MODELS } from "../../../constants/models";
import ModelParamForm from "./ModelParamForm.vue";

const props = defineProps<{
  modelValue: boolean;
}>();

const emit = defineEmits<{
  "update:modelValue": [value: boolean];
  tune: [data: { model: string; parameters: Record<string, any> }];
}>();

const visible = computed({
  get: () => props.modelValue,
  set: (value) => emit("update:modelValue", value),
});

const selectedModel = ref<string>("");
const formRef = ref();
const formData = ref<Record<string, any>>({});
const loading = ref(false);

const availableModels = AVAILABLE_MODELS;

const handleModelChange = () => {
  // Reset form data when model changes
  formData.value = {};
};

const handleTune = async () => {
  if (!selectedModel.value) return;

  try {
    loading.value = true;
    await formRef.value?.validate();
    emit("tune", {
      model: selectedModel.value,
      parameters: formData.value,
    });
    // Reset and close
    selectedModel.value = "";
    formData.value = {};
    visible.value = false;
  } catch (error) {
    console.error("Validation failed:", error);
  } finally {
    loading.value = false;
  }
};

const handleCancel = () => {
  selectedModel.value = "";
  formData.value = {};
  visible.value = false;
};
</script>

<style scoped>
.manual-tune-dialog-content {
  max-height: 600px;
  overflow-y: auto;
}
</style>
