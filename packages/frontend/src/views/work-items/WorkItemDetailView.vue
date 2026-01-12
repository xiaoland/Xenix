<template>
  <default-layout>
    <div class="max-w-7xl mx-auto px-4 py-8">
      <!-- Breadcrumb -->
      <a-breadcrumb class="mb-6">
        <a-breadcrumb-item>
          <router-link to="/"> {{ $t("navigation.home") }} </router-link>
        </a-breadcrumb-item>
        <a-breadcrumb-item v-if="workItem">
          {{ workItem.name }}
        </a-breadcrumb-item>
      </a-breadcrumb>

      <!-- Loading State -->
      <div v-if="loading" class="text-center py-12">
        <a-spin size="large" />
      </div>

      <!-- Error State -->
      <div v-else-if="error" class="text-center py-12">
        <a-result
          status="404"
          :title="$t('workItems.notFound')"
          :sub-title="$t('workItems.notFoundDescription')"
        >
          <template #extra>
            <a-button type="primary" @click="router.push('/')">
              {{ $t("workItems.backToHome") }}
            </a-button>
          </template>
        </a-result>
      </div>

      <!-- Work Item Content -->
      <div v-else-if="workItem">
        <!-- Header -->
        <div class="mb-8">
          <h1 class="text-3xl font-bold mb-2">{{ workItem.name }}</h1>
          <p v-if="workItem.description" class="text-gray-600 mb-3">
            {{ workItem.description }}
          </p>
          <a-tag :color="getStatusColor(workItem.status)">
            {{ workItem.status }}
          </a-tag>
        </div>

        <!-- Workflow Steps -->
        <a-card class="mb-6">
          <a-steps :current="currentStep" class="mb-8">
            <a-step
              :title="$t('steps.prepare.title')"
              :description="$t('steps.prepare.description')"
            />
            <a-step
              :title="$t('steps.tune.title')"
              :description="$t('steps.tune.description')"
            />
            <a-step
              :title="$t('steps.predict.title')"
              :description="$t('steps.predict.description')"
            />
          </a-steps>

          <!-- Step Content -->
          <div class="mt-6">
            <!-- Step 0: Prepare -->
            <div v-if="currentStep === 0">
              <prepare-step
                :work-item="workItem"
                @confirm="handlePrepareConfirm"
              />
            </div>

            <!-- Step 1: Tune -->
            <div v-if="currentStep === 1">
              <tuning-step
                :work-item-id="workItem.id"
                :dataset-id="workItem.datasetId || 0"
                :feature-columns="workItem.featureColumns || []"
                :target-column="workItem.targetColumn || ''"
                @continue="handleTuningContinue"
                @back="goToPrepareStep"
              />
            </div>

            <!-- Step 2: Predict -->
            <div v-if="currentStep === 2">
              <prediction-step
                :work-item-id="workItem.id"
                :selected-model="selectedModel"
                :selected-parameters="selectedParameters"
                :task-id="selectedTuningTaskId"
                :feature-columns="workItem.featureColumns || []"
                @back="goToTuningStep"
                @reset="resetWorkflow"
              />
            </div>
          </div>
        </a-card>
      </div>
    </div>
  </default-layout>
</template>

<script setup lang="ts">
import { message } from "ant-design-vue";

import { computed, ref } from "vue";
import { useRoute, useRouter } from "vue-router";

import type { WorkItem } from "@xenix/shared";

import PredictionStep from "../../components/ml/prediction/PredictionStep.vue";
import PrepareStep from "../../components/ml/prepare/PrepareStep.vue";
import TuningStep from "../../components/ml/tuning/TuningStep.vue";
import { useWorkItem } from "../../composables";
import DefaultLayout from "../../layouts/DefaultLayout.vue";

const route = useRoute();
const router = useRouter();

// Use composable for fetching work item
const workItemId = computed(() => Number(route.params.id));
const {
  data: workItemData,
  isLoading: loading,
  error: fetchError,
  refetch,
} = useWorkItem(workItemId.value);

// Computed property to safely access work item
const workItem = computed((): WorkItem | undefined => {
  if (!workItemData.value) return undefined;
  return {
    ...workItemData.value,
    datasetId: workItemData.value.datasetId || undefined,
    featureColumns: (workItemData.value.featureColumns as string[]) || [],
  } as WorkItem;
});
const error = computed(() => !!fetchError.value);

// Workflow state
const currentStep = ref(0);
const selectedModel = ref<string | null>(null);
const selectedParameters = ref<Record<string, any>>({});
const selectedTuningTaskId = ref<number | null>(null);

// Check if work item has saved prepare data and auto-advance
const checkWorkItemStep = () => {
  if (
    workItem.value?.datasetId &&
    workItem.value?.featureColumns &&
    workItem.value?.targetColumn
  ) {
    // Skip to tuning step
    currentStep.value = 1;
    message.info("Restored saved dataset configuration");
  }
};

// Watch for work item data and check step
if (workItem.value) {
  checkWorkItemStep();
}

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

const handlePrepareConfirm = () => {
  currentStep.value = 1;
  // Refresh work item to get updated data
  refetch();
};

const handleTuningContinue = (data: {
  model: string;
  parameters: Record<string, any>;
  taskId: number;
}) => {
  selectedModel.value = data.model;
  selectedParameters.value = data.parameters;
  selectedTuningTaskId.value = data.taskId;
  currentStep.value = 2;
};

const goToPrepareStep = () => {
  currentStep.value = 0;
};

const goToTuningStep = () => {
  currentStep.value = 1;
};

const resetWorkflow = () => {
  currentStep.value = 0;
  selectedModel.value = null;
  selectedParameters.value = {};
  selectedTuningTaskId.value = null;
};
</script>
