import { eq } from 'drizzle-orm';
import { readFile } from 'fs/promises';
import { resolve } from 'path';

import { zValidator } from '@hono/zod-validator';
import { Hono } from 'hono';

import { TaskIdParamSchema } from '@xenix/shared';

import { db, schema } from '../database/index.js';
import { BadRequestError, NotFoundError } from '../errors/index.js';
import { authMiddleware } from '../middleware/auth.js';
import logger from '../utils/logger/index.js';

const download = new Hono()
  .use('*', authMiddleware)

  // Download prediction result file
  .get('/:id', zValidator('param', TaskIdParamSchema), async (c) => {
    const { id: idStr } = c.req.valid('param');
    const taskId = parseInt(idStr);

    // Get task info
    const [task] = await db
      .select()
      .from(schema.tasks)
      .where(eq(schema.tasks.id, taskId))
      .limit(1);

    if (!task) {
      throw new NotFoundError('Task');
    }

    // Only allow downloading completed prediction tasks
    if (task.type !== 'predict') {
      throw new BadRequestError(
        'Only prediction task results can be downloaded'
      );
    }

    if (task.status !== 'completed') {
      throw new BadRequestError('Task is not completed yet');
    }

    const result: any = task.result || {};
    const outputFile = result.outputFile || (task.parameter as any)?.outputFile;

    if (!outputFile) {
      throw new NotFoundError('Output file');
    }

    // Read the file
    const filePath = resolve(outputFile);
    const fileBuffer = await readFile(filePath);
    const fileName = outputFile.split(/[\\/]/).pop() || 'predictions.xlsx';

    // Set response headers for file download
    c.header(
      'Content-Type',
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    );
    c.header('Content-Disposition', `attachment; filename="${fileName}"`);
    c.header('Content-Length', fileBuffer.length.toString());

    return c.body(fileBuffer);
  });

export default download;
