# i18n Implementation Guide

## Overview

This document describes the internationalization (i18n) implementation in Xenix using vue-i18n with lazy loading.

## Architecture

### Lazy Loading

The application uses lazy loading for locale files to reduce the initial bundle size. Only the current language is loaded, and additional languages are loaded on-demand when the user switches languages.

**Implementation:**
- `packages/frontend/src/i18n/index.ts` - Core i18n setup with lazy loading
- `packages/frontend/src/main.ts` - Async initialization
- `packages/frontend/src/components/common/LanguageSwitcher.vue` - Language selector

### Supported Languages

- **English (en)** - Default language
- **Chinese (zh-CN)** - Secondary language

## How to Use

### In Vue Templates

Use the `$t()` function to translate strings:

```vue
<template>
  <h1>{{ $t('home.title') }}</h1>
  <p>{{ $t('home.subtitle') }}</p>
</template>
```

### In Script Setup

Import and use the `useI18n` composable:

```vue
<script setup lang="ts">
import { useI18n } from 'vue-i18n';

const { t } = useI18n();

const message = t('projects.createSuccess');
</script>
```

### Adding New Translations

1. Add the key to `packages/frontend/src/locales/en.json`
2. Add the same key to `packages/frontend/src/locales/zh-CN.json`
3. Use the key in your component with `$t('key')` or `t('key')`

Example:

```json
// en.json
{
  "myFeature": {
    "title": "My Feature",
    "description": "This is my feature"
  }
}

// zh-CN.json
{
  "myFeature": {
    "title": "我的功能",
    "description": "这是我的功能"
  }
}
```

## Development Tools

### Translation Validation

Check for missing or unused translation keys:

```bash
cd packages/frontend
npm run i18n:check
```

This will show:
- Missing translations (keys used in code but not in locale files)
- Unused translations (keys in locale files but not used in code)

### ESLint Integration

The project includes `@intlify/eslint-plugin-vue-i18n` for catching i18n issues during development:

```bash
npm run lint
```

ESLint rules configured:
- `@intlify/vue-i18n/no-unused-keys` - Warns about unused translation keys
- `@intlify/vue-i18n/no-missing-keys` - Warns about missing translation keys
- `@intlify/vue-i18n/no-raw-text` - (Optional) Enforces all text to use i18n

## Verifying Lazy Loading

To verify that locale files are loaded lazily:

1. Start the dev server: `npm run dev`
2. Open browser DevTools (F12)
3. Go to the Network tab
4. Navigate to the homepage (http://localhost:5173)
5. Look for a request to load `en.json`
6. Click the language switcher and select "中文"
7. Observe a new network request to load `zh-CN.json`

The locale files are loaded as separate chunks, demonstrating lazy loading.

## File Structure

```
packages/frontend/
├── src/
│   ├── i18n/
│   │   └── index.ts              # i18n configuration & lazy loading
│   ├── components/
│   │   └── common/
│   │       └── LanguageSwitcher.vue  # Language selector component
│   ├── locales/
│   │   ├── en.json               # English translations
│   │   └── zh-CN.json            # Chinese translations
│   └── main.ts                   # App initialization with i18n
└── package.json                  # Includes i18n dependencies
```

## Implementation Details

### Language Persistence

The selected language is persisted in `localStorage` with the key `xenix-locale`. This ensures the user's language preference is maintained across sessions.

### Fallback Behavior

If a translation key is missing in the selected language, the system automatically falls back to English (the fallback locale).

### Type Safety

The `SupportedLocale` type ensures only valid language codes can be used:

```typescript
export type SupportedLocale = 'en' | 'zh-CN';
```

## Future Enhancements

- Add more languages (Spanish, French, German, etc.)
- Implement i18n for all remaining views and components
- Add date/time/number formatting with i18n
- Enable stricter ESLint rules for raw text detection
- Add context-aware translations for pluralization
- Implement RTL (Right-to-Left) support for Arabic/Hebrew

## Testing

### Manual Testing Checklist

- [ ] Language switcher appears in header
- [ ] Default language is English on first load
- [ ] Switching to Chinese updates all text
- [ ] Switching back to English works correctly
- [ ] Language preference persists after page reload
- [ ] No console errors or warnings about missing keys
- [ ] Layout and formatting look correct in both languages

### Automated Testing

To add automated tests for i18n:

```typescript
import { mount } from '@vue/test-utils';
import { createI18n } from 'vue-i18n';
import HomeView from '@/views/HomeView.vue';

const i18n = createI18n({
  legacy: false,
  locale: 'en',
  messages: {
    en: { home: { title: 'Xenix' } }
  }
});

test('renders with i18n', () => {
  const wrapper = mount(HomeView, {
    global: {
      plugins: [i18n]
    }
  });
  expect(wrapper.text()).toContain('Xenix');
});
```

## Troubleshooting

### Missing Translation Warning

If you see warnings like `Not found 'key' key in 'en' locale messages`:

1. Check if the key exists in `locales/en.json`
2. Verify the key path is correct (e.g., `home.title` not `homeTitle`)
3. Ensure the locale file is properly formatted JSON
4. Clear browser cache and reload

### Language Not Switching

If the language doesn't change when clicking the switcher:

1. Check browser console for errors
2. Verify the locale file exists (e.g., `locales/zh-CN.json`)
3. Check network tab to see if the locale file is being loaded
4. Verify localStorage has the correct language code

## Resources

- [vue-i18n Documentation](https://vue-i18n.intlify.dev/)
- [Intlify ESLint Plugin](https://eslint-plugin-vue-i18n.intlify.dev/)
- [vue-i18n-extract Tool](https://github.com/pixari/vue-i18n-extract)
- [ICU Message Format](https://unicode-org.github.io/icu/userguide/format_parse/messages/)
