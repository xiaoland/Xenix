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
        <div v-if="currentStep === 0" class="space-y-4">
          <h2 class="text-2xl font-semibold mb-4">Upload Training Data</h2>
          
          <a-upload-dragger
            v-model:file-list="trainingFileList"
            name="file"
            :before-upload="beforeUpload"
            :max-count="1"
            accept=".xlsx,.xls"
          >
            <p class="ant-upload-drag-icon">
              <i class="i-mdi-cloud-upload text-6xl text-blue-500"></i>
            </p>
            <p class="ant-upload-text">Click or drag file to upload training data</p>
            <p class="ant-upload-hint">
              Support for Excel files (.xlsx, .xls). Data should contain features and target variable.
            </p>
          </a-upload-dragger>

          <a-button 
            type="primary" 
            size="large" 
            block
            :disabled="trainingFileList.length === 0"
            @click="nextStep"
          >
            Continue to Model Training
          </a-button>
        </div>

        <!-- Step 2: Model Training -->
        <div v-if="currentStep === 1" class="space-y-6">
          <h2 class="text-2xl font-semibold mb-4">Model Training & Comparison</h2>

          <!-- Available Models -->
          <div>
            <h3 class="text-lg font-medium mb-3">Available Models for Tuning</h3>
            <div class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
              <a-button
                v-for="model in availableModels"
                :key="model.value"
                :type="selectedModels.includes(model.value) ? 'primary' : 'default'"
                @click="toggleModel(model.value)"
                class="h-auto py-3"
              >
                <div class="text-center">
                  <div class="font-medium">{{ model.label }}</div>
                  <div v-if="tuningStatus[model.value]" class="text-xs mt-1">
                    <a-tag :color="getStatusColor(tuningStatus[model.value])">
                      {{ tuningStatus[model.value] }}
                    </a-tag>
                  </div>
                </div>
              </a-button>
            </div>
          </div>

          <!-- Tuning Actions -->
          <div class="flex gap-4">
            <a-button
              type="primary"
              size="large"
              :loading="isTuning"
              :disabled="selectedModels.length === 0"
              @click="startTuning"
            >
              <i class="i-mdi-tune mr-2"></i>
              Start Hyperparameter Tuning
            </a-button>

            <a-button
              type="default"
              size="large"
              :loading="isComparing"
              :disabled="!canCompare"
              @click="startComparison"
            >
              <i class="i-mdi-compare mr-2"></i>
              Compare All Models
            </a-button>
          </div>

          <!-- Comparison Results -->
          <div v-if="comparisonResults" class="mt-6">
            <h3 class="text-lg font-medium mb-3">Model Comparison Results</h3>
            <a-table
              :columns="comparisonColumns"
              :data-source="comparisonResults.results"
              :pagination="false"
              bordered
              size="small"
            >
              <template #bodyCell="{ column, record }">
                <template v-if="column.key === 'Model'">
                  <a-tag v-if="record.Model === comparisonResults.bestModel" color="green">
                    {{ record.Model }} ⭐
                  </a-tag>
                  <span v-else>{{ record.Model }}</span>
                </template>
              </template>
            </a-table>
          </div>

          <!-- Navigation -->
          <div class="flex gap-4 mt-6">
            <a-button @click="prevStep">Back</a-button>
            <a-button
              type="primary"
              :disabled="!comparisonResults"
              @click="nextStep"
            >
              Continue to Prediction
            </a-button>
          </div>
        </div>

        <!-- Step 3: Prediction -->
        <div v-if="currentStep === 2" class="space-y-4">
          <h2 class="text-2xl font-semibold mb-4">Make Predictions</h2>

          <a-alert
            v-if="comparisonResults && comparisonResults.bestModel"
            :message="`Best Model: ${comparisonResults.bestModel}`"
            type="success"
            show-icon
            class="mb-4"
          />

          <a-upload-dragger
            v-model:file-list="predictionFileList"
            name="file"
            :before-upload="beforeUpload"
            :max-count="1"
            accept=".xlsx,.xls"
          >
            <p class="ant-upload-drag-icon">
              <i class="i-mdi-file-table text-6xl text-green-500"></i>
            </p>
            <p class="ant-upload-text">Upload data for prediction</p>
            <p class="ant-upload-hint">
              The file should have the same features as the training data.
            </p>
          </a-upload-dragger>

          <a-button
            type="primary"
            size="large"
            block
            :loading="isPredicting"
            :disabled="predictionFileList.length === 0"
            @click="startPrediction"
          >
            <i class="i-mdi-chart-line mr-2"></i>
            Generate Predictions
          </a-button>

          <div v-if="predictionTask" class="mt-4">
            <a-alert
              :message="predictionTaskMessage"
              :type="predictionTaskType"
              show-icon
            />
          </div>

          <div class="flex gap-4 mt-6">
            <a-button @click="prevStep">Back</a-button>
            <a-button @click="reset">Start Over</a-button>
          </div>
        </div>
      </a-card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue';
import type { UploadProps } from 'ant-design-vue';
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

// Comparison table columns
const comparisonColumns = [
  { title: 'Model', dataIndex: 'Model', key: 'Model' },
  { title: 'MSE (Train)', dataIndex: 'MSE_train', key: 'MSE_train' },
  { title: 'MAE (Train)', dataIndex: 'MAE_train', key: 'MAE_train' },
  { title: 'R² (Train)', dataIndex: 'R2_train', key: 'R2_train' },
  { title: 'MSE (Test)', dataIndex: 'MSE_test', key: 'MSE_test' },
  { title: 'MAE (Test)', dataIndex: 'MAE_test', key: 'MAE_test' },
  { title: 'R² (Test)', dataIndex: 'R2_test', key: 'R2_test' },
];

const canCompare = computed(() => {
  return Object.values(tuningStatus.value).some(status => status === 'completed');
});

const predictionTaskMessage = computed(() => {
  if (!predictionTask.value) return '';
  
  switch (predictionTask.value.status) {
    case 'pending':
      return 'Prediction task queued...';
    case 'running':
      return 'Generating predictions...';
    case 'completed':
      return 'Predictions completed successfully!';
    case 'failed':
      return `Prediction failed: ${predictionTask.value.error || 'Unknown error'}`;
    default:
      return '';
  }
});

const predictionTaskType = computed(() => {
  if (!predictionTask.value) return 'info';
  
  switch (predictionTask.value.status) {
    case 'completed':
      return 'success';
    case 'failed':
      return 'error';
    default:
      return 'info';
  }
});

const beforeUpload: UploadProps['beforeUpload'] = (file) => {
  const isExcel = file.name.endsWith('.xlsx') || file.name.endsWith('.xls');
  if (!isExcel) {
    message.error('You can only upload Excel files!');
  }
  return false; // Prevent auto upload
};

const toggleModel = (modelValue: string) => {
  const index = selectedModels.value.indexOf(modelValue);
  if (index > -1) {
    selectedModels.value.splice(index, 1);
  } else {
    selectedModels.value.push(modelValue);
  }
};

const getStatusColor = (status: string) => {
  switch (status) {
    case 'completed':
      return 'green';
    case 'running':
      return 'blue';
    case 'failed':
      return 'red';
    default:
      return 'default';
  }
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
        pollTaskStatus(response.taskId, modelValue);
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
      message.success('Model comparison started');
      
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

<style scoped>
.ant-upload-drag-icon {
  margin-bottom: 1rem;
}
</style>
