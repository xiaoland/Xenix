import { defineConfig, presetWind } from "unocss";
import presetIcons from "@unocss/preset-icons";

export default defineConfig({
  presets: [
    presetWind(),
    presetIcons({
      collections: {
        mdi: () => import("@iconify-json/mdi").then((i) => i.default),
      },
    }),
  ],
});
