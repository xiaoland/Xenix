import { contextBridge, ipcRenderer } from "electron";
contextBridge.exposeInMainWorld("electronAPI", {
  openDialog: (options) => ipcRenderer.invoke("dialog:open", options)
});
