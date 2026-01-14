import { defineConfig } from 'tsup';

export default defineConfig({
  entry: [
    'src/index.ts',
    'src/adapters/stdio/index.ts',
    'src/adapters/aliyun-fc/auto-tune.ts',
    'src/adapters/aliyun-fc/manual-tune.ts',
    'src/adapters/aliyun-fc/predict.ts',
    'src/utils/logger.ts',
  ],
  format: ['esm'],
  dts: true,
  clean: true,
  sourcemap: true,
  target: 'node18',
  external: ['pg-native'],
  noExternal: ['@xenix/shared'],
});
