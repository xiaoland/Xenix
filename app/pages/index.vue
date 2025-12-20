<template>
  <div class="min-h-screen bg-gray-50 py-8">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
      <div class="text-center mb-8">
        <h1 class="text-4xl font-bold text-gray-900 mb-2">Xenix</h1>
        <p class="text-lg text-gray-600">Machine Learning Model Training and Prediction Platform</p>
      </div>

      <a-card class="mb-6">
        <a-steps :current="currentStep" class="mb-8">
          <a-step title="Upload Data" description="Upload training data" />
          <a-step title="Train Models" description="Tune and compare models" />
          <a-step title="Predict" description="Make predictions" />
        </a-steps>

        <!-- Step 1: Upload Training Data -->
        <UploadStep
          v-if="currentStep === 0"
          v-model="trainingFileList"
          @continue="nextStep"
        />

        <!-- Step 2: Model Training -->
        <TrainingStep
          v-if="currentStep === 1"
          v-model:selected-models="selectedModels"
          v-model:active-log-tab="activeLogTab"
          :available-models="availableModels"
          :tuning-status="tuningStatus"
          :tuning-tasks="tuningTasks"
          :is-tuning="isTuning"
          :is-comparing="isComparing"
          :comparison-results="comparisonResults"
          :comparison-task-id="comparisonTaskId"
          :task-logs="taskLogs"
          @start-tuning="startTuning"
          @start-comparison="startComparison"
          @back="prevStep"
          @continue="nextStep"
        />

        <!-- Step 3: Prediction -->
        <PredictionStep
          v-if="currentStep === 2"
          v-model="predictionFileList"
          :best-model="comparisonResults?.bestModel"
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
import { ref, computed } from 'vue';
import { message } from 'ant-design-vue';

const currentStep = ref(0);
const trainingFileList = ref([]);
const predictionFileList = ref([]);

// Available regression models
const availableModels = [
  { label: 'Linear Regression', value: 'Linear_Regression_Hyperparameter_Tuning' },
  { label: 'Ridge', value: 'Ridge' },
  { label: 'Lasso', value: 'Lasso' },
  { label: 'Bayesian Ridge', value: 'Bayesian_Ridge_Regression' },
  { label: 'KNN', value: 'K-Nearest_Neighbors' },
  { label: 'Decision Tree', value: 'Regression_Decision_Tree' },
  { label: 'Random Forest', value: 'Random_Forest' },
  { label: 'GBDT', value: 'GBDT' },
  { label: 'AdaBoost', value: 'AdaBoost' },
  { label: 'XGBoost', value: 'XGBoost' },
  { label: 'LightGBM', value: 'LightGBM' },
  { label: 'Polynomial', value: 'Polynomial_Regression' },
];

const selectedModels = ref<string[]>([]);
const tuningStatus = ref<Record<string, string>>({});
const tuningTasks = ref<Record<string, string>>({});
const isTuning = ref(false);
const isComparing = ref(false);
const isPredicting = ref(false);
const comparisonResults = ref<any>(null);
const comparisonTaskId = ref<string | null>(null);
const predictionTask = ref<any>(null);

// Logs state
const taskLogs = ref<Record<string, any[]>>({});
const activeLogTab = ref<string>('');

const fetchTaskLogs = async (taskId: string) => {
  try {
    const response = await $fetch(`/api/logs/${taskId}`);
    if (response.success) {
      // Reverse to show newest first
      taskLogs.value[taskId] = response.logs.reverse();
    }
  } catch (error) {
    console.error(`Failed to fetch logs for ${taskId}:`, error);
  }
};

const pollTaskLogs = (taskId: string) => {
  // Initial fetch
  fetchTaskLogs(taskId);
  
  // Poll every 3 seconds
  const interval = setInterval(async () => {
    await fetchTaskLogs(taskId);
    
    // Stop polling if task is complete
    const isComplete = Object.values(tuningStatus.value).every(
      status => status === 'completed' || status === 'failed'
    );
    if (comparisonTaskId.value) {
      const comparisonComplete = await $fetch(`/api/task/${comparisonTaskId.value}`)
        .then(r => r.task.status === 'completed' || r.task.status === 'failed')
        .catch(() => true);
      if (isComplete && comparisonComplete) {
        clearInterval(interval);
      }
    } else if (isComplete) {
      clearInterval(interval);
    }
  }, 3000);
};

