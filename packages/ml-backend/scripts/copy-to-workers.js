/**
 * Copy built adapters and Python scripts to FC worker directories
 * Prepares each worker for independent deployment to Aliyun FC
 */
import fs from 'fs-extra';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const workers = [
  { name: 'auto-tune', handler: 'auto-tune.js' },
  { name: 'manual-tune', handler: 'manual-tune.js' },
  { name: 'predict', handler: 'predict.js' },
];

const pythonSource = path.join(__dirname, '..', 'src', 'python');
const adapterSource = path.join(__dirname, '..', 'dist', 'adapters', 'aliyun-fc');
const workersBaseDir = path.join(__dirname, '..', 'fc-workers');

async function copyToWorkers() {
  console.log('Preparing FC workers...\n');

  for (const worker of workers) {
    const workerDir = path.join(workersBaseDir, worker.name);

    console.log(`  ${worker.name}:`);

    // Create worker directory if it doesn't exist
    await fs.ensureDir(workerDir);

    // Copy Python scripts
    const pythonDest = path.join(workerDir, 'python');
    await fs.remove(pythonDest);
    await fs.copy(pythonSource, pythonDest, {
      filter: (src) => {
        const basename = path.basename(src);
        if (basename === '__pycache__') return false;
        if (basename.includes('.test.') || basename.includes('.spec.'))
          return false;
        return true;
      },
    });
    console.log(`    ✓ Python scripts copied`);

    // Copy adapter handler as index.js
    const handlerSource = path.join(adapterSource, worker.handler);
    const handlerDest = path.join(workerDir, 'index.js');

    if (await fs.pathExists(handlerSource)) {
      await fs.copy(handlerSource, handlerDest);
      console.log(`    ✓ Handler copied (${worker.handler})`);
    } else {
      console.warn(`    ⚠ Handler not found: ${handlerSource}`);
    }

    // Copy all dependencies from dist (core, utils, types)
    const distDirs = ['core', 'utils', 'types'];
    for (const dir of distDirs) {
      const srcDir = path.join(__dirname, '..', 'dist', dir);
      const destDir = path.join(workerDir, dir);
      if (await fs.pathExists(srcDir)) {
        await fs.copy(srcDir, destDir);
      }
    }
    console.log(`    ✓ Dependencies copied`);

    // Create package.json for the worker
    const workerPackageJson = {
      name: `@xenix/ml-${worker.name}-worker`,
      version: '1.0.0',
      type: 'module',
      main: 'index.js',
      dependencies: {
        pg: '^8.13.1',
        pino: '^9.7.0',
      },
    };
    await fs.writeJSON(
      path.join(workerDir, 'package.json'),
      workerPackageJson,
      { spaces: 2 }
    );
    console.log(`    ✓ package.json created\n`);
  }

  console.log('✓ All FC workers prepared successfully!');
}

copyToWorkers().catch((error) => {
  console.error('Error preparing FC workers:', error);
  process.exit(1);
});
