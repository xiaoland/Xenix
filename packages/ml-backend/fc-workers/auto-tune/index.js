import {
  batchTrain
} from "../../chunk-ZLP46V6Z.js";
import "../../chunk-XFIKUN4J.js";
import {
  createLogger
} from "../../chunk-YVWWAEX3.js";

// src/adapters/aliyun-fc/auto-tune.ts
async function handler(event, context) {
  try {
    const {
      taskId,
      inputFile,
      model,
      featureColumns,
      targetColumn,
      paramGrid
    } = event;
    if (!taskId || !inputFile || !model || !featureColumns || !targetColumn || !paramGrid) {
      throw new Error("Missing required fields in event payload");
    }
    const logger = createLogger(taskId, {
      databaseUrl: process.env.DATABASE_URL || ""
    });
    await logger.log(
      `FC auto-tune started: ${model}`,
      "INFO",
      { requestId: context.requestId }
    );
    const result = await batchTrain({
      inputFile,
      model,
      featureColumns,
      targetColumn,
      paramGrid,
      taskId,
      logger
    });
    await logger.log(
      `FC auto-tune completed: ${model}`,
      "INFO",
      { requestId: context.requestId, metrics: result.metrics }
    );
    return {
      statusCode: 200,
      body: JSON.stringify(result)
    };
  } catch (error) {
    console.error("FC auto-tune error:", error);
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
//# sourceMappingURL=auto-tune.js.map