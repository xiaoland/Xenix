export {}; // keep this file a module

declare global {
  interface Window {
    electronAPI: {
      openDialog: (options?: Electron.OpenDialogOptions) => Promise<string[]>;
    };
  }
}
