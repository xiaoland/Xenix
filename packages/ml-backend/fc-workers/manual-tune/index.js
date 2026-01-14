import {
  singleTrain
} from "../../chunk-VTTC2LX6.js";
import "../../chunk-XFIKUN4J.js";
import {
  createLogger
} from "../../chunk-YVWWAEX3.js";

// src/adapters/aliyun-fc/manual-tune.ts
async function handler(event, context) {
  try {
    const {
      taskId,
      inputFile,
      model,
      featureColumns,
      targetColumn,
      params,
      parentTaskId
    } = event;
    if (!taskId || !inputFile || !model || !featureColumns || !targetColumn || !params) {
      throw new Error("Missing required fields in event payload");
    }
    const logger = createLogger(taskId, {
      databaseUrl: process.env.DATABASE_URL || ""
    });
    await logger.log(
      `FC manual-tune started: ${model}`,
      "INFO",
      { requestId: context.requestId }
    );
    const result = await singleTrain({
      inputFile,
      model,
      featureColumns,
      targetColumn,
      params,
      taskId,
      logger,
      parentTaskId
    });
    await logger.log(
      `FC manual-tune completed: ${model}`,
      "INFO",
      { requestId: context.requestId, metrics: result.metrics }
    );
    return {
      statusCode: 200,
      body: JSON.stringify(result)
    };
  } catch (error) {
    console.error("FC manual-tune error:", error);
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
//# sourceMappingURL=manual-tune.js.map