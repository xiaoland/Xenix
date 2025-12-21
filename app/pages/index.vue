<template>
  <div class="min-h-screen bg-gray-50 py-8">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
      <div class="text-center mb-8">
        <h1 class="text-4xl font-bold text-gray-900 mb-2">Xenix</h1>
        <p class="text-lg text-gray-600">
          Machine Learning Model Training and Prediction Platform
        </p>
      </div>

      <a-card class="mb-6">
        <a-steps :current="currentStep" class="mb-8">
          <a-step
            title="Upload & Train"
            description="Upload data and tune models"
          />
          <a-step
            title="Predict"
            description="Select model and make predictions"
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

          <!-- Training Section (shown after upload) -->
          <TrainingStep
            v-else
            v-model:selected-models="selectedModels"
            v-model:active-log-tab="activeLogTab"
            v-model:selected-best-model="selectedBestModel"
            :available-models="availableModels"
            :tuning-status="tuningStatus"
            :tuning-tasks="tuningTasks"
            :is-tuning="isTuning"
            :tuning-results="tuningResults"
            :task-logs="taskLogs"
            @start-tuning="startTuning"
            @start-single-tune="startSingleModelTuning"
            @continue="nextStep"
            @back="resetUpload"
          />
        </div>

        <!-- Step 2: Prediction -->
        <PredictionStep
          v-if="currentStep === 1"
          v-model="predictionFileList"
          :best-model="selectedBestModel"
          :is-predicting="isPredicting"
          :prediction-task="predictionTask"
          @predict="startPrediction"
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

const currentStep = ref(0);
const trainingFileList = ref([]);
const predictionFileList = ref([]);
const hasUploadedData = ref(false);

// Available regression models
const availableModels = [
  {
    label: "Linear Regression",
    value: "Linear_Regression_Hyperparameter_Tuning",
  },
  { label: "Ridge", value: "Ridge" },
  { label: "Lasso", value: "Lasso" },
  { label: "Bayesian Ridge", value: "Bayesian_Ridge_Regression" },
  { label: "KNN", value: "K-Nearest_Neighbors" },
  { label: "Decision Tree", value: "Regression_Decision_Tree" },
  { label: "Random Forest", value: "Random_Forest" },
  { label: "GBDT", value: "GBDT" },
  { label: "AdaBoost", value: "AdaBoost" },
  { label: "XGBoost", value: "XGBoost" },
  { label: "LightGBM", value: "LightGBM" },
  { label: "Polynomial", value: "Polynomial_Regression" },
];

const selectedModels = ref<string[]>([]);
const tuningStatus = ref<Record<string, string>>({});
const tuningTasks = ref<Record<string, string>>({});
const tuningResults = ref<any[]>([]);
const uploadedFilePath = ref<string>("");
const selectedFeatureColumns = ref<string[]>([]);
const selectedTargetColumn = ref<string>("");
const isTuning = ref(false);
const isPredicting = ref(false);
const selectedBestModel = ref<string | null>(null);
const predictionTask = ref<any>(null);

// Logs state
const taskLogs = ref<Record<string, any[]>>({});
const activeLogTab = ref<string>("");

const fetchTaskLogs = async (taskId: string) => {
  try {
    const response = await $fetch(`/api/obsrv/${taskId}`);
    if (response.success) {
      taskLogs.value[taskId] = response.logs.reverse();
    }
  } catch (error) {
    console.error(`Failed to fetch logs for ${taskId}:`, error);
  }
};

const pollTaskLogs = (taskId: string) => {
  fetchTaskLogs(taskId);

  const interval = setInterval(async () => {
    await fetchTaskLogs(taskId);

    const isComplete = Object.values(tuningStatus.value).every(
      (status) => status === "completed" || status === "failed"
    );
    if (isComplete) {
      clearInterval(interval);
    }
  }, 3000);
};

const handleColumnSelection = ({
  featureColumns,
  targetColumn,
}: {
  featureColumns: string[];
  targetColumn: string;
}) => {
  selectedFeatureColumns.value = featureColumns;
  selectedTargetColumn.value = targetColumn;
  hasUploadedData.value = true;
  message.success(`Ready to train with ${featureColumns.length} features`);
};

const resetUpload = () => {
  hasUploadedData.value = false;
  trainingFileList.value = [];
  selectedModels.value = [];
  selectedFeatureColumns.value = [];
  selectedTargetColumn.value = "";
  tuningStatus.value = {};
  tuningTasks.value = {};
  tuningResults.value = [];
  selectedBestModel.value = null;
};

const startTuning = async () => {
  if (trainingFileList.value.length === 0) {
    message.error("Please upload training data first");
    return;
  }

  if (
    selectedFeatureColumns.value.length === 0 ||
    !selectedTargetColumn.value
  ) {
    message.error("Please select feature columns and target column");
    return;
  }

  isTuning.value = true;

  try {
    for (const modelValue of selectedModels.value) {
      tuningStatus.value[modelValue] = "pending";

      const formData = new FormData();
      formData.append("file", trainingFileList.value[0].originFileObj);
      formData.append("model", modelValue);
      formData.append(
        "featureColumns",
        JSON.stringify(selectedFeatureColumns.value)
      );
      formData.append("targetColumn", selectedTargetColumn.value);

      const response = await $fetch("/api/upload", {
        method: "POST",
        body: formData,
      });

      if (response.success) {
        tuningTasks.value[modelValue] = response.taskId;
        tuningStatus.value[modelValue] = "running";
        activeLogTab.value = response.taskId;

        if (!uploadedFilePath.value && response.inputFile) {
          uploadedFilePath.value = response.inputFile;
        }

        pollTaskStatus(response.taskId, modelValue);
        pollTaskLogs(response.taskId);
      }
    }

    message.success("Hyperparameter tuning started for selected models");
  } catch (error) {
    message.error("Failed to start tuning: " + error.message);
  } finally {
    isTuning.value = false;
  }
};

