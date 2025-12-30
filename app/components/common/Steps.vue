<template>
  <div class="steps-container flex items-start">
    <div
      v-for="(item, index) in items"
      :key="index"
      class="step-item flex flex-col items-center flex-1"
      :class="{
        'step-active': index === current,
        'step-completed': index < current,
      }"
    >
      <!-- Step Circle -->
      <div
        class="step-circle relative flex items-center justify-center w-10 h-10 rounded-full border-2 mb-2"
      >
        <span
          v-if="index < current"
          class="i-mdi-check text-white text-lg"
        ></span>
        <span v-else class="text-sm font-medium">{{ index + 1 }}</span>
      </div>

      <!-- Step Content -->
      <div class="step-content text-center">
        <div class="step-title text-sm font-medium mb-1">{{ item.title }}</div>
        <div class="step-description text-xs text-gray-500">
          {{ item.description }}
        </div>
      </div>

      <!-- Connector Line (except last item) -->
      <div
        v-if="index < items.length - 1"
        class="connector-line absolute top-5 left-1/2 w-full h-0.5 bg-gray-300 -z-10"
        :class="{ 'bg-blue-500': index < current }"
      ></div>
    </div>
  </div>
</template>

<script setup lang="ts">
interface StepItem {
  title: string;
  description: string;
}

defineProps<{
  current: number;
  items: StepItem[];
}>();
</script>

<style scoped>
.step-circle {
  transition: all 0.3s ease;
}

.step-item.step-completed .step-circle {
  background-color: #52c41a;
  border-color: #52c41a;
  color: white;
}

.step-item.step-active .step-circle {
  background-color: #1890ff;
  border-color: #1890ff;
  color: white;
}

.step-item:not(.step-active):not(.step-completed) .step-circle {
  background-color: white;
  border-color: #d9d9d9;
  color: #bfbfbf;
}

.step-item.step-completed .step-title,
.step-item.step-active .step-title {
  color: #262626;
}

.step-item:not(.step-active):not(.step-completed) .step-title {
  color: #bfbfbf;
}

.step-item.step-completed .step-description,
.step-item.step-active .step-description {
  color: #595959;
}

.step-item:not(.step-active):not(.step-completed) .step-description {
  color: #d9d9d9;
}

.connector-line {
  transform: translateX(50%);
}
</style>
