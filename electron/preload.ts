import { contextBridge, ipcRenderer } from "electron";

contextBridge.exposeInMainWorld("electronAPI", {
  openDialog: (options?: Electron.OpenDialogOptions) =>
    ipcRenderer.invoke("dialog:open", options),
});
