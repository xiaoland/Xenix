# Current Architecture Exploration Plan

## Objective

Understand the actual code architecture of Xenix to identify areas for future refactoring and architectural improvements.

## Exploration Scope

### 1. Core Package Structure

- [ ] Analyze monorepo setup (pnpm workspace)
- [ ] Understand shared package structure (types, schemas)
- [ ] Map frontend entry points and bootstrap
- [ ] Map backend entry points and routing
- [ ] Analyze ml-backend setup

### 2. Frontend Architecture

- [ ] Entry point (main.ts)
- [ ] App initialization and setup
- [ ] Router configuration (explicit routing)
- [ ] Store setup (Pinia)
- [ ] API client integration
- [ ] Composables and hooks architecture
- [ ] Component organization
- [ ] Data fetching patterns (TanStack Query usage)
- [ ] State management patterns

### 3. Backend Architecture

- [ ] Entry point (index.ts)
- [ ] Hono app configuration
- [ ] Route structure and organization
- [ ] Middleware stack
- [ ] Database layer (DrizzleORM schema)
- [ ] Business logic organization (ML operations)
- [ ] Python integration approach
- [ ] Job queue setup (if implemented)
- [ ] Error handling patterns

### 4. Shared Layer

- [ ] Type definitions
- [ ] Zod schemas structure
- [ ] Shared utilities
- [ ] Type exports

### 5. ML Integration

- [ ] Python layer structure
- [ ] How Python scripts are called
- [ ] Data flow between Node.js and Python
- [ ] Model parameter management

### 6. Cross-Cutting Concerns

- [ ] Authentication/Authorization flow
- [ ] Error handling patterns
- [ ] Logging approach
- [ ] Configuration management
- [ ] Database migrations

### 7. Build & Deployment

- [ ] Build configuration (Vite, tsup)
- [ ] Deployment setup (Aliyun FC)
- [ ] Docker setup

## Key Questions to Answer

1. How tightly coupled are frontend and backend?
2. What's the current data flow for ML operations?
3. How is shared state managed?
4. What are the major architectural bottlenecks?
5. Where are legacy patterns that should be modernized?
6. What's the actual testing strategy?

## Execution Strategy

- Deep dive into actual code files
- Map dependencies and imports
- Trace data flow through key operations
- Document actual vs intended patterns
