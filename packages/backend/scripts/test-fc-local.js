import { spawn } from 'child_process';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const distFCDir = path.join(__dirname, '..', 'dist-fc');

console.log('Testing FC build locally...');
console.log('Make sure to set environment variables in .env.fc');
console.log('');

// Simulate FC environment
const env = {
  ...process.env,
  NODE_ENV: 'production',
  FC_FUNC_CODE_PATH: distFCDir,
};

const nodeProcess = spawn('node', ['index.js'], {
  cwd: distFCDir,
  env,
  stdio: 'inherit',
});

nodeProcess.on('error', (error) => {
  console.error('Failed to start server:', error);
  process.exit(1);
});

nodeProcess.on('exit', (code) => {
  console.log(`Server exited with code ${code}`);
  process.exit(code);
});

// Graceful shutdown
process.on('SIGINT', () => {
  nodeProcess.kill('SIGINT');
});
