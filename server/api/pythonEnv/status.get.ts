import { getPythonEnvStatus, setupEnvironment, reinstallEnvironment } from '../../business/mlPipeline';

export default defineEventHandler(async (event) => {
  try {
    const status = await getPythonEnvStatus();
    
    return {
      success: true,
      status
    };
  } catch (error) {
    console.error('Error getting Python environment status:', error);
    throw createError({
      statusCode: 500,
      message: error instanceof Error ? error.message : 'Failed to get environment status',
    });
  }
});
