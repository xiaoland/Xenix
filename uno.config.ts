import presetIcons from '@unocss/preset-icons';
import { defineConfig, presetWind } from 'unocss';

export default defineConfig({
  presets: [
    presetWind(),
    presetIcons({
      collections: {
        mdi: () => import('@iconify-json/mdi').then((i) => i.default),
      },
    }),
  ],
});
