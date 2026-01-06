import path from "path";
import { spawn } from "child_process";
import { existsSync } from "fs";
import logger from "../../utils/logger/index.js";

/**
 * Check if PDM is installed
 */
export async function isPdmInstalled(): Promise<boolean> {
  return new Promise((resolve) => {
    const pdmCheck = spawn("pdm", ["--version"]);
    pdmCheck.on("close", (code) => {
      resolve(code === 0);
    });
    pdmCheck.on("error", () => {
      resolve(false);
    });
  });
}

/**
 * Install PDM if not available using official installation script
 * Supports installation without pip using curl/wget
 */
export async function installPdm(): Promise<void> {
  logger.info('PDM not found. Installing PDM...');

  // Try official PDM installer first (works without pip)
  // https://pdm-project.org/latest/#installation
  return new Promise((resolve, reject) => {
    // Use curl to download and execute the official installer
    const installer = spawn(
      "curl",
      ["-sSL", "https://pdm-project.org/install-pdm.py"],
      {
        shell: true,
      }
    );

    const python = spawn("python3", ["-"], {
      shell: true,
    });

    installer.stdout.pipe(python.stdin);

    installer.stderr.on("data", (data) => {
      logger.error({ message: data.toString() }, 'PDM Install - Curl error');
    });

    python.stdout.on("data", (data) => {
      logger.info({ message: data.toString() }, 'PDM Install');
    });

    python.stderr.on("data", (data) => {
      logger.error({ message: data.toString() }, 'PDM Install error');
    });

    python.on("close", (code) => {
      if (code === 0) {
        logger.info('PDM installed successfully using official installer');
        resolve();
      } else {
        logger.warn('Official installer failed, trying pip fallback...');
        // Fallback to pip if available
        installPdmViaPip().then(resolve).catch(reject);
      }
    });

    python.on("error", (error) => {
      logger.error({ error }, 'Failed to run Python for PDM installation');
      // Fallback to pip if available
      installPdmViaPip().then(resolve).catch(reject);
    });
  });
}

/**
 * Fallback: Install PDM via pip
 */
export async function installPdmViaPip(): Promise<void> {
  return new Promise((resolve, reject) => {
    const pip = spawn("pip", ["install", "--user", "pdm"]);

    pip.stdout.on("data", (data) => {
      logger.info({ message: data.toString() }, 'PDM Install - Pip');
    });

    pip.stderr.on("data", (data) => {
      logger.error({ message: data.toString() }, 'PDM Install - Pip error');
    });

    pip.on("close", (code) => {
      if (code === 0) {
        logger.info('PDM installed successfully via pip');
        resolve();
      } else {
        reject(new Error(`Failed to install PDM via pip: exit code ${code}`));
      }
    });

    pip.on("error", (error) => {
      reject(new Error(`Pip not available: ${error.message}`));
    });
  });
}

/**
 * Check if Python environment is set up (dependencies installed)
 */
export function isPythonEnvReady(): boolean {
  // Check if __pypackages__ directory exists (PDM's local package directory)
  const pyPackagesDir = path.join(process.cwd(), "__pypackages__");
  const pdmLockFile = path.join(process.cwd(), "pdm.lock");

  return existsSync(pyPackagesDir) && existsSync(pdmLockFile);
}

/**
 * Install Python dependencies using PDM
 */
export async function setupPythonEnvironment(): Promise<void> {
  logger.info('Setting up Python environment with PDM...');
  return new Promise((resolve, reject) => {
    const pdmInstall = spawn("pdm", ["install"], {
      cwd: process.cwd(),
      env: process.env,
    });

    pdmInstall.stdout.on("data", (data) => {
      logger.info({ message: data.toString() }, 'PDM Install');
    });

    pdmInstall.stderr.on("data", (data) => {
      logger.error({ message: data.toString() }, 'PDM Install error');
    });

    pdmInstall.on("close", (code) => {
      if (code === 0) {
        logger.info('Python environment setup completed');
        resolve();
      } else {
        reject(
          new Error(`Failed to setup Python environment: exit code ${code}`)
        );
      }
    });
  });
}

/**
 * Ensure Python environment is ready
 * Installs PDM if not available and sets up dependencies if needed
 */
export async function ensurePythonEnvironment(): Promise<void> {
  // Check if PDM is installed
  const pdmAvailable = await isPdmInstalled();

  if (!pdmAvailable) {
    await installPdm();
  }

  // Check if environment is ready
  if (!isPythonEnvReady()) {
    await setupPythonEnvironment();
  } else {
    logger.info('Python environment already configured');
  }
}

// Initialize environment on module load with proper mutex
let environmentInitialized = false;
let environmentInitPromise: Promise<void> | null = null;

/**
 * Get or create the initialization promise (prevents race conditions)
 */
export async function getInitPromise(): Promise<void> {
  if (environmentInitialized) {
    return Promise.resolve();
  }

  if (environmentInitPromise) {
    return environmentInitPromise;
  }

  environmentInitPromise = (async () => {
    try {
      await ensurePythonEnvironment();
      environmentInitialized = true;
    } catch (error) {
      logger.error({ error }, 'Failed to initialize Python environment');
      // Reset promise so it can be retried
      environmentInitPromise = null;
      throw error;
    }
  })();

  return environmentInitPromise;
}

/**
 * Get Python environment status
 */
export async function getPythonEnvStatus() {
  const pdmInstalled = await isPdmInstalled();
  const envReady = isPythonEnvReady();

  return {
    pdmInstalled,
    envReady,
    initialized: environmentInitialized,
    pyPackagesExists: existsSync(path.join(process.cwd(), "__pypackages__")),
    pdmLockExists: existsSync(path.join(process.cwd(), "pdm.lock")),
  };
}

/**
 * Manually trigger environment setup
 */
export async function setupEnvironment() {
  await getInitPromise();
  return getPythonEnvStatus();
}

/**
 * Force reinstall of Python environment
 */
export async function reinstallEnvironment() {
  environmentInitialized = false;
  environmentInitPromise = null;
  await setupPythonEnvironment();
  environmentInitialized = true;
  return getPythonEnvStatus();
}
