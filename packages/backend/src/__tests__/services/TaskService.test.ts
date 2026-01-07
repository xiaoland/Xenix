import { beforeEach, describe, expect, it, vi } from 'vitest';

import { TaskService } from '../../services/TaskService';
import { NotFoundError } from '../../errors';
import { TaskRepository } from '../../repositories/TaskRepository';

vi.mock('../../repositories/TaskRepository');

describe('TaskService', () => {
  let taskService: TaskService;
  let mockTaskRepo: any;

  beforeEach(() => {
    vi.clearAllMocks();
    taskService = new TaskService();
    mockTaskRepo = (taskService as any).taskRepo;
  });

  describe('getTasksByWorkItem', () => {
    it('should return all tasks for a work item', async () => {
      const mockTasks = [
        { id: 1, workItemId: 1, type: 'auto-tune', status: 'completed' },
        { id: 2, workItemId: 1, type: 'predict', status: 'running' },
      ];
      mockTaskRepo.findByWorkItem = vi.fn().mockResolvedValue(mockTasks);

      const result = await taskService.getTasksByWorkItem(1);

      expect(result).toEqual(mockTasks);
      expect(mockTaskRepo.findByWorkItem).toHaveBeenCalledWith(1, undefined);
    });

    it('should filter tasks by types', async () => {
      const mockTasks = [
        { id: 1, workItemId: 1, type: 'auto-tune', status: 'completed' },
      ];
      mockTaskRepo.findByWorkItem = vi.fn().mockResolvedValue(mockTasks);

      const result = await taskService.getTasksByWorkItem(1, ['auto-tune']);

      expect(result).toEqual(mockTasks);
      expect(mockTaskRepo.findByWorkItem).toHaveBeenCalledWith(1, [
        'auto-tune',
      ]);
    });
  });

  describe('getTaskById', () => {
    it('should return a task when found', async () => {
      const mockTask = { id: 1, type: 'auto-tune', status: 'completed' };
      mockTaskRepo.findById = vi.fn().mockResolvedValue(mockTask);

      const result = await taskService.getTaskById(1);

      expect(result).toEqual(mockTask);
    });

    it('should throw NotFoundError when task does not exist', async () => {
      mockTaskRepo.findById = vi.fn().mockResolvedValue(null);

      await expect(taskService.getTaskById(999)).rejects.toThrow(
        NotFoundError
      );
    });
  });

  describe('createTask', () => {
    it('should create a new task', async () => {
      const taskData = {
        workItemId: 1,
        type: 'auto-tune',
        model: 'linear_regression',
      };
      const createdTask = { id: 1, ...taskData, status: 'pending' };
      mockTaskRepo.create = vi.fn().mockResolvedValue(createdTask);

      const result = await taskService.createTask(taskData);

      expect(result).toEqual(createdTask);
      expect(mockTaskRepo.create).toHaveBeenCalledWith(taskData);
    });
  });

  describe('updateTask', () => {
    it('should update a task', async () => {
      const mockTask = { id: 1, status: 'pending' };
      const updatedTask = { id: 1, status: 'completed' };
      mockTaskRepo.findById = vi.fn().mockResolvedValue(mockTask);
      mockTaskRepo.update = vi.fn().mockResolvedValue(updatedTask);

      const result = await taskService.updateTask(1, { status: 'completed' });

      expect(result).toEqual(updatedTask);
      expect(mockTaskRepo.update).toHaveBeenCalledWith(1, {
        status: 'completed',
      });
    });
  });

  describe('deleteFailedTasks', () => {
    it('should delete all failed tasks for a work item', async () => {
      mockTaskRepo.deleteFailedByWorkItem = vi.fn().mockResolvedValue(3);

      const result = await taskService.deleteFailedTasks(1);

      expect(result).toBe(3);
      expect(mockTaskRepo.deleteFailedByWorkItem).toHaveBeenCalledWith(1);
    });
  });
});
