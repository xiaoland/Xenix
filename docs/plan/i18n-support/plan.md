# Internationalization (i18n) Support Plan

## Overview

Xenix implements comprehensive internationalization support using **@nuxtjs/i18n** (v10.2.1), enabling the platform to serve users in multiple languages. This document outlines the i18n architecture, implementation details, and guidelines for maintaining and extending language support.

## Current Implementation Status

### Supported Languages

- **English (en)** - Default locale (ISO: en-US)
- **Simplified Chinese (zh-CN)** - Secondary locale (ISO: zh-CN)

### Technology Stack

- **Framework**: @nuxtjs/i18n (Nuxt module for Vue I18n)
- **Vue I18n Version**: 10.x (Composition API)
- **Strategy**: `no_prefix` (URLs remain the same for all locales)
- **Detection**: Browser language detection with cookie persistence

## Architecture

### 1. Configuration

#### Nuxt Configuration (`nuxt.config.ts`)

```typescript
i18n: {
  locales: [
    {
      code: "en",
      name: "English",
      file: "en.json",
      iso: "en-US",
    },
    {
      code: "zh-CN",
      name: "简体中文",
      file: "zh-CN.json",
      iso: "zh-CN",
    },
  ],
  langDir: "locales",
  defaultLocale: "en",
  strategy: "no_prefix",
  detectBrowserLanguage: {
    useCookie: true,
    cookieKey: "i18n_redirected",
    redirectOn: "root",
    alwaysRedirect: false,
    fallbackLocale: "en",
  },
}
```

**Key Configuration Options:**
- `strategy: "no_prefix"` - No locale prefix in URLs (e.g., `/` instead of `/en/` or `/zh-CN/`)
- `detectBrowserLanguage` - Automatically detects user's browser language on first visit
- `useCookie: true` - Persists language preference across sessions
- `fallbackLocale: "en"` - Falls back to English if translation is missing

#### I18n Module Configuration (`i18n.config.ts`)

```typescript
export default defineI18nConfig(() => ({
  legacy: false,        // Use Composition API (Vue I18n 9+)
  locale: "en",         // Initial locale
  fallbackLocale: "en", // Fallback locale
  messages: {},         // Messages loaded from JSON files
}));
```

### 2. Translation Files

#### File Structure

Translation files are located in the project root:

```
i18n/
└── locales/
    ├── en.json      (357 lines, ~14KB)
    └── zh-CN.json   (399 lines, ~15KB)
```

The `langDir: "locales"` configuration in `nuxt.config.ts` points to this directory relative to the i18n module's base path.

#### Translation Organization

Translations are organized hierarchically by feature/domain:

```json
{
  "app": { ... },              // Application-level strings
  "navigation": { ... },       // Navigation menu items
  "home": { ... },             // Home page
  "projects": { ... },         // Project management
  "datasets": { ... },         // Dataset management
  "workItems": { ... },        // Work items
  "steps": {                   // ML workflow steps
    "prepare": { ... },
    "tune": { ... },
    "predict": { ... }
  },
  "training": { ... },         // Model training
  "tuning": { ... },           // Hyperparameter tuning
  "prediction": { ... },       // Prediction results
  "models": { ... },           // ML model names
  "metrics": { ... },          // Evaluation metrics
  "common": { ... },           // Shared UI strings
  "messages": { ... },         // Success/error messages
  "status": { ... }            // Status labels
}
```

### 3. Components

#### LanguageSwitcher Component

**Location**: `app/components/common/LanguageSwitcher.vue`

A dropdown button component that allows users to switch between available languages:

```vue
<template>
  <a-dropdown>
    <a-button class="inline-flex items-center">
      <span class="i-mdi-translate mr-2" />
      {{ currentLocaleName }}
      <span class="i-mdi-chevron-down ml-2" />
    </a-button>
    <template #overlay>
      <a-menu @click="handleLocaleChange">
        <a-menu-item
          v-for="locale in availableLocales"
          :key="locale.code"
        >
          {{ locale.name }}
        </a-menu-item>
      </a-menu>
    </template>
  </a-dropdown>
</template>
```

**Features**:
- Displays current language name
- Lists all available locales
- Highlights current selection
- Uses Ant Design Vue dropdown/menu components
- Includes translation icon (MDI icon set)

**Integration**: Used in `PageHeader.vue` component, visible on all pages.

### 4. Usage Patterns

#### In Vue Templates

Use the `$t()` global function:

```vue
<template>
  <h1>{{ $t("home.title") }}</h1>
  <p>{{ $t("home.subtitle") }}</p>
  
  <!-- With interpolation -->
  <span>{{ $t("projects.workItemsCount", { count: 5 }) }}</span>
  
  <!-- Dynamic keys -->
  <span>{{ $t(`status.${currentStatus}`) }}</span>
</template>
```

