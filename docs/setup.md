# Setup Guide

## Prerequisites

- Node.js 18+ and pnpm
- Python 3.12

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/xiaoland/Xenix.git
cd Xenix
```

### 2. Install dependencies

```bash
# Install Node.js dependencies
pnpm install
```

**Note:** Python dependencies (PDM and packages) are automatically installed on first use. The ML pipeline will:

1. Check if PDM is installed, and install it if missing
2. Check if Python dependencies are installed, and run `pdm install` if needed

You can also manually install Python dependencies:

```bash
# Install PDM (Python package manager)
pip install --user pdm

# Install Python dependencies
pdm install
```

### 3. Configure Database

```bash
# Copy environment file
cp .env.example .env

# The default configuration uses SQLite with DATABASE_URL=./xenix.db
```

Generate and apply migrations:

```bash
# Generate SQLite migrations
pnpm db:generate

# Apply migrations (SQLite will auto-create the database)
pnpm db:migrate
```

### 4. Start the development server

```bash
pnpm dev
```

The application will be available at `http://localhost:3005` (or `http://localhost:3000` if 3005 is in use).
