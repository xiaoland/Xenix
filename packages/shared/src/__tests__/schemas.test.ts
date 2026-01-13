import { describe, expect, it } from 'vitest';

import {
  CreateProjectSchema,
  CreateWorkItemSchema,
  DatasetIdParamSchema,
  ModelIdParamSchema,
  ProjectIdParamSchema,
  SignInSchema,
  SignUpSchema,
  TaskIdParamSchema,
  UpdateProjectSchema,
  UpdateWorkItemSchema,
  WorkItemIdParamSchema,
} from '../schemas';

describe('Zod Schemas', () => {
  describe('Auth Schemas', () => {
    describe('SignInSchema', () => {
      it('should validate correct sign in data', () => {
        const validData = {
          identifier: 'test@example.com',
          password: 'password123',
        };
        const result = SignInSchema.safeParse(validData);
        expect(result.success).toBe(true);
      });

      it('should reject missing identifier', () => {
        const invalidData = { password: 'password123' };
        const result = SignInSchema.safeParse(invalidData);
        expect(result.success).toBe(false);
      });

      it('should reject missing password', () => {
        const invalidData = { identifier: 'test@example.com' };
        const result = SignInSchema.safeParse(invalidData);
        expect(result.success).toBe(false);
      });
    });

    describe('SignUpSchema', () => {
      it('should validate correct sign up data', () => {
        const validData = {
          email: 'test@example.com',
          password: 'password123',
        };
        const result = SignUpSchema.safeParse(validData);
        expect(result.success).toBe(true);
      });

      it('should reject invalid email format', () => {
        const invalidData = {
          email: 'not-an-email',
          password: 'password123',
        };
        const result = SignUpSchema.safeParse(invalidData);
        expect(result.success).toBe(false);
      });

      it('should reject password shorter than 6 characters', () => {
        const invalidData = {
          email: 'test@example.com',
          password: '12345',
        };
        const result = SignUpSchema.safeParse(invalidData);
        expect(result.success).toBe(false);
      });
    });
  });

  describe('Project Schemas', () => {
    describe('CreateProjectSchema', () => {
      it('should validate correct project data', () => {
        const validData = {
          name: 'Test Project',
          description: 'Test description',
        };
        const result = CreateProjectSchema.safeParse(validData);
        expect(result.success).toBe(true);
      });

      it('should allow missing description', () => {
        const validData = { name: 'Test Project' };
        const result = CreateProjectSchema.safeParse(validData);
        expect(result.success).toBe(true);
      });

      it('should reject empty name', () => {
        const invalidData = { name: '' };
        const result = CreateProjectSchema.safeParse(invalidData);
        expect(result.success).toBe(false);
      });
    });

    describe('UpdateProjectSchema', () => {
      it('should validate partial updates', () => {
        const validData = { name: 'Updated Name' };
        const result = UpdateProjectSchema.safeParse(validData);
        expect(result.success).toBe(true);
      });

      it('should validate status updates', () => {
        const validData = { status: 'completed' };
        const result = UpdateProjectSchema.safeParse(validData);
        expect(result.success).toBe(true);
      });

      it('should reject invalid status', () => {
        const invalidData = { status: 'invalid-status' };
        const result = UpdateProjectSchema.safeParse(invalidData);
        expect(result.success).toBe(false);
      });
    });

    describe('ProjectIdParamSchema', () => {
      it('should validate numeric ID string', () => {
        const validData = { id: '123' };
        const result = ProjectIdParamSchema.safeParse(validData);
        expect(result.success).toBe(true);
      });

      it('should reject non-numeric ID', () => {
        const invalidData = { id: 'abc' };
        const result = ProjectIdParamSchema.safeParse(invalidData);
        expect(result.success).toBe(false);
      });
    });
  });

  describe('WorkItem Schemas', () => {
    describe('CreateWorkItemSchema', () => {
      it('should validate correct work item data', () => {
        const validData = {
          projectId: 1,
          name: 'Test Work Item',
          description: 'Test description',
        };
        const result = CreateWorkItemSchema.safeParse(validData);
        expect(result.success).toBe(true);
      });

      it('should reject missing projectId', () => {
        const invalidData = { name: 'Test Work Item' };
        const result = CreateWorkItemSchema.safeParse(invalidData);
        expect(result.success).toBe(false);
      });
    });

    describe('UpdateWorkItemSchema', () => {
      it('should validate partial updates', () => {
        const validData = { name: 'Updated Name' };
        const result = UpdateWorkItemSchema.safeParse(validData);
        expect(result.success).toBe(true);
      });

      it('should validate ML workflow fields', () => {
        const validData = {
          datasetId: 5,
          featureColumns: ['feature1', 'feature2'],
          targetColumn: 'target',
        };
        const result = UpdateWorkItemSchema.safeParse(validData);
        expect(result.success).toBe(true);
      });
    });

    describe('WorkItemIdParamSchema', () => {
      it('should validate numeric ID string', () => {
        const validData = { id: '456' };
        const result = WorkItemIdParamSchema.safeParse(validData);
        expect(result.success).toBe(true);
      });
    });
  });

  describe('Parameter Schemas', () => {
    it('DatasetIdParamSchema should validate numeric ID', () => {
      const result = DatasetIdParamSchema.safeParse({ id: '789' });
      expect(result.success).toBe(true);
    });

    it('ModelIdParamSchema should validate numeric ID', () => {
      const result = ModelIdParamSchema.safeParse({ id: '101' });
      expect(result.success).toBe(true);
    });

    it('TaskIdParamSchema should validate numeric ID', () => {
      const result = TaskIdParamSchema.safeParse({ id: '202' });
      expect(result.success).toBe(true);
    });
  });
});
