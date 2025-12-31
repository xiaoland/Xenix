<template>
  <tr class="bg-gray-50 border-b">
    <!-- Select Column -->
    <td class="pl-8 py-2">
      <a-radio
        :checked="selectedTaskId === taskId"
        @click="$emit('update:selectedTaskId', taskId)"
      />
    </td>

    <!-- Action Column -->
    <td class="px-4 py-2">
      <div class="flex gap-2 items-center">
        <!-- Tune Type -->
        <a-tag
          v-if="taskType === 'auto-tune'"
          color="blue"
          class="tune-type-tag"
        >
          {{ t("tuning.type.auto") }}
        </a-tag>
        <a-tag
          v-else-if="taskType === 'manual-tune'"
          color="green"
          class="tune-type-tag"
        >
          {{ t("tuning.type.manual") }}
        </a-tag>
        <!-- Tune Status -->
        <a-tag
          v-if="task?.status"
          :color="getStatusColor(task.status)"
          class="status-tag"
        >
          {{ t(`task.status.${task.status}`) }}
        </a-tag>
        <!-- Task Logs -->
        <a-button
          size="small"
          @click="handleViewLogs"
          class="inline-flex items-center action-btn"
        >
          <span class="i-mdi-text-box-outline mr-1" />
          {{ t("tuning.viewLogs") }}
        </a-button>
        <!-- View Params -->
        <a-button
          v-if="taskParams && Object.keys(taskParams).length > 0"
          size="small"
          @click="handleViewParams"
          class="inline-flex items-center action-btn"
        >
          <span class="i-mdi-eye-outline mr-1" />
          {{ t("tuning.viewParams") }}
        </a-button>
      </div>
    </td>

    <!-- Metrics Column -->
    <td class="px-4 py-2 metrics-cell">
      <div
        class="metrics-scroll-wrapper"
        @mouseenter="showScrollButtons = true"
        @mouseleave="showScrollButtons = false"
      >
        <transition name="fade">
          <button
            v-show="showScrollButtons && canScrollLeft"
            class="scroll-nav-btn scroll-nav-left"
            @click="scrollMetrics('left')"
          >
            <span class="i-mdi-chevron-left" />
          </button>
        </transition>
        <div ref="metricsScrollContainer" class="metrics-scroll-container">
          <ModelAutoMetrics :metrics="taskMetrics" />
        </div>
        <transition name="fade">
          <button
            v-show="showScrollButtons && canScrollRight"
            class="scroll-nav-btn scroll-nav-right"
            @click="scrollMetrics('right')"
          >
            <span class="i-mdi-chevron-right" />
          </button>
        </transition>
      </div>
    </td>
  </tr>

  <!-- Log Modal -->
  <teleport to="body">
    <a-modal
      v-model:open="logModalVisible"
      :title="t('logs.titleWithTask', { taskId })"
      width="800px"
      :footer="null"
    >
      <LogPanel :logs="taskLogs" />
    </a-modal>

    <!-- Params Modal -->
    <a-modal
      v-model:open="paramsModalVisible"
      :title="t('tuning.paramsTitle')"
      width="600px"
      :footer="null"
    >
      <AutoForm
        v-if="paramSchema"
        :model-value="taskParams || {}"
        :schema="paramSchema"
        :readonly="true"
      />
      <div v-else-if="taskParams" class="params-fallback">
        <div v-for="(value, key) in taskParams" :key="key" class="param-row">
          <span class="param-key">{{ key }}:</span>
          <span class="param-value">{{ formatParamValue(value) }}</span>
        </div>
      </div>
      <div v-else class="text-gray-400">
        {{ t("common.noData") }}
      </div>
    </a-modal>
  </teleport>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from "vue";
import { useI18n } from "vue-i18n";
import { TaskService, ModelService } from "~/services";
import { useFormatters } from "~/composables/useFormatters";
import type { TaskInfo, TuningMetrics } from "~/types";
import ModelAutoMetrics from "./ModelAutoMetrics.vue";
import LogPanel from "~/components/obsrv/LogPanel.vue";
import AutoForm from "~/components/common/AutoForm.vue";

const { t } = useI18n();
const { getStatusColor } = useFormatters();

const props = defineProps<{
  taskId: number;
  selectedTaskId: number | null;
}>();

const emit = defineEmits<{
  "update:selectedTaskId": [taskId: number | null];
}>();

// Local state
const task = ref<TaskInfo | null>(null);
const taskLogs = ref<any[]>([]);
const logModalVisible = ref(false);
const paramsModalVisible = ref(false);
const paramSchema = ref<any>(null);

// Scroll navigation state
const metricsScrollContainer = ref<HTMLElement | null>(null);
const showScrollButtons = ref(false);
const canScrollLeft = ref(false);
const canScrollRight = ref(false);
let resizeObserver: ResizeObserver | null = null;

// Update scroll button visibility based on scroll position
const updateScrollState = () => {
  const container = metricsScrollContainer.value;
  if (!container) return;

  const { scrollLeft, scrollWidth, clientWidth } = container;
  canScrollLeft.value = scrollLeft > 1;
  canScrollRight.value = scrollLeft < scrollWidth - clientWidth - 1;
};

// Scroll metrics container
const scrollMetrics = (direction: "left" | "right") => {
  const container = metricsScrollContainer.value;
  if (!container) return;

  const scrollAmount = 150;
  const newScrollLeft =
    direction === "left"
      ? container.scrollLeft - scrollAmount
      : container.scrollLeft + scrollAmount;

  container.scrollTo({
    left: newScrollLeft,
    behavior: "smooth",
  });

  // Update state after scroll animation
  setTimeout(updateScrollState, 200);
};

