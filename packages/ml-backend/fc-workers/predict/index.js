import {
  predict
} from "../../chunk-CKBP4TQ3.js";
import "../../chunk-XFIKUN4J.js";
import {
  createLogger
} from "../../chunk-YVWWAEX3.js";

// src/adapters/aliyun-fc/predict.ts
async function handler(event, context) {
  try {
    const {
      taskId,
      trainData,
      predictData,
      outputPath,
      model,
      params,
      featureColumns,
      targetColumn
    } = event;
    if (!taskId || !trainData || !predictData || !outputPath || !model || !params || !featureColumns || !targetColumn) {
      throw new Error("Missing required fields in event payload");
    }
    const logger = createLogger(taskId, {
      databaseUrl: process.env.DATABASE_URL || ""
    });
    await logger.log(
      `FC predict started: ${model}`,
      "INFO",
      { requestId: context.requestId }
    );
    const result = await predict({
      trainData,
      predictData,
      outputPath,
      model,
      params,
      featureColumns,
      targetColumn,
      taskId,
      logger
    });
    await logger.log(
      `FC predict completed: ${model}`,
      "INFO",
      { requestId: context.requestId }
    );
    return {
      statusCode: 200,
      body: JSON.stringify(result)
    };
  } catch (error) {
    console.error("FC predict error:", error);
    return {
      statusCode: 500,
      body: JSON.stringify({
        error: error instanceof Error ? error.message : "Unknown error",
        stack: error instanceof Error ? error.stack : void 0
      })
    };
  }
}
export {
  handler
};
//# sourceMappingURL=predict.js.map