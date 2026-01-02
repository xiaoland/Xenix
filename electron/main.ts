import { app, BrowserWindow, dialog, ipcMain, shell } from "electron";
import path from "node:path";

// Directory helpers mirroring nuxt-electron quick-start structure
process.env.APP_ROOT = path.join(__dirname, "..");
export const MAIN_DIST = path.join(process.env.APP_ROOT, "dist-electron");
export const RENDERER_DIST = path.join(process.env.APP_ROOT, ".output/public");

process.env.VITE_PUBLIC = process.env.VITE_DEV_SERVER_URL
  ? path.join(process.env.APP_ROOT, "public")
  : RENDERER_DIST;

let win: BrowserWindow | null = null;

async function createWindow() {
  win = new BrowserWindow({
    width: 1280,
    height: 800,
    show: false,
    webPreferences: {
      preload: path.join(MAIN_DIST, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
    },
  });

  win.once("ready-to-show", () => win?.show());

  if (process.env.VITE_DEV_SERVER_URL) {
    await win.loadURL(process.env.VITE_DEV_SERVER_URL);
    if (process.env.NUXT_ELECTRON_OPEN_DEVTOOLS === "true") {
      win.webContents.openDevTools();
    }
  } else {
    await win.loadFile(path.join(process.env.VITE_PUBLIC!, "index.html"));
  }

  win.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: "deny" };
  });
}

function registerIpc() {
  ipcMain.handle(
    "dialog:open",
    async (_event, options: Electron.OpenDialogOptions = {}) => {
      const result = await dialog.showOpenDialog(win ?? undefined, {
        properties: ["openFile"],
        ...options,
      });
      return result.canceled ? [] : result.filePaths;
    }
  );
}

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    app.quit();
    win = null;
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