#### In Script Setup (Composition API)

Use the `useI18n()` composable:

```typescript
<script setup lang="ts">
import { useI18n } from "vue-i18n";

const { t, locale, setLocale } = useI18n();

// Translation function
const message = t("common.success");

// Current locale
console.log(locale.value); // "en" or "zh-CN"

// Change locale programmatically
await setLocale("zh-CN");
</script>
```

#### Common Composables Using i18n

Several composables leverage i18n for localized messages:

- `usePrepareStep.ts` - Data preparation messages
- `useFormatters.ts` - Number/date formatting
- `useModelTraining.ts` - Training status messages
- `useUploadStep.ts` - File upload feedback
- `useFileUpload.ts` - Upload validation messages

### 5. Translation Guidelines

#### Adding New Translations

1. **Add English translation** in `i18n/locales/en.json`:
   ```json
   {
     "newFeature": {
       "title": "New Feature",
       "description": "Feature description"
     }
   }
   ```

2. **Add corresponding Chinese translation** in `i18n/locales/zh-CN.json`:
   ```json
   {
     "newFeature": {
       "title": "新功能",
       "description": "功能描述"
     }
   }
   ```

3. **Use in components**:
   ```vue
   <h2>{{ $t("newFeature.title") }}</h2>
   ```

#### Best Practices

1. **Namespace Organization**: Group related translations under meaningful namespaces
   ```json
   {
     "feature": {
       "action": "Action",
       "status": "Status",
       "error": "Error message"
     }
   }
   ```

2. **Consistent Key Naming**: Use camelCase for consistency
   - ✅ `createProject`
   - ❌ `create_project`, `create-project`

3. **Interpolation**: Use placeholders for dynamic content
   ```json
   {
     "greeting": "Hello, {name}!",
     "itemCount": "{count} items"
   }
   ```

4. **Pluralization**: Handle singular/plural forms
   ```json
   {
     "items": "no items | {count} item | {count} items"
   }
   ```

5. **Fallback Values**: Always provide English as the default
   - English should be complete and high-quality
   - Other languages can fall back to English if missing

6. **Avoid Hardcoded Text**: All user-facing strings should use `$t()` or `t()`
   - ✅ `{{ $t("common.cancel") }}`
   - ❌ `Cancel`

## Browser Language Detection

### How It Works

1. **First Visit**: 
   - Checks browser's preferred language
   - Sets locale if supported (en or zh-CN)
   - Falls back to English if not supported
   - Saves preference in cookie (`i18n_redirected`)

2. **Subsequent Visits**:
   - Reads locale from cookie
   - Applies saved preference

3. **Manual Override**:
   - User selects language via LanguageSwitcher
   - Updates cookie with new preference
   - Overrides browser detection

### Cookie Storage

- **Cookie Name**: `i18n_redirected`
- **Value**: Locale code (e.g., "en", "zh-CN")
- **Persistence**: Across browser sessions
- **Scope**: Site-wide

## Adding New Languages

To add support for a new language (e.g., Spanish):

### Step 1: Create Translation File

Create `i18n/locales/es.json` with all translations:

```json
{
  "app": {
    "title": "Xenix",
    "subtitle": "Plataforma de Entrenamiento y Predicción de Modelos de Machine Learning"
  },
  "navigation": {
    "home": "Inicio",
    "projects": "Proyectos",
    "pythonEnv": "Entorno Python"
  },
  // ... continue with all translations
}
```

### Step 2: Update Nuxt Configuration

Add the locale to `nuxt.config.ts`:

```typescript
i18n: {
  locales: [
    {
      code: "en",
      name: "English",
      file: "en.json",
      iso: "en-US",
    },
    {
      code: "zh-CN",
      name: "简体中文",
      file: "zh-CN.json",
      iso: "zh-CN",
    },
    {
      code: "es",
      name: "Español",
      file: "es.json",
      iso: "es-ES",
    },
  ],
  // ... other config
}
```

### Step 3: Test

1. Clear browser cookies
2. Restart dev server: `pnpm dev`
3. Test language switching via LanguageSwitcher
4. Verify all translations appear correctly

## Feature Coverage

### Fully Translated Areas

All user-facing text is internationalized, including:

- ✅ Navigation menus
- ✅ Home page and project lists
- ✅ Project management (CRUD operations)
- ✅ Dataset management (upload, selection)
- ✅ ML Workflow steps (Prepare, Tune, Predict)
- ✅ Model selection interface
- ✅ Hyperparameter tuning (auto/manual)
- ✅ Training logs and status messages
- ✅ Evaluation metrics display
- ✅ Prediction results interface
- ✅ Error messages and validation feedback
- ✅ Success notifications
- ✅ Python environment setup page
- ✅ Form labels and placeholders
- ✅ Button labels
- ✅ Status indicators

