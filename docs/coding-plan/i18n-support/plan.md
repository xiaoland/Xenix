# I18n Support Implementation Plan

## Overview

Add comprehensive i18n support to the frontend package using vue-i18n with lazy-loading for en and zh-CN locales, and include a language switcher in the header.

## Current State Analysis

- vue-i18n is already installed (v11.2.8)
- Locale files exist: en.json and zh-CN.json with translations
- i18n is initialized in main.ts but loads all messages synchronously
- Components are not using i18n; strings are hardcoded
- No language switcher in UI

## Implementation Strategy

### 1. Refactor i18n Setup for Lazy Loading

- Modify `main.ts` to create i18n instance without pre-loaded messages
- Create `loadLanguageAsync` function in a separate i18n utility file
- Load default locale (en) on app initialization
- Support dynamic loading of zh-CN when needed

### 2. Create Language Switcher Component

- Build `LanguageSwitcher.vue` component with dropdown for en/zh-CN
- Integrate into `DefaultLayout.vue` header
- Use Ant Design Select component for consistency

### 3. Update Layout and Navigation

- Replace hardcoded strings in `DefaultLayout.vue` with i18n keys
- Add navigation keys to locale files if missing
- Ensure proper i18n integration

### 4. Update Key Views to Use i18n

- Modify `HomeView.vue` to use $t for all user-facing text
- Update other critical views (Projects, Tasks, etc.) and their child components
- Ensure all buttons, labels, and messages are translatable

### 5. Add Missing Translation Keys

- Audit existing locale files for completeness
- Add keys for header, navigation, common UI elements
- Ensure zh-CN translations are accurate

### 6. Integrate Translation Validation Tools

- Install `vue-i18n-extract` as dev dependency
- Add npm script for checking missing and unused translations
- Configure script to scan Vue files and compare with locale JSON files
- Integrate into CI/CD pipeline for automated checks
- Add ESLint rules for i18n best practices (@intlify/eslint-plugin-vue-i18n)

### 7. Testing and Validation

- Test language switching functionality
- Verify lazy loading works (check network requests)
- Ensure all components display correctly in both languages
- Run translation validation tools and fix any issues

## Technical Details

### Lazy Loading Implementation

```typescript
// In i18n/index.ts
const loadedLanguages = ['en']

export async function loadLanguageAsync(lang: string) {
  if (loadedLanguages.includes(lang)) {
    i18n.global.locale.value = lang
    return
  }
  
  const messages = await import(`../locales/${lang}.json`)
  i18n.global.setLocaleMessage(lang, messages.default)
  loadedLanguages.push(lang)
  i18n.global.locale.value = lang
}
```

### Language Switcher Component

- Use `a-select` from Ant Design
- Options: English (en), 中文 (zh-CN)
- On change, call loadLanguageAsync and update locale

### File Structure Changes

```
packages/frontend/
├── package.json              # add vue-i18n-extract, eslint-plugin-vue-i18n
├── src/
│   ├── i18n/
│   │   ├── index.ts          # i18n setup and utilities
│   │   └── loadLanguage.ts   # lazy loading function
│   ├── components/
│   │   └── LanguageSwitcher.vue
│   ├── locales/              # existing
│   └── layouts/              # update DefaultLayout.vue
├── .eslintrc.js              # add i18n eslint rules
└── scripts/
    └── check-i18n.js         # custom script for translation validation
```

### Translation Validation Setup

```json
// package.json scripts
{
  "i18n:extract": "vue-i18n-extract report --vueFiles 'src/**/*.vue' --languageFiles 'src/locales/*.json'",
  "i18n:check": "npm run i18n:extract && echo 'Translation check complete'"
}
```

```javascript
// .eslintrc.js
{
  "extends": [
    "@intlify/vue-i18n/recommended"
  ],
  "settings": {
    "vue-i18n": {
      "localeDir": "./src/locales/*.json",
      "messageSyntaxVersion": "^11.0.0"
    }
  }
}
```

## Benefits

- Reduced initial bundle size (only load current language)
- Better performance for users not needing multiple languages
- Proper internationalization foundation for future expansion
- Consistent UI with language switching capability

## Risks and Mitigations

- Potential flash of untranslated content during language switch (mitigate with loading states)
- Bundle splitting may affect caching strategies (monitor and optimize)
- Need to ensure all new features include i18n keys from start

## Success Criteria

- Language switcher appears in header
- Switching languages updates all text immediately
- Network tab shows lazy loading of locale files
- All major UI elements are translatable
- Default language (en) loads on app start
- Translation validation tools are installed and functional
- `npm run i18n:check` successfully reports missing/unused keys
- ESLint catches i18n issues during development
