# Xenix

Machine Learning Model Training and Prediction Platform

![Xenix UI](https://github.com/user-attachments/assets/9a227c7b-8394-4558-8afa-5ced3dcd7afa)

Xenix provides an interface for teachers and mid-small enterprises to analyze their data with ease. The platform supports automated hyperparameter tuning with evaluation metrics display and batch prediction for regression tasks.

## Features

- **3-Step Workflow**: Prepare Data, Pick Features, Target → Tune & Train → Predict
- **Data Manager**: Upload and reuse datasets across multiple tasks without duplication
- **Automated Hyperparameter Tuning**: GridSearchCV-based optimization for 12 regression models
- **Evaluation Metrics Display**: Real-time display of MSE, MAE, and R² scores from tuning
- **Background Task Processing**: Long-running tasks execute asynchronously with status polling
- **Database Persistence**: All tasks, parameters, metrics, and results stored in PostgreSQL
- **Modern Monorepo Architecture**: Separate frontend and backend packages with shared types
- **Type-Safe API**: Shared TypeScript types between frontend and backend
- **Fast Development**: Vite HMR for instant feedback during development

## Architecture

Xenix is built as a modern monorepo with three main packages:

```
packages/
├── shared/      # Shared TypeScript types and utilities
├── backend/     # Hono API server with Python ML integration
└── frontend/    # Vite + Vue 3 application with Ant Design Vue
```

### Tech Stack

**Frontend:**

- Framework: Vite + Vue 3 (Composition API)
- UI Library: Ant Design Vue
- State Management: Pinia
- Routing: Vue Router
- Styling: UnoCSS + SCSS
- i18n: Vue I18n

**Backend:**

- Framework: Hono
- Database: PostgreSQL
- ORM: Drizzle ORM
- Authentication: JWT with bcrypt

**Machine Learning:**

- Language: Python 3.9+
- Package Manager: PDM
- Libraries: scikit-learn, pandas, XGBoost, LightGBM

**Infrastructure:**

- Monorepo: pnpm workspaces
- Testing: Vitest
- Database: PostgreSQL 17 (Docker)
- Cache: Redis 7 (Docker, ready for job queue)

## Quick Start

### Prerequisites

- Node.js 18+
- pnpm 8+
- Python 3.9+
- Docker & Docker Compose (for PostgreSQL and Redis)

### Installation

```bash
# Clone repository
git clone https://github.com/xiaoland/Xenix.git
cd Xenix

# Install Node dependencies
pnpm install

# Install Python dependencies (optional, for ML features)
pip install scikit-learn xgboost lightgbm pandas numpy openpyxl
# OR use PDM
pdm install

# Setup environment variables
cp .env.example .env
cp packages/backend/.env.example packages/backend/.env
cp packages/frontend/.env.example packages/frontend/.env
# Edit .env files with your configuration

# Start PostgreSQL and Redis
pnpm docker:up

# Run database migrations
pnpm db:migrate

# Start development servers (both frontend and backend)
pnpm dev
```

Access the application:

- Frontend: http://localhost:5173
- Backend API: http://localhost:3000
- Health Check: http://localhost:3000/health

### Running Tests

```bash
# Run all tests
pnpm test

# Run tests in watch mode
pnpm test:watch

# Generate coverage report
pnpm test:coverage
```

## Documentation

### General

- [Deployment Guide](docs/DEPLOYMENT.md) - Production deployment instructions
- [Migration Notes](docs/MIGRATION-NOTES.md) - Migration journey from Nuxt to monorepo
- [Architecture Plan](docs/plan/monorepo-refactor-vite-vue-hono.md) - Detailed architecture documentation

### Legacy Documentation (from Nuxt version)

- [Supported Models](docs/models.md)
- [Setup Guide](docs/setup.md)
- [Usage Guide](docs/usage.md)
- [Project Structure](docs/structure.md)
- [API Documentation](docs/api.md)
- [Configuration](docs/configuration.md)
- [Development Guide](docs/development.md)

## Development

### Package Scripts

**Root level:**

```bash
pnpm dev              # Run all packages in development mode
pnpm dev:frontend     # Run frontend only
pnpm dev:backend      # Run backend only
pnpm build            # Build all packages
pnpm test             # Run all tests
pnpm db:generate      # Generate database migrations
pnpm db:migrate       # Apply database migrations
pnpm docker:up        # Start PostgreSQL and Redis
pnpm docker:down      # Stop containers
```

**Individual packages:**

```bash
cd packages/shared    # Shared types and utilities
pnpm test             # Run tests

cd packages/backend   # Backend API server
pnpm dev              # Start development server
pnpm build            # Build for production
pnpm test             # Run tests

cd packages/frontend  # Frontend application
pnpm dev              # Start development server
pnpm build            # Build for production
pnpm test             # Run tests
```

## Project Structure

```
Xenix/
├── packages/
│   ├── shared/               # Shared TypeScript types
│   │   ├── src/
│   │   │   ├── types/       # Type definitions (Project, Dataset, Task, etc.)
│   │   │   └── __tests__/   # Type tests
│   │   └── package.json
│   │
│   ├── backend/              # Hono API server
│   │   ├── src/
│   │   │   ├── routes/      # API route handlers
│   │   │   ├── middleware/  # Auth, CORS, logging
│   │   │   ├── business/ml/ # ML logic & Python integration
│   │   │   ├── database/    # Drizzle schema & migrations
│   │   │   ├── utils/       # Server utilities
│   │   │   └── __tests__/   # Backend tests
│   │   └── package.json
│   │
│   └── frontend/             # Vite + Vue 3 app
│       ├── src/
│       │   ├── components/  # Vue components
│       │   ├── views/       # Page components
│       │   ├── router/      # Route definitions
│       │   ├── stores/      # Pinia stores
│       │   ├── services/    # API client services
│       │   ├── locales/     # i18n translations
│       │   └── __tests__/   # Frontend tests
│       └── package.json
│
├── docs/                     # Documentation
├── data/                     # Model parameters (shared)
├── datasets/                 # Uploaded datasets (shared)
├── uploads/                  # File uploads (shared)
├── docker-compose.yml        # PostgreSQL + Redis
├── pnpm-workspace.yaml       # pnpm workspace config
└── package.json              # Root workspace
```

## Contributing

Contributions are welcome! Please follow these guidelines:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Run tests (`pnpm test`)
5. Commit your changes (`git commit -m 'Add amazing feature'`)
6. Push to the branch (`git push origin feature/amazing-feature`)
7. Open a Pull Request

## License

This project is licensed under the MIT License.

## Authors

- Lanzhijiang (<lanzhijiang@foxmail.com>)
- Chenxin
- GitHub Copilot

## Acknowledgments

- Built with modern web technologies: Vite, Vue 3, Hono, PostgreSQL
- ML powered by scikit-learn, XGBoost, and LightGBM
- UI components from Ant Design Vue
- Styling with UnoCSS
