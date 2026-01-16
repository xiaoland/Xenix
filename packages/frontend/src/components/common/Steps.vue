<template>
  <div class="steps-container">
    <div class="flex items-start">
      <div
        v-for="(item, index) in items"
        :key="index"
        class="step-item flex-1"
        :class="{
          'step-active': index === current,
          'step-completed': index < current,
        }"
      >
        <!-- Step Layout -->
        <div class="flex items-start">
          <!-- Step Circle and Connector -->
          <div class="flex flex-col items-center">
            <!-- Step Circle -->
            <div
              class="step-circle relative flex items-center justify-center w-10 h-10 rounded-full border-2 flex-shrink-0"
            >
              <span
                v-if="index < current"
                class="i-mdi-check text-white text-lg"
              ></span>
              <span v-else class="text-sm font-medium">{{ index + 1 }}</span>
            </div>

            <!-- Connector Line (except last item) -->
            <div
              v-if="index < items.length - 1"
              class="connector-line w-0.5 flex-1 mt-2"
              style="min-height: 40px"
            ></div>
          </div>

          <!-- Step Content -->
          <div class="step-content ml-4 flex-1 pb-8">
            <div class="step-title text-base font-medium mb-1">
              {{ item.title }}
            </div>
            <div class="step-description text-sm text-gray-500">
              {{ item.description }}
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
interface StepItem {
  title: string;
  description?: string;
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

.step-item.step-completed .connector-line {
  background-color: #52c41a;
}

.step-item.step-active .connector-line,
.step-item:not(.step-active):not(.step-completed) .connector-line {
  background-color: #d9d9d9;
}
</style>
