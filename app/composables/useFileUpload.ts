/**
 * Composable for managing file upload and Excel processing
 */

import { ref } from "vue";
import * as XLSX from "xlsx";
import { message } from "ant-design-vue";
import { useI18n } from "vue-i18n";

export function useFileUpload() {
  const { t } = useI18n();
  const isLoadingColumns = ref(false);

  /**
   * Read Excel file and extract column names
   */
  const readExcelColumns = async (file: File): Promise<string[]> => {
    isLoadingColumns.value = true;

    try {
      const arrayBuffer = await file.arrayBuffer();
      const workbook = XLSX.read(arrayBuffer, { type: "array" });

      // Get the first sheet
      const firstSheetName = workbook.SheetNames[0];
      const worksheet = workbook.Sheets[firstSheetName];

      // Convert to JSON to get column names
      const jsonData = XLSX.utils.sheet_to_json(worksheet, { header: 1 });

      if (jsonData.length === 0) {
        message.error(t("upload.emptyFile"));
        return [];
      }

      // First row contains column names
      const columns = (jsonData[0] as any[]).filter(
        (col) => col !== null && col !== undefined && col !== ""
      );

      if (columns.length === 0) {
        message.error(t("upload.noColumns"));
        return [];
      }

      message.success(t("upload.columnsFound", { count: columns.length }));
      return columns.map(String);
    } catch (error) {
      console.error("Error reading Excel file:", error);
      message.error(t("upload.readError"));
      return [];
    } finally {
      isLoadingColumns.value = false;
    }
  };

  /**
   * Validate file is Excel format
   */
  const validateExcelFile = (file: File): boolean => {
    const isExcel = file.name.endsWith(".xlsx") || file.name.endsWith(".xls");
    if (!isExcel) {
      message.error(t("upload.excelOnly"));
      return false;
    }
    return true;
  };

  return {
    isLoadingColumns,
    readExcelColumns,
    validateExcelFile,
  };
}
