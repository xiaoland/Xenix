/**
 * Common Types
 *
 * Shared type definitions used across multiple features
 */

/**
 * Language option
 */
export interface LanguageOption {
  code: string;
  name: string;
  flag?: string;
}

/**
 * Theme configuration
 */
export interface ThemeConfig {
  mode: "light" | "dark" | "auto";
  primaryColor: string;
  borderRadius: "small" | "medium" | "large";
}

/**
 * Navigation item
 */
export interface NavigationItem {
  id: string;
  label: string;
  icon?: string;
  path?: string;
  children?: NavigationItem[];
  badge?: number | string;
  disabled?: boolean;
}

/**
 * Breadcrumb item
 */
export interface BreadcrumbItem {
  label: string;
  path?: string;
  icon?: string;
}

/**
 * UI Step configuration
 */
export interface UIStepConfig {
  id: string;
  title: string;
  description?: string;
  icon?: string;
  status: "pending" | "active" | "completed" | "error";
  disabled?: boolean;
}

/**
 * Table column configuration
 */
export interface TableColumn<T = unknown> {
  key: string;
  title: string;
  width?: number | string;
  sortable?: boolean;
  filterable?: boolean;
  render?: (row: T) => unknown;
}

/**
 * Menu item
 */
export interface MenuItem {
  key: string;
  label: string;
  icon?: string;
  shortcut?: string;
  disabled?: boolean;
  danger?: boolean;
  divider?: boolean;
  children?: MenuItem[];
  onClick?: () => void;
}

/**
 * Confirmation dialog options
 */
export interface ConfirmOptions {
  title: string;
  content?: string;
  okText?: string;
  cancelText?: string;
  okDanger?: boolean;
  onOk?: () => void | Promise<void>;
  onCancel?: () => void;
}
