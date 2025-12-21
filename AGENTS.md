# AGENTS.md for `Xenix`

Xenix provides an interface for teachers, mid-small enterprises to analysis their data in ease.

## Tech Stacks

- Framework: Nuxt.js
- UI Library: AntDesign
- Style management: UnoCSS (iconfont and simple styles) + SCSS (complex styles)
- Database: DrizzleORM + PostgreSQL
- Automation testing:
  - Unit testing: Vitest (with `@vue/test-utils`)
- Data processing, model fit and prefiction: Python
- Package management: pnpm, pdm

## Project Structure

- docs/
- app/
  - models/ : python script, application to run data processing, analysis; subfolder by type
    - regression/
    - classification/
    - association/
    - recommendations/
    - clsutering-segmentation/
  - pages/
  - styles/
  - app.vue

## Development

1. Config `.env`
2. Setup your local PostgreSQL using docker compose.
3. Run `pnpm run db:generate`
4. Run `pnpm run db:migrate`
