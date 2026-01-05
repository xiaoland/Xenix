import { describe, it, expect } from 'vitest';
import type { Dataset, ColumnSelection } from '../types/dataset';

describe('Dataset Types', () => {
  describe('Dataset', () => {
    it('should have required fields', () => {
      const dataset: Dataset = {
        id: 1,
        name: 'Sales Data',
        fileName: 'sales.csv',
        fileSize: 1024,
        columns: ['date', 'sales', 'region'],
        rowCount: 100,
        createdAt: new Date().toISOString(),
      };

      expect(dataset.id).toBe(1);
      expect(dataset.name).toBe('Sales Data');
      expect(dataset.fileName).toBe('sales.csv');
      expect(dataset.fileSize).toBe(1024);
      expect(dataset.columns).toHaveLength(3);
      expect(dataset.rowCount).toBe(100);
    });

    it('should accept optional projectId and description', () => {
      const dataset: Dataset = {
        id: 1,
        projectId: 5,
        name: 'Sales Data',
        description: 'Monthly sales data',
        fileName: 'sales.csv',
        fileSize: 1024,
        columns: ['date', 'sales'],
        rowCount: 100,
        createdAt: new Date().toISOString(),
      };

      expect(dataset.projectId).toBe(5);
      expect(dataset.description).toBe('Monthly sales data');
    });
  });

  describe('ColumnSelection', () => {
    it('should define feature and target columns', () => {
      const selection: ColumnSelection = {
        featureColumns: ['feature1', 'feature2', 'feature3'],
        targetColumn: 'target',
      };

      expect(selection.featureColumns).toHaveLength(3);
      expect(selection.targetColumn).toBe('target');
    });

    it('should accept optional datasetId', () => {
      const selection: ColumnSelection = {
        featureColumns: ['feature1'],
        targetColumn: 'target',
        datasetId: 10,
      };

      expect(selection.datasetId).toBe(10);
    });
  });
});
