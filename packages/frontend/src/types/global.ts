/**
 * Global Type Declarations
 *
 * Type definitions that are used across the entire application.
 * For feature-specific types, use features/<feature>/types/
 * For shared types between frontend and backend, use @xenix/shared
 */

/**
 * Generic API response wrapper
 */
export interface ApiResponse<T> {
  data: T;
  success: boolean;
  message?: string;
}

/**
 * API error response
 */
export interface ApiError {
  error: string;
  code?: string;
  details?: Record<string, string[]>;
}

/**
 * Pagination parameters
 */
export interface PaginationParams {
  page?: number;
  pageSize?: number;
}

/**
 * Paginated response
 */
export interface PaginatedResponse<T> {
  data: T[];
  total: number;
  page: number;
  pageSize: number;
  totalPages: number;
}

/**
 * Sort direction
 */
export type SortDirection = "asc" | "desc";

/**
 * Sort configuration
 */
export interface SortConfig<T = string> {
  field: T;
  direction: SortDirection;
}

/**
 * Filter operators
 */
export type FilterOperator =
  | "eq"
  | "neq"
  | "gt"
  | "gte"
  | "lt"
  | "lte"
  | "contains"
  | "startsWith"
  | "endsWith";

/**
 * Filter condition
 */
export interface FilterCondition {
  field: string;
  operator: FilterOperator;
  value: unknown;
}

/**
 * Query parameters for list endpoints
 */
export interface ListQueryParams extends PaginationParams {
  sort?: SortConfig;
  filters?: FilterCondition[];
  search?: string;
}

/**
 * Loading states
 */
export type LoadingState = "idle" | "loading" | "success" | "error";

/**
 * Modal/Dialog result
 */
export interface DialogResult<T = void> {
  confirmed: boolean;
  data?: T;
}

/**
 * File upload progress
 */
export interface UploadProgress {
  loaded: number;
  total: number;
  percentage: number;
}

/**
 * Select option for dropdowns
 */
export interface SelectOption<T = string | number> {
  label: string;
  value: T;
  disabled?: boolean;
}

/**
 * Tree node structure
 */
export interface TreeNode<T = unknown> {
  id: string;
  label: string;
  children?: TreeNode<T>[];
  data?: T;
  expanded?: boolean;
  selected?: boolean;
  disabled?: boolean;
}

/**
 * Toast/Notification types
 */
export type NotificationType = "info" | "success" | "warning" | "error";

/**
 * Notification message
 */
export interface NotificationMessage {
  id: string;
  type: NotificationType;
  title?: string;
  message: string;
  duration?: number;
  closable?: boolean;
}
