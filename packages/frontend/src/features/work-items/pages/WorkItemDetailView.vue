<template>
  <default-layout>
    <div class="max-w-7xl mx-auto px-4 py-8">
      <a-breadcrumb class="mb-6">
        <a-breadcrumb-item>
          <router-link to="/">{{ $t("navigation.home") }}</router-link>
        </a-breadcrumb-item>
        <a-breadcrumb-item v-if="workItem">{{
          workItem.name
        }}</a-breadcrumb-item>
      </a-breadcrumb>

      <div v-if="loading" class="text-center py-12">
        <a-spin size="large" />
      </div>

      <div v-else-if="error" class="text-center py-12">
        <a-result
          status="404"
          :title="$t('workItems.notFound')"
          :sub-title="$t('workItems.notFoundDescription')"
        >
          <template #extra>
            <a-button type="primary" @click="router.push('/')">{{
              $t("workItems.backToHome")
            }}</a-button>
          </template>
        </a-result>
      </div>

      <div v-else-if="workItem">
        <div class="mb-8">
          <h1 class="text-3xl font-bold mb-2">{{ workItem.name }}</h1>
          <p v-if="workItem.description" class="text-gray-600 mb-3">
            {{ workItem.description }}
          </p>
          <a-tag :color="getStatusColor(workItem.status)">{{
            workItem.status
          }}</a-tag>
        </div>

        <a-card class="mb-6">
          <h3 class="text-lg font-semibold mb-4">ML Backend Configuration</h3>
          <ml-backend-deployment-selector
            v-model="selectedDeploymentId"
            :dataset-storage="datasetStorage"
            @update:model-value="handleDeploymentChange"
          />
        </a-card>

        <a-card class="mb-6">
          <steps :current="currentStep" :items="stepItems" class="mb-8" />

          <div class="mt-6">
            <div v-if="currentStep === 0">
              <prepare-step
                :work-item="workItem"
                @confirm="handlePrepareConfirm"
              />
            </div>

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
import { computed, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useI18n } from "vue-i18n";

import type { WorkItem } from "@xenix/shared";

import DefaultLayout from "../../common/components/DefaultLayout.vue";
import Steps from "../../common/components/Steps.vue";
import MLBackendDeploymentSelector from "../../common/components/MLBackendDeploymentSelector.vue";
import { useDataset } from "../../datasets/queries";
import { useWorkItem, useUpdateWorkItem } from "../queries";
import PrepareStep from "../../ml/components/prepare/PrepareStep.vue";
import TuningStep from "../../ml/components/tuning/TuningStep.vue";
import PredictionStep from "../../ml/components/prediction/PredictionStep.vue";

const route = useRoute();
const router = useRouter();
const { t } = useI18n();

const stepItems = computed(() => [
  {
    title: t("steps.prepare.title"),
    description: t("steps.prepare.description"),
  },
  { title: t("steps.tune.title"), description: t("steps.tune.description") },
  {
    title: t("steps.predict.title"),
    description: t("steps.predict.description"),
  },
]);

const workItemId = computed(() => Number(route.params.id));
const {
  data: workItemData,
  isLoading: loading,
  error: fetchError,
  refetch,
} = useWorkItem(workItemId.value);

const workItem = computed((): WorkItem | undefined => {
  if (!workItemData.value) return undefined;
  return {
    ...workItemData.value,
    datasetId: workItemData.value.datasetId || undefined,
    featureColumns: (workItemData.value.featureColumns as string[]) || [],
  } as WorkItem;
});
const error = computed(() => !!fetchError.value);

const selectedDeploymentId = ref<number | null>(null);
const { mutate: updateWorkItem } = useUpdateWorkItem();

watch(
  workItem,
  (newWorkItem) => {
    if (newWorkItem && newWorkItem.mlBackendDeploymentId) {
      selectedDeploymentId.value = newWorkItem.mlBackendDeploymentId;
    }
  },
  { immediate: true },
);

const datasetId = computed(() => workItem.value?.datasetId);
const { data: datasetData } = useDataset(datasetId);
const datasetStorage = computed(() => {
  if (!datasetData.value) return null;
  return datasetData.value.storage as "local" | "oss" | null;
});

const handleDeploymentChange = async (deploymentId: number | null) => {
  if (!workItem.value) return;
  try {
    updateWorkItem(
      {
        id: workItem.value.id,
        updates: { mlBackendDeploymentId: deploymentId ?? undefined },
      },
      {
        onSuccess: () => {
          message.success("ML backend deployment updated");
          refetch();
        },
        onError: () => message.error("Failed to update ML backend deployment"),
      },
    );
  } catch (err) {
    message.error("Failed to update ML backend deployment");
  }
};

const currentStep = ref(0);
const selectedModel = ref<string | null>(null);
const selectedParameters = ref<Record<string, any>>({});
const selectedTuningTaskId = ref<number | null>(null);

const checkWorkItemStep = () => {
  if (
    workItem.value?.datasetId &&
    workItem.value?.featureColumns &&
    workItem.value.featureColumns.length > 0 &&
    workItem.value?.targetColumn &&
    workItem.value.targetColumn.trim() !== ""
  ) {
    currentStep.value = 1;
    message.info("Restored saved dataset configuration");
  }
};

watch(
  workItem,
  (newWorkItem) => {
    if (newWorkItem) checkWorkItemStep();
  },
  { immediate: true },
);

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
