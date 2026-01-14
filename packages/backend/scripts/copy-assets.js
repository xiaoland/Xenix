import fs from 'fs-extra';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const rootDir = path.join(__dirname, '..');
const srcMLDir = path.join(rootDir, 'src', 'business', 'ml');
const distFCDir = path.join(rootDir, 'dist-fc');
const destMLDir = path.join(distFCDir, 'ml');

async function copyAssets() {
  console.log('Copying Python scripts to dist-fc/ml...');

  // Copy all Python files
  await fs.copy(srcMLDir, destMLDir, {
    filter: (src) => {
      // Only copy .py files, exclude TypeScript and test files
      return src.endsWith('.py') || fs.statSync(src).isDirectory();
    },
  });

  console.log('✓ Python scripts copied successfully!');
  console.log(`  Source: ${srcMLDir}`);
  console.log(`  Destination: ${destMLDir}`);
}

copyAssets().catch(console.error);
