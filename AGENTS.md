# AGENTS.md for `Xenix`

Xenix provides an interface for teachers, mid-small enterprises to analysis their data in ease.

## Tech Stacks

- Framework: Nuxt.js
- UI Library: AntDesign
- Style management: UnoCSS (iconfont and simple styles) + SCSS (complex styles)
- Data processing, model fit and prefiction: Python (uses PDM)
- Package management: pnpm

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
