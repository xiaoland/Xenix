/**
 * Copy Python scripts to dist directory for runtime access
 */
import fs from 'fs-extra';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const pythonSource = path.join(__dirname, '..', 'src', 'python');
const pythonDest = path.join(__dirname, '..', 'dist', 'python');

async function copyPython() {
  console.log('Copying Python scripts to dist...\n');
  console.log(`  Source: ${pythonSource}`);
  console.log(`  Dest:   ${pythonDest}`);

  // Remove existing python directory
  await fs.remove(pythonDest);

  // Copy Python scripts
  await fs.copy(pythonSource, pythonDest, {
    filter: (src) => {
      // Skip __pycache__ and test files
      const basename = path.basename(src);
      if (basename === '__pycache__') return false;
      if (basename.includes('.test.') || basename.includes('.spec.'))
        return false;
      return true;
    },
  });

  console.log('  ✓ Copied\n');
  console.log('✓ Python scripts copied successfully!');
}

copyPython().catch((error) => {
  console.error('Error copying Python scripts:', error);
  process.exit(1);
});
