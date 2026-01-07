import { describe, expect, it } from 'vitest';

import { useFormatters } from '../../composables/useFormatters';

describe('useFormatters', () => {
  const { formatDate, formatFileSize, formatStatus } = useFormatters();

  describe('formatDate', () => {
    it('should format a date string correctly', () => {
      const dateStr = '2024-01-15T10:30:00Z';
      const result = formatDate(dateStr);

      expect(result).toMatch(/\d{4}-\d{2}-\d{2} \d{2}:\d{2}/);
    });

    it('should handle invalid date strings', () => {
      const result = formatDate('invalid-date');

      expect(result).toBe('Invalid Date');
    });
  });

  describe('formatFileSize', () => {
    it('should format bytes correctly', () => {
      expect(formatFileSize(500)).toBe('500 B');
    });

    it('should format kilobytes correctly', () => {
      expect(formatFileSize(1024)).toBe('1.00 KB');
      expect(formatFileSize(1536)).toBe('1.50 KB');
    });

    it('should format megabytes correctly', () => {
      expect(formatFileSize(1048576)).toBe('1.00 MB');
      expect(formatFileSize(5242880)).toBe('5.00 MB');
    });

    it('should format gigabytes correctly', () => {
      expect(formatFileSize(1073741824)).toBe('1.00 GB');
    });

    it('should handle zero bytes', () => {
      expect(formatFileSize(0)).toBe('0 B');
    });
  });

  describe('formatStatus', () => {
    it('should format pending status', () => {
      const result = formatStatus('pending');
      expect(result).toContain('Pending');
    });

    it('should format running status', () => {
      const result = formatStatus('running');
      expect(result).toContain('Running');
    });

    it('should format completed status', () => {
      const result = formatStatus('completed');
      expect(result).toContain('Completed');
    });

    it('should format failed status', () => {
      const result = formatStatus('failed');
      expect(result).toContain('Failed');
    });

    it('should handle unknown status', () => {
      const result = formatStatus('unknown');
      expect(result).toContain('Unknown');
    });
  });
});
