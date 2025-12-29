# Xenix

Machine Learning Model Training and Prediction Platform

![Xenix UI](https://github.com/user-attachments/assets/9a227c7b-8394-4558-8afa-5ced3dcd7afa)

Xenix provides an interface for teachers and mid-small enterprises to analyze their data with ease. The platform supports automated hyperparameter tuning with evaluation metrics display and batch prediction for regression tasks.

## Features

- **3-Step Workflow**: Upload Data, Pick Features, Target -> Tune & Train → Predict
- **Data Manager**: Upload and reuse datasets across multiple tasks without duplication
- **Automated Hyperparameter Tuning**: GridSearchCV-based optimization for 12 regression models
- **Evaluation Metrics Display**: Real-time display of MSE, MAE, and R² scores from tuning
- **Background Task Processing**: Long-running tasks execute asynchronously with status polling
- **Real-Time Logs**: OpenTelemetry-compliant logging with structured JSON output
- **Database Persistence**: All tasks, parameters, metrics, and results stored in SQLite
- **Modern UI**: Built with Nuxt.js and Ant Design Vue with modular components

## Tech Stack

- Fullstack Frameowork: Nuxt.js (Nitro)
- UI Library: Ant Design Vue
- Styling: UnoCSS + SCSS
- Database: SQLite
- ORM: DrizzleORM

### Data Analysis(Machine Learning)

- Language: Python 3.12
- Package Manager: PDM
- Libraries: scikit-learn, pandas, statsmodels, XGBoost, LightGBM

## Documentation

- [Supported Models](docs/models.md)
- [Setup Guide](docs/setup.md)
- [Usage Guide](docs/usage.md)
- [Project Structure](docs/structure.md)
- [API Documentation](docs/api.md)
- [Configuration](docs/configuration.md)
- [Development Guide](docs/development.md)

## Quick Start

```bash
# Install dependencies
pnpm install

# Configure database
cp .env.example .env
pnpm db:generate
pnpm db:migrate

# Start development server
pnpm dev
```

## Author

- Lanzhijiang (<lanzhijiang@foxmail.com>)
- Chenxin
- Github Copilot
