/**
 * Builds Python layer package for Aliyun FC
 *
 * Creates directory structure:
 *   python-layer/
 *     python/
 *       lib/
 *         python3.10/
 *           site-packages/
 *
 * This structure is required by Aliyun FC for Python layers.
 * Dependencies are installed from requirements.txt using pip.
 */
import fs from 'fs-extra';
import path from 'path';
import { execSync } from 'child_process';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const rootDir = path.join(__dirname, '..');
const layerDir = path.join(rootDir, 'python-layer');
const pythonDir = path.join(layerDir, 'python');
const sitePackagesDir = path.join(pythonDir, 'lib', 'python3.10', 'site-packages');
const requirementsFile = path.join(rootDir, 'python-workers', 'auto_tune', 'requirements.txt');

async function buildPythonLayer() {
  console.log('🐍 Building Python layer for Aliyun FC...\n');

  // Check if requirements.txt exists
  if (!fs.existsSync(requirementsFile)) {
    console.error(`❌ Error: requirements.txt not found at ${requirementsFile}`);
    process.exit(1);
  }

  // Clean and recreate directory structure
  console.log('📁 Creating directory structure...');
  await fs.remove(layerDir);
  await fs.mkdirs(sitePackagesDir);
  console.log(`   Created: ${layerDir}`);
  console.log(`   Created: ${sitePackagesDir}\n`);

  // Install dependencies
  console.log('📦 Installing Python dependencies from requirements.txt...');
  console.log(`   Source: ${requirementsFile}\n`);

  try {
    execSync(
      `pip install -r "${requirementsFile}" -t "${sitePackagesDir}" --no-cache-dir --upgrade`,
      {
        stdio: 'inherit',
        cwd: rootDir
      }
    );
  } catch (error) {
    console.error('\n❌ Failed to install Python dependencies');
    console.error('Make sure you have pip installed and accessible in your PATH');
    process.exit(1);
  }

  // Get layer size
  const getDirectorySize = (dirPath) => {
    let totalSize = 0;
    const files = fs.readdirSync(dirPath);

    for (const file of files) {
      const filePath = path.join(dirPath, file);
      const stats = fs.statSync(filePath);

      if (stats.isDirectory()) {
        totalSize += getDirectorySize(filePath);
      } else {
        totalSize += stats.size;
      }
    }

    return totalSize;
  };

  const layerSize = getDirectorySize(layerDir);
  const layerSizeMB = (layerSize / (1024 * 1024)).toFixed(2);

  console.log('\n✅ Python layer built successfully!');
  console.log(`   Location: ${layerDir}`);
  console.log(`   Size: ${layerSizeMB} MB`);
  console.log('\n📋 Next steps:');
  console.log('   1. Review the layer contents if needed');
  console.log('   2. Run: pnpm run deploy:layer');
  console.log('   3. Or deploy everything: pnpm run deploy:all\n');

  // Warn if layer is too large
  if (layerSize > 250 * 1024 * 1024) {
    console.warn('⚠️  Warning: Layer size exceeds 250MB');
    console.warn('   Aliyun FC has limits on layer size (typically 250MB)');
    console.warn('   Consider removing unnecessary dependencies\n');
  }
}

buildPythonLayer().catch((error) => {
  console.error('❌ Error building Python layer:', error.message);
  process.exit(1);
});
