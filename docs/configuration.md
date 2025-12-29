# Configuration

## Environment Variables

Create a `.env` file from the example:

```bash
cp .env.example .env
```

Available variables:

- `DATABASE_URL` - SQLite database file path (required)
  - Example: `./xenix.db` or `sqlite://./xenix.db`
- `PYTHON_EXECUTABLE` - Python command to use (default: `python3`)
