/**
 * Global application providers and configuration
 * Centralizes plugin setup and global state initialization
 */

// Re-export bootstrap for convenience
export { bootstrapApp, initApp } from "./bootstrap";
export { setGlobalAppContext, getGlobalAppContext } from "./context";
export type { AppContext } from "./context";
