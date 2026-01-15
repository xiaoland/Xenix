import fs from 'fs-extra';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const workers = [
  { name: 'batch-train', handler: 'batch-train.js' },
  { name: 'single-train', handler: 'single-train.js' },
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
    await fs.ensureDir(workerDir);

    const pythonDest = path.join(workerDir, 'python');
    await fs.remove(pythonDest);
    await fs.copy(pythonSource, pythonDest, {
      filter: (src) => {
        const basename = path.basename(src);
        return basename !== '__pycache__' && !basename.includes('.test.');
      },
    });
    console.log(`    ✓ Python scripts copied`);

    const handlerSource = path.join(adapterSource, worker.handler);
    const handlerDest = path.join(workerDir, 'index.js');
    if (await fs.pathExists(handlerSource)) {
      await fs.copy(handlerSource, handlerDest);
      console.log(`    ✓ Handler copied (${worker.handler})`);
    }

    const distDirs = ['core', 'utils', 'types'];
    for (const dir of distDirs) {
      const srcDir = path.join(__dirname, '..', 'dist', dir);
      const destDir = path.join(workerDir, dir);
      if (await fs.pathExists(srcDir)) {
        await fs.copy(srcDir, destDir);
      }
    }
    console.log(`    ✓ Dependencies copied`);

    await fs.writeJSON(
      path.join(workerDir, 'package.json'),
      {
        name: `@xenix/ml-${worker.name}-worker`,
        version: '1.0.0',
        type: 'module',
        main: 'index.js',
        dependencies: { pg: '^8.13.1', pino: '^9.7.0' },
      },
      { spaces: 2 }
    );
    console.log(`    ✓ package.json created\n`);
  }

  console.log('✓ All FC workers prepared!');
}

copyToWorkers().catch((error) => {
  console.error('Error:', error);
  process.exit(1);
});
