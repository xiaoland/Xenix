# AGENTS.md for `Xenix`

Xenix is a Machine Learning Model Training and Prediction Platform that provides an interface for teachers and mid-small enterprises to analyze their data with ease.

## Tech Stacks

- **Framework:** Nuxt.js (Vue 3 + Nitro server)
- **UI Library:** Ant Design Vue
- **Style management:** UnoCSS (icons and simple styles) + SCSS (complex styles)
- **Database:** DrizzleORM + SQLite
- **Automation testing:** Vitest (with `@vue/test-utils`)
- **ML Backend:** Python (scikit-learn, XGBoost, LightGBM)
- **Package management:** pnpm (Node.js), pdm (Python)

## Core Workflow

The application follows a 3-step ML workflow:

1. **Prepare** - Upload dataset, select feature columns and target column
2. **Tune** - Train models with auto/manual hyperparameter tuning
3. **Predict** - Use trained model for batch predictions

## Project Structure

```
Xenix/
├── app/                   # Frontend (Nuxt.js application)
│   ├── components/        # Vue components organized by domain
│   ├── composables/       # Vue composition functions (shared logic)
│   ├── pages/             # Nuxt page routes
│   ├── services/          # API client services
│   ├── types/             # TypeScript type definitions
│   ├── constants/         # Application constants
│   └── utils/             # Frontend utilities
├── server/                 # Backend (Nitro server)
│   ├── api/               # REST API endpoints
│   ├── business/ml/       # ML business logic & Python scripts
│   │   └── regression/    # Regression model implementations
│   ├── database/          # DrizzleORM schema & migrations
│   └── utils/             # Server utilities (pythonExecutor, etc.)
├── docs/                   # Documentation
├── datasets/              # Uploaded dataset storage
├── uploads/               # User file uploads
├── i18n/                  # Internationalization files
└── data/                  # Model parameters & configuration
```

## Key Concepts

### Work Items

A work item represents a complete ML workflow session, containing:

- Dataset reference
- Selected feature/target columns
- Tuning tasks (auto/manual)
- Selected models for prediction

### Tasks

Background tasks for ML operations:

- `auto-tune` - GridSearchCV hyperparameter tuning
- `manual-tune` - Manual parameter configuration
- `predict` - Batch prediction execution

### Supported Models (Regression)

- Linear Regression, Ridge, Lasso
- Polynomial Regression
- K-Nearest Neighbors
- Decision Tree, Random Forest
- AdaBoost, GBDT
- XGBoost, LightGBM
- Bayesian Ridge Regression

## Development

- `.env`
- Run `pnpm run db:generate` to generate migrations
- Run `pnpm run db:migrate` to apply the migrations

## Coding Guidelines

1. **Vue Components:** Use `<script setup lang="ts">` with Composition API
2. **API Endpoints:** Follow Nitro file-based routing (`[id].get.ts`, `index.post.ts`)
3. **Database:** Use DrizzleORM with PostgreSQL, define schema in `server/database/schema.ts`
4. **Python Integration:** Execute via `pythonExecutor.ts`, use JSON for I/O
5. **i18n:** All user-facing strings should use `$t('key')` or `t('key')`
6. **Styling:** Prefer UnoCSS utility classes, use SCSS for complex styles
