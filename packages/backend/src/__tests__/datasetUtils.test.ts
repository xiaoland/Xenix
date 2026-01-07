import { describe, expect, it } from 'vitest';

import {
  generateDatasetId,
  parseDatasetColumns,
  safeParseJsonArray,
} from '../utils/datasetUtils';

describe('Dataset Utils', () => {
  describe('generateDatasetId', () => {
    it('should generate a unique dataset ID with correct prefix', () => {
      const id1 = generateDatasetId();
      const id2 = generateDatasetId();

      expect(id1).toMatch(/^dataset_\d+_[a-f0-9]{16}$/);
      expect(id2).toMatch(/^dataset_\d+_[a-f0-9]{16}$/);
      expect(id1).not.toBe(id2);
    });
  });

  describe('parseDatasetColumns', () => {
    it('should parse JSON string to array', () => {
      const jsonString = '["col1", "col2", "col3"]';
      const result = parseDatasetColumns(jsonString);

      expect(result).toEqual(['col1', 'col2', 'col3']);
    });

    it('should return array if already an array', () => {
      const array = ['col1', 'col2'];
      const result = parseDatasetColumns(array);

      expect(result).toEqual(['col1', 'col2']);
    });

    it('should return empty array for invalid JSON', () => {
      const invalid = 'not valid json';
      const result = parseDatasetColumns(invalid);

      expect(result).toEqual([]);
    });

    it('should return empty array for non-array values', () => {
      expect(parseDatasetColumns(null)).toEqual([]);
      expect(parseDatasetColumns(undefined)).toEqual([]);
      expect(parseDatasetColumns(123)).toEqual([]);
      expect(parseDatasetColumns({})).toEqual([]);
    });
  });

  describe('safeParseJsonArray', () => {
    it('should return array if already an array', () => {
      const array = ['item1', 'item2'];
      const result = safeParseJsonArray(array);

      expect(result).toEqual(['item1', 'item2']);
    });

    it('should parse JSON string to array', () => {
      const jsonString = '["item1", "item2"]';
      const result = safeParseJsonArray(jsonString);

      expect(result).toEqual(['item1', 'item2']);
    });

    it('should return default value for invalid JSON string', () => {
      const invalid = 'not valid json';
      const result = safeParseJsonArray(invalid, ['default']);

      expect(result).toEqual(['default']);
    });

    it('should return default value for non-array parsed JSON', () => {
      const objectJson = '{"key": "value"}';
      const result = safeParseJsonArray(objectJson, ['default']);

      expect(result).toEqual(['default']);
    });

    it('should return empty array as default when no default provided', () => {
      expect(safeParseJsonArray(null)).toEqual([]);
      expect(safeParseJsonArray(undefined)).toEqual([]);
      expect(safeParseJsonArray(123)).toEqual([]);
    });

    it('should accept custom default value', () => {
      const customDefault = ['custom', 'default'];
      const result = safeParseJsonArray(null, customDefault);

      expect(result).toEqual(['custom', 'default']);
    });
  });
});
