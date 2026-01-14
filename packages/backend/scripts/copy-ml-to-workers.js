/**
 * Copy ML Python scripts to all worker directories
 * This ensures each worker has access to the ML modules
 */
import fs from 'fs-extra';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const workers = ['auto_tune', 'manual_tune', 'predict'];
const mlSourceDir = path.join(__dirname, '..', 'src', 'business', 'ml');
const workersBaseDir = path.join(__dirname, '..', 'python-workers');

async function copyMLScripts() {
  console.log('Copying ML scripts to worker directories...\n');

  for (const worker of workers) {
    const destDir = path.join(workersBaseDir, worker, 'ml');

    console.log(`  ${worker}:`);
    console.log(`    Source: ${mlSourceDir}`);
    console.log(`    Dest:   ${destDir}`);

    // Remove existing ml directory
    await fs.remove(destDir);

    // Copy ML scripts
    await fs.copy(mlSourceDir, destDir, {
      filter: (src) => {
        // Skip TypeScript files, test files, and __pycache__
        const basename = path.basename(src);
        const ext = path.extname(src);

        if (basename === '__pycache__') return false;
        if (ext === '.ts') return false;
        if (basename.includes('.test.') || basename.includes('.spec.')) return false;

        return true;
      },
    });

    console.log(`    ✓ Copied\n`);
  }

  console.log('✓ All ML scripts copied successfully!');
}

copyMLScripts().catch((error) => {
  console.error('Error copying ML scripts:', error);
  process.exit(1);
});