// Computed properties
const taskType = computed(() => {
  return task.value?.parameter?.type || task.value?.type || "unknown";
});

const taskParams = computed(() => {
  const result = task.value?.result;
  return result?.params || null;
});

const taskMetrics = computed((): TuningMetrics | undefined => {
  const result = task.value?.result;
  if (!result?.metrics) return undefined;
  return result.metrics;
});

// Fetch task data
const fetchTask = async () => {
  try {
    const response = await TaskService.fetchStatus(props.taskId);
    if (response.task) {
      task.value = response.task;
    }
  } catch (error) {
    console.error(`Failed to fetch task ${props.taskId}:`, error);
  }
};

// Fetch task logs
const fetchTaskLogs = async () => {
  try {
    const response = await TaskService.fetchLogs(props.taskId);
    if (response.success && response.logs) {
      taskLogs.value = response.logs;
    }
  } catch (error) {
    console.error(`Failed to fetch logs for task ${props.taskId}:`, error);
  }
};

// Event handlers
const handleViewLogs = () => {
  logModalVisible.value = true;
  fetchTaskLogs();
};

const handleViewParams = async () => {
  // Get model name from task parameter
  const modelName = task.value?.parameter?.model;
  if (modelName) {
    try {
      const response = await ModelService.fetchModel(modelName);
      if (response.success && response.model?.paramSchema) {
        paramSchema.value = response.model.paramSchema;
      }
    } catch (error) {
      console.error(`Failed to fetch param schema for ${modelName}:`, error);
    }
  }
  paramsModalVisible.value = true;
};

const formatParamValue = (value: any): string => {
  if (Array.isArray(value)) {
    return `[${value.join(", ")}]`;
  }
  if (typeof value === "object" && value !== null) {
    return JSON.stringify(value);
  }
  return String(value);
};

// Poll for task updates if status is not completed or failed
const pollTask = () => {
  if (
    task.value &&
    (task.value.status === "pending" || task.value.status === "running")
  ) {
    setTimeout(() => {
      fetchTask().then(() => {
        if (
          task.value &&
          (task.value.status === "pending" || task.value.status === "running")
        ) {
          pollTask();
        }
      });
    }, 3000); // Poll every 3 seconds
  }
};

// Watch for taskId changes
watch(
  () => props.taskId,
  () => {
    fetchTask().then(() => {
      pollTask();
    });
  },
  { immediate: true }
);

// Update scroll state when metrics change
watch(taskMetrics, () => {
  nextTick(updateScrollState);
});

// Initialize
onMounted(() => {
  fetchTask().then(() => {
    pollTask();
  });

  // Set up scroll event listener and ResizeObserver for metrics container
  nextTick(() => {
    const container = metricsScrollContainer.value;
    if (container) {
      container.addEventListener("scroll", updateScrollState);

      // Use ResizeObserver to detect when content size changes
      resizeObserver = new ResizeObserver(() => {
        updateScrollState();
      });
      resizeObserver.observe(container);

      // Also observe the inner content if it exists
      const innerContent = container.firstElementChild;
      if (innerContent) {
        resizeObserver.observe(innerContent);
      }

      updateScrollState();
    }
  });
});

onUnmounted(() => {
  const container = metricsScrollContainer.value;
  if (container) {
    container.removeEventListener("scroll", updateScrollState);
  }
  if (resizeObserver) {
    resizeObserver.disconnect();
    resizeObserver = null;
  }
});
</script>

<style scoped>
.params-fallback {
  padding: 12px;
  background-color: #fafafa;
  border-radius: 6px;
}

.param-row {
  padding: 8px 0;
  border-bottom: 1px solid #f0f0f0;
}

.param-row:last-child {
  border-bottom: none;
}

.param-key {
  font-weight: 500;
  color: #6b7280;
  margin-right: 8px;
}

.param-value {
  font-family: monospace;
  color: #111827;
}

.metrics-scroll-wrapper {
  position: relative;
  display: flex;
  align-items: center;
  width: 100%;
  min-width: 0; /* Allow flex child to shrink below content size */
}

.metrics-scroll-container {
  overflow-x: auto;
  scrollbar-width: none; /* Firefox */
  -ms-overflow-style: none; /* IE and Edge */
  flex: 1;
  min-width: 0; /* Allow flex child to shrink below content size */
}

.metrics-scroll-container::-webkit-scrollbar {
  display: none; /* Chrome, Safari, Opera */
}

.scroll-nav-btn {
  position: absolute;
  z-index: 10;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border: none;
  border-radius: 50%;
  background-color: rgba(255, 255, 255, 0.95);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
  cursor: pointer;
  color: #6b7280;
  transition: all 0.2s ease;
}

.scroll-nav-btn:hover {
  background-color: #fff;
  color: #374151;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.2);
}

.scroll-nav-left {
  left: 0;
}

.scroll-nav-right {
  right: 0;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.15s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

.tune-type-tag {
  min-width: 40px;
  text-align: center;
  margin: 0;
}

.status-tag {
  min-width: 40px;
  text-align: center;
  margin: 0;
}

.action-btn {
  min-width: 70px;
  justify-content: center;
}

.metrics-cell {
  max-width: 0; /* Force cell to respect table-fixed layout */
}
</style>
