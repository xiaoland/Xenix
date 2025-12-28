<template>
  <div class="min-h-screen bg-gray-50 py-8">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
      <PageHeader />

      <div class="text-center mb-8">
        <h1 class="text-4xl font-bold text-gray-900 mb-2">
          {{ $t("app.title") }}
        </h1>
        <p class="text-lg text-gray-600">
          {{ $t("app.subtitle") }}
        </p>
      </div>

      <a-card class="mb-6">
        <a-steps :current="currentStep" class="mb-8">
          <a-step
            :title="$t('steps.uploadTrain.title')"
            :description="$t('steps.uploadTrain.description')"
          />
          <a-step
            :title="$t('steps.predict.title')"
            :description="$t('steps.predict.description')"
          />
        </a-steps>

        <!-- Step 1: Upload & Train -->
        <div v-if="currentStep === 0">
          <!-- Upload Section (shown first) -->
          <UploadStep
            v-if="!hasUploadedData"
            v-model="trainingFileList"
            @continue="handleColumnSelection"
          />

          <!-- Tuning Section (shown after upload) -->
          <TuningStep
            v-else
            v-model:selected-models="selectedModels"
            v-model:active-log-tab="activeLogTab"
            v-model:selected-best-model="selectedBestModel"
            v-model:selected-task-id="selectedTaskId"
            v-model:tuning-status="tuningStatus"
            v-model:tuning-tasks="tuningTasks"
            v-model:tuning-results="tuningResults"
            v-model:is-tuning="isTuning"
            :available-models="availableModels"
            :task-logs="taskLogs"
            :uploaded-dataset-id="uploadedDatasetId"
            :feature-columns="selectedFeatureColumns"
            :target-column="selectedTargetColumn"
            @continue="nextStep"
            @back="resetUpload"
          />
        </div>

        <!-- Step 2: Prediction -->
        <PredictionStep
          v-if="currentStep === 1"
          v-model="predictionFileList"
          v-model:is-predicting="isPredicting"
          v-model:prediction-task="predictionTask"
          :best-model="selectedBestModel"
          :selected-task-id="selectedTaskId"
          :training-dataset-id="uploadedDatasetId"
          :feature-columns="selectedFeatureColumns"
          :target-column="selectedTargetColumn"
          @back="prevStep"
          @reset="reset"
        />
      </a-card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from "vue";
import { message } from "ant-design-vue";
import { useI18n } from "vue-i18n";

const { t } = useI18n();

const currentStep = ref(0);
const trainingFileList = ref([]);
const predictionFileList = ref([]);
const hasUploadedData = ref(false);

// Available regression models
const availableModels = [
  {
    label: "Linear Regression",
    value: "regression.linear_regression_hyperparameter_tuning",
  },
  { label: "Ridge", value: "regression.ridge" },
  { label: "Lasso", value: "regression.lasso" },
  { label: "Bayesian Ridge", value: "regression.bayesian_ridge_regression" },
  { label: "KNN", value: "regression.k_nearest_neighbors" },
  { label: "Decision Tree", value: "regression.regression_decision_tree" },
  { label: "Random Forest", value: "regression.random_forest" },
  { label: "GBDT", value: "regression.gbdt" },
  { label: "AdaBoost", value: "regression.adaboost" },
  { label: "XGBoost", value: "regression.xgboost" },
  { label: "LightGBM", value: "regression.lightgbm" },
  { label: "Polynomial", value: "regression.polynomial_regression" },
];

const selectedModels = ref<string[]>([]);
const tuningStatus = ref<Record<string, string>>({});
const tuningTasks = ref<Record<string, number>>({});
const tuningResults = ref<any[]>([]);
const uploadedFilePath = ref<string>("");
const uploadedDatasetId = ref<string>("");
const selectedFeatureColumns = ref<string[]>([]);
const selectedTargetColumn = ref<string>("");
const isTuning = ref(false);
const isPredicting = ref(false);
const selectedBestModel = ref<string | null>(null);
const selectedTaskId = ref<number | null>(null);
const predictionTask = ref<any>(null);

// Logs state
const taskLogs = ref<Record<string, any[]>>({});
const activeLogTab = ref<string>("");

const handleColumnSelection = ({
  featureColumns,
  targetColumn,
  datasetId,
}: {
  featureColumns: string[];
  targetColumn: string;
  datasetId?: string;
}) => {
  selectedFeatureColumns.value = featureColumns;
  selectedTargetColumn.value = targetColumn;
  uploadedDatasetId.value = datasetId || "";
  hasUploadedData.value = true;
  message.success(t("messages.readyToTrain", { count: featureColumns.length }));
};

const resetUpload = () => {
  hasUploadedData.value = false;
  trainingFileList.value = [];
  selectedModels.value = [];
  selectedFeatureColumns.value = [];
  selectedTargetColumn.value = "";
  uploadedDatasetId.value = "";
  tuningStatus.value = {};
  tuningTasks.value = {};
  tuningResults.value = [];
  selectedBestModel.value = null;
  selectedTaskId.value = null;
};

const nextStep = () => {
  if (currentStep.value < 1) {
    currentStep.value++;
  }
};

const prevStep = () => {
  if (currentStep.value > 0) {
    currentStep.value--;
  }
};

const reset = () => {
  currentStep.value = 0;
  trainingFileList.value = [];
  predictionFileList.value = [];
  hasUploadedData.value = false;
  selectedModels.value = [];
  selectedFeatureColumns.value = [];
  selectedTargetColumn.value = "";
  uploadedDatasetId.value = "";
  tuningStatus.value = {};
  tuningTasks.value = {};
  tuningResults.value = [];
  uploadedFilePath.value = "";
  isTuning.value = false;
  isPredicting.value = false;
  selectedBestModel.value = null;
  selectedTaskId.value = null;
  predictionTask.value = null;
  taskLogs.value = {};
  activeLogTab.value = "";
};
</script>