const startTuning = async () => {
  if (trainingFileList.value.length === 0) {
    message.error('Please upload training data first');
    return;
  }

  isTuning.value = true;
  
  try {
    for (const modelValue of selectedModels.value) {
      tuningStatus.value[modelValue] = 'pending';
      
      const formData = new FormData();
      formData.append('file', trainingFileList.value[0].originFileObj);
      formData.append('model', modelValue);

      const response = await $fetch('/api/upload', {
        method: 'POST',
        body: formData,
      });

      if (response.success) {
        tuningTasks.value[modelValue] = response.taskId;
        tuningStatus.value[modelValue] = 'running';
        activeLogTab.value = response.taskId; // Set first task as active
        pollTaskStatus(response.taskId, modelValue);
        pollTaskLogs(response.taskId); // Start polling logs
      }
    }
    
    message.success('Hyperparameter tuning started for selected models');
  } catch (error) {
    message.error('Failed to start tuning: ' + error.message);
  } finally {
    isTuning.value = false;
  }
};

const pollTaskStatus = async (taskId: string, modelValue?: string) => {
  const maxAttempts = 120; // 10 minutes with 5-second intervals
  let attempts = 0;

  const poll = async () => {
    try {
      const response = await $fetch(`/api/task/${taskId}`);
      
      if (modelValue && response.task.status !== tuningStatus.value[modelValue]) {
        tuningStatus.value[modelValue] = response.task.status;
      }

      if (response.task.status === 'completed' || response.task.status === 'failed') {
        return response;
      }

      attempts++;
      if (attempts < maxAttempts) {
        setTimeout(poll, 5000); // Poll every 5 seconds
      }
    } catch (error) {
      console.error('Failed to poll task status:', error);
    }
  };

  return poll();
};

const startComparison = async () => {
  isComparing.value = true;
  
  try {
    const response = await $fetch('/api/compare', {
      method: 'POST',
    });

    if (response.success) {
      comparisonTaskId.value = response.taskId;
      activeLogTab.value = 'comparison'; // Switch to comparison tab
      message.success('Model comparison started');
      
      // Start polling logs for comparison task
      pollTaskLogs(response.taskId);
      
      // Poll for results
      const result = await pollComparisonStatus(response.taskId);
      if (result && result.results) {
        comparisonResults.value = result.results;
      }
    }
  } catch (error) {
    message.error('Failed to start comparison: ' + error.message);
  } finally {
    isComparing.value = false;
  }
};

const pollComparisonStatus = async (taskId: string) => {
  const maxAttempts = 60;
  let attempts = 0;

  const poll = async (): Promise<any> => {
    try {
      const response = await $fetch(`/api/task/${taskId}`);

      if (response.task.status === 'completed') {
        return response.results;
      }

      if (response.task.status === 'failed') {
        message.error('Comparison failed: ' + response.task.error);
        return null;
      }

      attempts++;
      if (attempts < maxAttempts) {
        await new Promise(resolve => setTimeout(resolve, 5000));
        return poll();
      }
    } catch (error) {
      console.error('Failed to poll comparison status:', error);
    }
    return null;
  };

  return poll();
};

const startPrediction = async () => {
  if (!comparisonResults.value || !comparisonResults.value.bestModel) {
    message.error('Please complete model comparison first');
    return;
  }

  isPredicting.value = true;
  
  try {
    const formData = new FormData();
    formData.append('file', predictionFileList.value[0].originFileObj);
    formData.append('model', comparisonResults.value.bestModel);

    const response = await $fetch('/api/predict', {
      method: 'POST',
      body: formData,
    });

    if (response.success) {
      message.success('Prediction started');
      predictionTask.value = { status: 'running' };
      
      // Poll for results
      await pollPredictionStatus(response.taskId);
    }
  } catch (error) {
    message.error('Failed to start prediction: ' + error.message);
  } finally {
    isPredicting.value = false;
  }
};

const pollPredictionStatus = async (taskId: string) => {
  const maxAttempts = 60;
  let attempts = 0;

  const poll = async () => {
    try {
      const response = await $fetch(`/api/task/${taskId}`);
      predictionTask.value = response.task;

      if (response.task.status !== 'completed' && response.task.status !== 'failed') {
        attempts++;
        if (attempts < maxAttempts) {
          setTimeout(poll, 5000);
        }
      }
    } catch (error) {
      console.error('Failed to poll prediction status:', error);
    }
  };

  return poll();
};

const nextStep = () => {
  if (currentStep.value < 2) {
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
  selectedModels.value = [];
  tuningStatus.value = {};
  tuningTasks.value = {};
  comparisonResults.value = null;
  predictionTask.value = null;
};
</script>
