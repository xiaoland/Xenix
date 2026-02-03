/**
 * Add Dataset Hook
 * Composable for adding datasets with support for local and OSS storage
 */
import { message } from "ant-design-vue";
import type { UploadProps } from "ant-design-vue";

import { computed, ref } from "vue";
import { useI18n } from "vue-i18n";

import { useCreateDataset } from "@/features/datasets/queries/useDatasets";
import {
  extractDatasetMetadata,
  type DatasetMetadata,
} from "@/utils/datasetUtils";

export function useAddDataset(projectId: number) {
  const { t } = useI18n();

  const storageType = ref<"local" | "oss">("oss");
  const datasetName = ref("");
  const fileList = ref<any[]>([]);
  const metadata = ref<DatasetMetadata | null>(null);
  const selectedFilePath = ref<string>("");
  const showPathTooltip = ref(false);

  const { mutate: createDataset, isPending: creating } = useCreateDataset();

  const canCreate = computed(() => {
    return (
      datasetName.value.trim() !== "" &&
      metadata.value !== null &&
      fileList.value.length > 0 &&
      (storageType.value === "oss" ||
        (storageType.value === "local" && selectedFilePath.value.trim() !== ""))
    );
  });

  const formatFileSize = (bytes: number): string => {
    if (bytes === 0) return "0 Bytes";
    const k = 1024;
    const sizes = ["Bytes", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + " " + sizes[i];
  };

  const beforeUpload: UploadProps["beforeUpload"] = (file) => {
    const isValidFormat =
      file.type === "text/csv" ||
      file.type === "application/vnd.ms-excel" ||
      file.type ===
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet";

    if (!isValidFormat) {
      message.error(t("dataset.add.invalidFileFormat"));
      return false;
    }

    const isLt10M = file.size / 1024 / 1024 < 10;
    if (!isLt10M) {
      message.error(t("dataset.add.fileTooLarge"));
      return false;
    }

    return false;
  };

  const handleFileChange = async () => {
    if (fileList.value.length > 0) {
      try {
        const file = fileList.value[0].originFileObj;
        message.loading({
          content: t("dataset.add.analyzingFile"),
          key: "analyze",
        });

        metadata.value = await extractDatasetMetadata(file);

        if (storageType.value === "local") {
          selectedFilePath.value = "";
        } else {
          selectedFilePath.value = file.name;
        }

        if (datasetName.value.trim() === "") {
          const nameWithoutExtension = file.name.replace(
            /\.(csv|xlsx|xls)$/i,
            "",
          );
          datasetName.value = nameWithoutExtension;
        }

        message.success({
          content: t("dataset.add.fileAnalyzed"),
          key: "analyze",
        });
      } catch (error: any) {
        message.error({
          content: error.message || t("dataset.add.analyzeFailed"),
          key: "analyze",
        });
        metadata.value = null;
        selectedFilePath.value = "";
      }
    } else {
      metadata.value = null;
      selectedFilePath.value = "";
    }
  };

  const handleCreate = async (
    onSuccess?: () => void,
    onError?: (error: any) => void,
  ) => {
    if (!canCreate.value || !metadata.value) return;

    const file = fileList.value[0].originFileObj;

    const params = {
      name: datasetName.value,
      projectId,
      storage: storageType.value,
      filePath:
        storageType.value === "local"
          ? `${selectedFilePath.value}/${file.name}`
          : selectedFilePath.value,
      file: storageType.value === "oss" ? file : null,
      columns: metadata.value.columns,
      rowCount: metadata.value.rowCount,
      fileSize: metadata.value.fileSize,
    };

    createDataset(params, {
      onSuccess: () => {
        message.success(t("dataset.add.createSuccess"));
        onSuccess?.();

        datasetName.value = "";
        fileList.value = [];
        metadata.value = null;
        selectedFilePath.value = "";
      },
      onError: (error: any) => {
        console.error("Creation failed:", error);
        message.error(error.message || t("dataset.add.createFailed"));
        onError?.(error);
      },
    });
  };

  const reset = () => {
    storageType.value = "oss";
    datasetName.value = "";
    fileList.value = [];
    metadata.value = null;
    selectedFilePath.value = "";
    showPathTooltip.value = false;
  };

  return {
    storageType,
    datasetName,
    fileList,
    metadata,
    selectedFilePath,
    showPathTooltip,
    canCreate,
    creating,
    formatFileSize,
    beforeUpload,
    handleFileChange,
    handleCreate,
    reset,
  };
}
