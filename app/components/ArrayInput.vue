<template>
  <div class="array-input">
    <div class="flex gap-2 mb-2">
      <a-input
        v-model:value="inputValue"
        :placeholder="placeholder"
        :type="inputType"
        @keydown.enter="handleAdd"
        class="flex-1"
      />
      <a-button
        type="primary"
        @click="handleAdd"
        :disabled="!inputValue"
        class="inline-flex items-center"
      >
        <span class="i-mdi-plus mr-1" />
        {{ t("common.add") }}
      </a-button>
    </div>
    <div v-if="localValues.length > 0" class="space-y-1">
      <a-tag
        v-for="(value, index) in localValues"
        :key="index"
        closable
        @close="handleRemove(index)"
        class="mb-1"
      >
        {{ formatValue(value) }}
      </a-tag>
    </div>
    <div v-else class="text-gray-400 text-sm py-2">
      {{ t("tuning.paramGrid.emptyArray") }}
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from "vue";

const { t } = useI18n();

interface ArrayInputProps {
  modelValue: any[];
  itemType?: string;
  placeholder?: string;
}

const props = withDefaults(defineProps<ArrayInputProps>(), {
  itemType: "string",
  placeholder: "Enter value and press Add",
});

const emit = defineEmits<{
  "update:modelValue": [value: any[]];
}>();

const inputValue = ref("");
const localValues = computed({
  get: () => props.modelValue || [],
  set: (value) => emit("update:modelValue", value),
});

const inputType = computed(() => {
  if (props.itemType === "number" || props.itemType === "integer") {
    return "number";
  }
  return "text";
});

const handleAdd = () => {
  if (!inputValue.value) return;

  let parsedValue: any;
  try {
    // Parse value based on type
    switch (props.itemType) {
      case "number":
      case "integer":
        parsedValue = parseFloat(inputValue.value);
        if (isNaN(parsedValue)) {
          console.error("Invalid number");
          return;
        }
        if (props.itemType === "integer") {
          parsedValue = Math.floor(parsedValue);
        }
        break;
      case "boolean":
        parsedValue = inputValue.value.toLowerCase() === "true";
        break;
      default:
        parsedValue = inputValue.value;
    }

    // Add to array
    localValues.value = [...localValues.value, parsedValue];
    inputValue.value = "";
  } catch (error) {
    console.error("Failed to parse value:", error);
  }
};

const handleRemove = (index: number) => {
  const newValues = [...localValues.value];
  newValues.splice(index, 1);
  localValues.value = newValues;
};

const formatValue = (value: any): string => {
  if (typeof value === "object") {
    return JSON.stringify(value);
  }
  return String(value);
};
</script>

<style scoped>
.array-input {
  border: 1px solid #d9d9d9;
  border-radius: 6px;
  padding: 12px;
  background-color: #fafafa;
}
</style>
