/**
 * Vue Component Types
 *
 * Type helpers and utilities for Vue components
 */

import type { Component } from "vue";

/**
 * Props extraction helper
 * Extracts props type from a Vue component
 */
export type ComponentProps<T extends Component> = T extends new (
  ...args: unknown[]
) => infer R
  ? R extends { $props: infer P }
    ? P
    : never
  : never;

/**
 * Emits extraction helper
 * Extracts emits type from a Vue component
 */
export type ComponentEmits<T extends Component> = T extends new (
  ...args: unknown[]
) => infer R
  ? R extends { $emit: infer E }
    ? E
    : never
  : never;

/**
 * Slot props extraction helper
 */
export type ComponentSlots<T extends Component> = T extends new (
  ...args: unknown[]
) => infer R
  ? R extends { $slots: infer S }
    ? S
    : never
  : never;

/**
 * Async component loader type
 */
export type AsyncComponentLoader<T extends Component = Component> =
  () => Promise<T | { default: T }>;
