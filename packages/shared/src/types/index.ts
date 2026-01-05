/**
 * Core type definitions for the application
 *
 * Types are organized by domain for better maintainability:
 * - task.ts: Task-related types (AutoTuneTask, ManualTuneTask, PredictTask, etc.)
 * - dataset.ts: Dataset-related types
 * - model.ts: Model-related types
 * - project.ts: Project and WorkItem types
 */

// Re-export all types from domain-specific files
export * from "./task";
export * from "./dataset";
export * from "./model";
export * from "./project";
export * from "./user";
