/**
 * Composable for managing model training operations
 * Uses strategy pattern for auto-tune vs manual train
 */

import { ref } from "vue";
import { message } from "ant-design-vue";
import { useI18n } from "vue-i18n";
import { TuneService } from "~/services";
import type { TrainingType } from "~/types";

interface TrainingParams {
  datasetId: string;
  featureColumns: string[];
  targetColumn: string;
  model: string;
  paramGrid?: Record<string, any>;
  workItemId?: number;
}

/**
 * Training strategy interface
 */
interface TrainingStrategy {
  execute(params: TrainingParams): Promise<{ success: boolean; taskId: number }>;
}

/**
 * Auto-tune strategy
 */
class AutoTuneStrategy implements TrainingStrategy {
  async execute(params: TrainingParams) {
    return await TuneService.startAutoTune({
      datasetId: params.datasetId,
      features: params.featureColumns,
      target: params.targetColumn,
      model: params.model,
      paramGrid: params.paramGrid,
      workItemId: params.workItemId,
    });
  }
}

/**
 * Manual train strategy
 */
class ManualTrainStrategy implements TrainingStrategy {
  async execute(params: TrainingParams) {
    return await TuneService.startManualTrain({
      datasetId: params.datasetId,
      features: params.featureColumns,
      target: params.targetColumn,
      model: params.model,
      parameters: params.paramGrid || {},
      workItemId: params.workItemId,
    });
  }
}

/**
 * Training strategy instances (singleton pattern)
 */
const autoTuneStrategy = new AutoTuneStrategy();
const manualTrainStrategy = new ManualTrainStrategy();

export function useModelTraining() {
  const { t } = useI18n();
  const isTuning = ref(false);

  /**
   * Get the appropriate training strategy
   */
  const getTrainingStrategy = (trainingType: TrainingType): TrainingStrategy => {
    return trainingType === "auto" ? autoTuneStrategy : manualTrainStrategy;
  };

  /**
   * Validate training prerequisites
   */
  const validateTrainingParams = (
    datasetId: string,
    featureColumns: string[],
    targetColumn: string
  ): boolean => {
    if (!datasetId) {
      message.error(t("messages.uploadError"));
      return false;
    }

    if (featureColumns.length === 0 || !targetColumn) {
      message.error(t("messages.columnSelectionError"));
      return false;
    }

    return true;
  };

  /**
   * Execute training with the appropriate strategy
   */
  const executeTrain = async (
    params: TrainingParams,
    trainingType: TrainingType = "auto"
  ): Promise<{ success: boolean; taskId: number } | null> => {
    if (!validateTrainingParams(params.datasetId, params.featureColumns, params.targetColumn)) {
      return null;
    }

    isTuning.value = true;

    try {
      const strategy = getTrainingStrategy(trainingType);
      const response = await strategy.execute(params);

      if (response.success) {
        // Show different messages based on training type
        if (trainingType === "manual") {
          message.success(t("messages.manualTrainingStarted"));
        } else {
          message.success(t("messages.tuningStarted"));
        }
        return response;
      }

      return null;
    } catch (error: any) {
      message.error(t("messages.tuningFailed") + ": " + error.message);
      return null;
    } finally {
      isTuning.value = false;
    }
  };

  return {
    isTuning,
    executeTrain,
  };
}
