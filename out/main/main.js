import { app, BrowserWindow, dialog, shell, ipcMain } from "electron";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { fork } from "child_process";
import getPort from "get-port";
import __cjs_mod__ from "node:module";
const __filename = import.meta.filename;
const __dirname = import.meta.dirname;
const require2 = __cjs_mod__.createRequire(import.meta.url);
const __filename$1 = fileURLToPath(import.meta.url);
const __dirname$1 = path.dirname(__filename$1);
let win = null;
let serverProcess = null;
const NUXT_DEV_PORT = 3005;
async function waitForServer(port) {
  const url = `http://localhost:${port}`;
  const maxRetries = 100;
  let retries = 0;
  while (retries < maxRetries) {
    try {
      const response = await fetch(url);
      if (response.ok) return;
    } catch {
    }
    await new Promise((resolve) => setTimeout(resolve, 100));
    retries++;
  }
  throw new Error(`Server failed to start on port ${port} after 10s`);
}
async function createWindow() {
  win = new BrowserWindow({
    width: 1280,
    height: 800,
    show: false,
    autoHideMenuBar: true,
    // (可选) 设置图标
    // icon: path.join(process.resourcesPath, 'build/icon.png'),
    webPreferences: {
      // ✅ 修正：electron-vite 默认结构是 dist/main/index.js 和 dist/preload/index.js
      // 所以这里需要往上跳一级去找 preload
      preload: path.join(__dirname$1, "../preload/index.js"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false
      // 如果你需要使用 Node.js API，sandbox 设为 false
    }
  });
  win.once("ready-to-show", () => win?.show());
  if (!app.isPackaged) {
    console.log(`[Dev] Loading http://localhost:${NUXT_DEV_PORT}...`);
    try {
      await win.loadURL(`http://localhost:${NUXT_DEV_PORT}`);
    } catch (e) {
      console.error("Failed to load URL. Is Nuxt running?");
    }
    win.webContents.openDevTools();
  } else {
    try {
      const port = await getPort();
      const serverPath = path.join(
        process.resourcesPath,
        "server/server/index.mjs"
      );
      console.log(`[Prod] Starting server at: ${serverPath}`);
      serverProcess = fork(serverPath, [], {
        env: {
          ...process.env,
          PORT: port.toString(),
          NITRO_PORT: port.toString(),
          NODE_ENV: "production",
          // 确保子进程不被 Electron 变量干扰，纯净运行 Node
          ELECTRON_RUN_AS_NODE: "1"
        }
      });
      console.log(`[Prod] Waiting for server on port ${port}...`);
      await waitForServer(port);
      await win.loadURL(`http://localhost:${port}`);
    } catch (err) {
      console.error("[Prod] Failed to start embedded server:", err);
      dialog.showErrorBox(
        "Startup Error",
        "Failed to start local server.\n" + err
      );
    }
  }
  win.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: "deny" };
  });
}
function registerIpc() {
  ipcMain.handle(
    "dialog:open",
    async (_event, options = {}) => {
      const result = await dialog.showOpenDialog(win ?? void 0, {
        properties: ["openFile"],
        ...options
      });
      return result.canceled ? [] : result.filePaths;
    }
  );
}
app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    app.quit();
  }
});
app.on("before-quit", () => {
  if (serverProcess) {
    console.log("Killing embedded server process...");
    serverProcess.kill();
    serverProcess = null;
  }
});
app.on("activate", () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    createWindow();
  }
});
app.whenReady().then(() => {
  registerIpc();
  createWindow();
});
