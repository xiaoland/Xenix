<template>
  <div class="min-h-screen bg-gray-50 py-8 overflow-x-hidden">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
      <PageHeader />

      <div class="text-center mb-4">
        <a-breadcrumb>
          <a-breadcrumb-item>
            <NuxtLink to="/">{{ $t("navigation.home") }}</NuxtLink>
          </a-breadcrumb-item>
          <a-breadcrumb-item v-if="workItem">
            {{ workItem.name }}
          </a-breadcrumb-item>
        </a-breadcrumb>
      </div>

      <div v-if="isLoading" class="text-center py-8">
        <a-spin size="large" />
      </div>

      <div v-else-if="!workItem" class="text-center py-8">
        <a-result
          status="404"
          :title="$t('workItems.fetchError')"
          :sub-title="$t('workItems.fetchError')"
        >
          <template #extra>
            <a-button type="primary" @click="$router.push('/')">
              {{ $t("navigation.home") }}
            </a-button>
          </template>
        </a-result>
      </div>

      <div v-else>
        <div class="text-center mb-8">
          <h1 class="text-4xl font-bold text-gray-900 mb-2">
            {{ workItem.name }}
          </h1>
          <p class="text-lg text-gray-600" v-if="workItem.description">
            {{ workItem.description }}
          </p>
          <div class="mt-2">
            <a-tag :color="getStatusColor(workItem.status)">
              {{ $t(`workItems.${workItem.status}`) }}
            </a-tag>
          </div>
        </div>

        <a-card class="mb-6">
          <Steps
            :current="currentStep"
            class="mb-8"
            :items="[
              {
                title: $t('steps.prepare.title'),
                description: $t('steps.prepare.description'),
              },
              {
                title: $t('steps.tune.title'),
                description: $t('steps.tune.description'),
              },
              {
                title: $t('steps.predict.title'),
                description: $t('steps.predict.description'),
              },
            ]"
          />

          <!-- Step 0: Prepare (Dataset + Columns) -->
          <div v-if="currentStep === 0">
            <PrepareStep
              :work-item-id="workItem.id"
              @confirm="handlePrepareConfirm"
            />
          </div>

          <!-- Step 1: Tuning -->
          <div v-if="currentStep === 1">
            <TuningStep
              :work-item-id="workItem.id"
              @continue="handleTuningContinue"
              @back="goToUploadStep"
            />
          </div>

          <!-- Step 2: Prediction -->
          <div
            v-if="currentStep === 2 && selectedModel && selectedTuningTaskId"
          >
            <PredictionStep
              :work-item-id="workItem.id"
              :model="selectedModel"
              :parameters="selectedParameters"
              :task-id="selectedTuningTaskId"
              :feature-columns="workItem.featureColumns || []"
              :target-column="workItem.targetColumn || ''"
              @back="prevStep"
              @reset="reset"
            />
          </div>
        </a-card>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from "vue";
import { useRoute } from "vue-router";
import { message } from "ant-design-vue";
import { useI18n } from "vue-i18n";
import { useDatasetRegistration } from "../../composables/useDatasetRegistration";
import { WorkItemService } from "../../services";
import PrepareStep from "~/components/ml/prepare/PrepareStep.vue";
import TuningStep from "~/components/ml/tuning/TuningStep.vue";
import PredictionStep from "~/components/ml/prediction/PredictionStep.vue";
import PageHeader from "~/components/common/PageHeader.vue";
import Steps from "~/components/common/Steps.vue";
import type { WorkItem } from "../../types";

const { t } = useI18n();
const route = useRoute();

// Work item data
const workItem = ref<WorkItem | null>(null);
const isLoading = ref(false);

// Dataset registration
const { uploadedDatasetId, clearDatasetId } = useDatasetRegistration();

// Workflow state
const currentStep = ref(0);

// Tuning step data - passed to PredictionStep
const selectedModel = ref<string | null>(null);
const selectedParameters = ref<Record<string, any>>({});
const selectedTuningTaskId = ref<number | null>(null);

// Navigation
const nextStep = () => {
  if (currentStep.value < 2) {
    currentStep.value = currentStep.value + 1;
  }
};

const prevStep = () => {
  if (currentStep.value > 0) {
    currentStep.value--;
  }
};

// Reset all state
const resetAll = () => {
  currentStep.value = 0;
  selectedModel.value = null;
  selectedParameters.value = {};
  selectedTuningTaskId.value = null;
};

// Current dataset columns for prepare step
const currentDatasetColumns = ref<string[]>([]);
const currentDatasetId = ref<number | undefined>(undefined);

const resetPrepareStep = () => {
  currentDatasetColumns.value = [];
  currentDatasetId.value = undefined;
};

/**
 * Handle prepare step confirmation
 */
const handlePrepareConfirm = async () => {
  nextStep();
};

const goToUploadStep = () => {
  currentStep.value = 0;
  currentDatasetColumns.value = [];
  currentDatasetId.value = undefined;
};

/**
 * Handle tuning continue - receives model and parameters from TuningStep
 */
const handleTuningContinue = (data: {
  model: string;
  parameters: Record<string, any>;
  taskId: number;
}) => {
  selectedModel.value = data.model;
  selectedParameters.value = data.parameters;
  selectedTuningTaskId.value = data.taskId;
  nextStep();
};

const reset = () => {
  resetAll();
  clearDatasetId();
  resetPrepareStep();
};

const fetchWorkItem = async () => {
  const workItemId = route.params.id as string;
  if (!workItemId) return;

  isLoading.value = true;
  try {
    const response = await WorkItemService.fetchById(workItemId);
    if (response.success) {
      workItem.value = response.workItem;

      // Check if work item has saved upload data
      if (
        workItem.value.datasetId &&
        workItem.value.featureColumns &&
        workItem.value.targetColumn
      ) {
        // Restore upload data
        uploadedDatasetId.value = String(workItem.value.datasetId);

        // Skip upload step, go directly to tuning
        currentStep.value = 1;

        message.info(t("messages.uploadDataRestored"));
      } else {
        // Start from upload step
        currentStep.value = 0;
      }
    }
  } catch (error) {
    console.error("Failed to fetch work item:", error);
    message.error(t("workItems.fetchError"));
  } finally {
    isLoading.value = false;
  }
};

const getStatusColor = (status: string) => {
  switch (status) {
    case "active":
      return "green";
    case "completed":
      return "blue";
    case "archived":
      return "gray";
    default:
      return "default";
  }
};

onMounted(() => {
  fetchWorkItem();
});
</script>
