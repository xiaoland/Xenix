# Project Structure

```
Xenix/
├── app/                         # Frontend application (Nuxt.js)
│   ├── components/              # Vue components
│   ├── composables/             # Shared logic & state management
│   ├── constants/               # Application constants
│   ├── pages/                   # Nuxt pages (index, datasets, python-env)
│   ├── services/                # API client services
│   ├── styles/                  # Global styles (SCSS)
│   ├── types/                   # TypeScript definitions
│   ├── utils/                   # Frontend utilities
│   └── app.vue                  # Root component
├── server/                      # Backend application (Nitro)
│   ├── api/                     # API endpoints (train, tune, predict, data)
│   ├── business/                # Core business logic
│   │   └── ml/                  # Python ML scripts & integration
│   │       ├── regression/      # Regression specific scripts
│   │       ├── tune_model.py    # Hyperparameter tuning
│   │       ├── train_model.py   # Model training
│   │       ├── predict.py       # Batch prediction
│   │       └── ...
│   ├── database/                # Database schema & migrations (Drizzle)
│   ├── plugins/                 # Nuxt server plugins
│   └── utils/                   # Server utilities (pythonExecutor, taskUtils)
├── data/                        # Model parameters & configurations
├── docs/                        # Project documentation
├── i18n/                        # Internationalization (locales)
├── public/                      # Static assets
├── scripts/                     # Maintenance & setup scripts
├── drizzle.config.ts            # DrizzleORM configuration
├── pyproject.toml               # Python dependencies (PDM)
├── package.json                 # Node.js dependencies (pnpm)
└── uno.config.ts                # UnoCSS configuration
```