const startSingleModelTuning = async (modelValue: string) => {
  if (trainingFileList.value.length === 0) {
    message.error("Please upload training data first");
    return;
  }

  if (
    selectedFeatureColumns.value.length === 0 ||
    !selectedTargetColumn.value
  ) {
    message.error("Please select feature columns and target column");
    return;
  }

  isTuning.value = true;
  tuningStatus.value[modelValue] = "pending";

  try {
    const formData = new FormData();
    formData.append("file", trainingFileList.value[0].originFileObj);
    formData.append("model", modelValue);
    formData.append(
      "featureColumns",
      JSON.stringify(selectedFeatureColumns.value)
    );
    formData.append("targetColumn", selectedTargetColumn.value);

    const response = await $fetch("/api/upload", {
      method: "POST",
      body: formData,
    });

    if (response.success) {
      tuningTasks.value[modelValue] = response.taskId;
      tuningStatus.value[modelValue] = "running";
      activeLogTab.value = response.taskId;

      if (!uploadedFilePath.value && response.inputFile) {
        uploadedFilePath.value = response.inputFile;
      }

      pollTaskStatus(response.taskId, modelValue);
      pollTaskLogs(response.taskId);

      message.success(
        `Hyperparameter tuning started for ${modelValue.replace(/_/g, " ")}`
      );
    }
  } catch (error) {
    message.error("Failed to start tuning: " + error.message);
    tuningStatus.value[modelValue] = "failed";
  } finally {
    isTuning.value = false;
  }
};

const pollTaskStatus = async (taskId: string, modelValue?: string) => {
  const maxAttempts = 120;
  let attempts = 0;

  const poll = async () => {
    try {
      const response = await $fetch(`/api/task/${taskId}`);

      if (
        modelValue &&
        response.task.status !== tuningStatus.value[modelValue]
      ) {
        tuningStatus.value[modelValue] = response.task.status;
      }

      if (response.task.status === "completed") {
        await fetchTuningResults();
        return response;
      }

      if (response.task.status === "failed") {
        return response;
      }

      attempts++;
      if (attempts < maxAttempts) {
        setTimeout(poll, 5000);
      }
    } catch (error) {
      console.error("Failed to poll task status:", error);
    }
  };

  return poll();
};

const fetchTuningResults = async () => {
  try {
    const taskIds = Object.values(tuningTasks.value);
    const results = await Promise.all(
      taskIds.map((taskId) =>
        $fetch(`/api/results/${taskId}`).catch(() => null)
      )
    );

    const validResults = results
      .filter((r) => r !== null && r.success && r.results)
      .map((r) => ({
        ...r.results,
        status:
          tuningStatus.value[
            Object.keys(tuningTasks.value).find(
              (k) => tuningTasks.value[k] === r.results.taskId
            ) || ""
          ] || "completed",
      }));

    tuningResults.value = validResults;
  } catch (error) {
    console.error("Failed to fetch tuning results:", error);
  }
};

const startPrediction = async () => {
  if (!selectedBestModel.value) {
    message.error("Please select a model from the tuning results first");
    return;
  }

  if (predictionFileList.value.length === 0) {
    message.error("Please upload prediction data");
    return;
  }

  if (!uploadedFilePath.value) {
    message.error("Training data path not found. Please retrain models first.");
    return;
  }

  // Find the task ID for the selected model
  const selectedModelTaskId = tuningTasks.value[selectedBestModel.value];
  if (!selectedModelTaskId) {
    message.error(
      "Could not find tuning task for selected model. Please retrain."
    );
    return;
  }

  isPredicting.value = true;

  try {
    const formData = new FormData();
    formData.append("file", predictionFileList.value[0].originFileObj);
    formData.append("model", selectedBestModel.value);
    formData.append("tuningTaskId", selectedModelTaskId);
    formData.append("trainingDataPath", uploadedFilePath.value);
    formData.append(
      "featureColumns",
      JSON.stringify(selectedFeatureColumns.value)
    );
    formData.append("targetColumn", selectedTargetColumn.value);

    const response = await $fetch("/api/predict", {
      method: "POST",
      body: formData,
    });

    if (response.success) {
      predictionTask.value = { taskId: response.taskId, status: "running" };
      message.success("Prediction started");

      const result = await pollTaskStatus(response.taskId);
      if (result && result.task.status === "completed") {
        predictionTask.value.status = "completed";
        predictionTask.value.outputFile = response.outputFile;
        message.success(
          "Prediction completed! Results saved to: " + response.outputFile
        );
      } else if (result && result.task.status === "failed") {
        predictionTask.value.status = "failed";
        predictionTask.value.error = result.task.error;
        message.error("Prediction failed: " + result.task.error);
      }
    }
  } catch (error) {
    message.error("Failed to start prediction: " + error.message);
  } finally {
    isPredicting.value = false;
  }
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
  tuningStatus.value = {};
  tuningTasks.value = {};
  tuningResults.value = [];
  uploadedFilePath.value = "";
  isTuning.value = false;
  isPredicting.value = false;
  selectedBestModel.value = null;
  predictionTask.value = null;
  taskLogs.value = {};
  activeLogTab.value = "";
};
</script>
