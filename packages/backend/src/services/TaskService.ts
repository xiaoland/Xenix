/**
 * Task Service
 * Business logic for task operations
 */

import { TaskRepository } from '../repositories/index.js';
import { NotFoundError } from '../errors/index.js';

export class TaskService {
  private taskRepo: TaskRepository;

  constructor() {
    this.taskRepo = new TaskRepository();
  }

  async getTasksByWorkItem(workItemId: number, types?: string[]) {
    return await this.taskRepo.findByWorkItem(workItemId, types);
  }

  async getTaskById(id: number) {
    const task = await this.taskRepo.findById(id);

    if (!task) {
      throw new NotFoundError('Task');
    }

    return task;
  }

  async createTask(data: any) {
    return await this.taskRepo.create(data);
  }

  async updateTask(id: number, data: any) {
    const task = await this.taskRepo.findById(id);

    if (!task) {
      throw new NotFoundError('Task');
    }

    return await this.taskRepo.update(id, data);
  }

  async deleteTask(id: number) {
    const task = await this.taskRepo.findById(id);

    if (!task) {
      throw new NotFoundError('Task');
    }

    await this.taskRepo.delete(id);
    return task;
  }

  async deleteFailedTasks(workItemId: number) {
    return await this.taskRepo.deleteFailedByWorkItem(workItemId);
  }

  async deleteTasksByModel(workItemId: number, model: string) {
    return await this.taskRepo.deleteByModel(workItemId, model);
  }
}
