import fs from 'fs-extra';
import path from 'path';
import archiver from 'archiver';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const rootDir = path.join(__dirname, '..');
const distFCDir = path.join(rootDir, 'dist-fc');
const outputZip = path.join(rootDir, 'fc-deploy.zip');

async function packageForFC() {
  console.log('Creating FC deployment package...');

  // Create minimal package.json for FC
  const minimalPackageJson = {
    name: '@xenix/backend-fc',
    version: '1.0.0',
    type: 'module',
    main: 'index.js',
    engines: {
      node: '>=22.0.0',
    },
  };

  await fs.writeJSON(path.join(distFCDir, 'package.json'), minimalPackageJson, {
    spaces: 2,
  });

  // Copy requirements.txt
  await fs.copy(
    path.join(rootDir, 'requirements.txt'),
    path.join(distFCDir, 'requirements.txt')
  );

  // Create zip archive
  if (fs.existsSync(outputZip)) {
    fs.removeSync(outputZip);
  }

  const output = fs.createWriteStream(outputZip);
  const archive = archiver('zip', {
    zlib: { level: 9 }, // Maximum compression
  });

  output.on('close', () => {
    const sizeMB = (archive.pointer() / 1024 / 1024).toFixed(2);
    console.log(`✓ FC deployment package created: ${outputZip}`);
    console.log(`✓ Package size: ${sizeMB} MB`);
    console.log('');
    console.log('Next steps:');
    console.log('1. Upload fc-deploy.zip to Aliyun FC');
    console.log('2. Configure environment variables in FC console');
    console.log('3. Set up Python layer or bootstrap script');
    console.log('4. Configure function trigger (HTTP)');
  });

  archive.on('error', (err) => {
    throw err;
  });

  archive.pipe(output);
  archive.directory(distFCDir, false);
  await archive.finalize();
}

packageForFC().catch(console.error);