### Technical Content Not Translated

Some technical content remains in English across all locales:

- Model names (e.g., "Linear Regression", "XGBoost")
- Metric abbreviations (MSE, MAE, R²)
- Column names in datasets
- API endpoints
- Log messages (structured JSON)

## Testing i18n

### Manual Testing Checklist

1. ✅ Language switcher is visible and accessible
2. ✅ Current language is highlighted in dropdown
3. ✅ All pages render correctly in each language
4. ✅ No missing translations (no translation keys visible)
5. ✅ Dynamic content interpolation works correctly
6. ✅ Browser detection works on first visit
7. ✅ Cookie persistence works across sessions
8. ✅ Fallback to English for missing keys

### Automated Testing

Currently, the project uses Vitest for unit testing. Consider adding i18n tests:

```typescript
// Example test structure
describe('i18n', () => {
  it('should load English translations', () => {
    const { t } = useI18n();
    expect(t('app.title')).toBe('Xenix');
  });

  it('should switch to Chinese', async () => {
    const { locale, setLocale } = useI18n();
    await setLocale('zh-CN');
    expect(locale.value).toBe('zh-CN');
  });
});
```

## Performance Considerations

### Loading Strategy

- **Lazy Loading**: Not currently enabled (all locales loaded on startup)
- **Bundle Size**: Each locale file is ~14-15KB (minimal impact)
- **Future Optimization**: Consider lazy loading for large applications with many locales

### Caching

- Translations are cached after initial load
- No server-side translation lookup
- Client-side only (all translations bundled with app)

## Maintenance

### Regular Tasks

1. **Synchronize Keys**: Ensure all locale files have the same keys
2. **Review Translations**: Periodically review translation quality
3. **Update Documentation**: Keep this plan in sync with implementation

### Tools and Scripts

Consider adding maintenance scripts:

```bash
# Check for missing translation keys
npm run i18n:check

# Generate translation report
npm run i18n:report

# Validate JSON syntax
npm run i18n:validate
```

## Known Limitations

1. **No Prefix Strategy**: URLs do not reflect current locale (e.g., no `/en/` or `/zh-CN/` prefix)
   - Simpler URL structure
   - Shared links display in user's preferred language (via cookie or browser detection)
   - SEO considerations for multi-language sites (search engines may not detect locale-specific content)

2. **Client-Side Only**: Translations are client-side rendered
   - Works well for SPA/desktop app
   - Consider SSR for better SEO if deploying as web app

3. **No Right-to-Left (RTL) Support**: Current implementation assumes LTR languages
   - Would require CSS adjustments for RTL languages (Arabic, Hebrew)

## Future Enhancements

### Potential Improvements

1. **Locale-Specific Formatting**
   - Numbers (1,000 vs 1.000)
   - Dates (MM/DD/YYYY vs DD/MM/YYYY)
   - Currency

2. **Content Localization**
   - Documentation translations
   - Help tooltips
   - Tutorial content

3. **User Preferences**
   - Save language preference to user profile (when auth is added)
   - Per-project language settings

4. **Translation Management**
   - Integration with translation management platforms (e.g., Crowdin, Lokalise)
   - Automated translation updates
   - Translation memory

5. **Additional Languages**
   - Japanese (ja)
   - Korean (ko)
   - French (fr)
   - German (de)

## Resources

### Official Documentation

- [@nuxtjs/i18n Documentation](https://i18n.nuxtjs.org/)
- [Vue I18n Documentation](https://vue-i18n.intlify.dev/)
- [ICU Message Syntax](https://unicode-org.github.io/icu/userguide/format_parse/messages/)

### Related Files

- `nuxt.config.ts` - Nuxt i18n module configuration
- `i18n.config.ts` - Vue I18n configuration
- `i18n/locales/en.json` - English translations
- `i18n/locales/zh-CN.json` - Chinese translations
- `app/components/common/LanguageSwitcher.vue` - Language switcher component
- `app/components/common/PageHeader.vue` - Page header with language switcher

### Code Examples

See the following files for i18n usage patterns:
- `app/composables/usePrepareStep.ts`
- `app/composables/useModelTraining.ts`
- `app/pages/work-items/[id].vue`
- `app/pages/index.vue`

## Conclusion

Xenix's i18n implementation provides a solid foundation for supporting multiple languages. The architecture is clean, maintainable, and extensible. By following the guidelines in this document, developers can easily add new languages and maintain translation quality across the application.

For questions or suggestions regarding i18n support, please refer to the main documentation or contact the development team.
