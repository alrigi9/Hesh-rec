import { contextBridge, ipcRenderer } from 'electron';

export interface ElectronAPI {
  getValidToken: (forceRefresh?: boolean) => Promise<string | null>;
  getUserEmail: () => Promise<string | null>;
  logout: () => Promise<void>;
  startActiveRecording: () => Promise<{ success: boolean; sessionId?: string; error?: string }>;
  appendRecordingChunk: (buffer: ArrayBuffer) => Promise<{
    success: boolean;
    totalBytes?: number;
    error?: string;
    diskError?: boolean;
    sessionClosed?: boolean;
  }>;
  finalizeActiveRecording: (durationMs: number, customFilename?: string) => Promise<{
    success: boolean;
    filePath?: string;
    filename?: string;
    size?: number;
    buffer?: ArrayBuffer;
    isValid?: boolean;
    validationReason?: string;
    error?: string;
  }>;
  cancelActiveRecording: () => Promise<{ success: boolean }>;
  saveAudioBackup: (buffer: ArrayBuffer, filename: string) => Promise<{ success: boolean; filePath?: string; error?: string }>;
  getRecordingFolder: () => Promise<{ folderPath: string; isDefault?: boolean }>;
  selectRecordingFolder: () => Promise<{ success?: boolean; canceled?: boolean; folderPath: string; error?: string }>;
  resetRecordingFolder: () => Promise<{ folderPath: string }>;
  checkRecordingDirStatus: () => Promise<{ ok: boolean; folderPath: string; error?: string }>;
  openRecordingsFolder: () => Promise<void>;
  openExternal: (url: string) => Promise<void>;
  minimize: () => void;
  close: () => void;
}

const api: ElectronAPI = {
  getValidToken: (forceRefresh?: boolean) => ipcRenderer.invoke('get-valid-token', forceRefresh),
  getUserEmail: () => ipcRenderer.invoke('get-user-email'),
  logout: () => ipcRenderer.invoke('logout'),
  startActiveRecording: () => ipcRenderer.invoke('recording-start'),
  appendRecordingChunk: (buffer: ArrayBuffer) => ipcRenderer.invoke('recording-append-chunk', buffer),
  finalizeActiveRecording: (durationMs: number, customFilename?: string) => ipcRenderer.invoke('recording-finalize', durationMs, customFilename),
  cancelActiveRecording: () => ipcRenderer.invoke('recording-cancel'),
  saveAudioBackup: (buffer: ArrayBuffer, filename: string) => ipcRenderer.invoke('save-audio-backup', buffer, filename),
  getRecordingFolder: () => ipcRenderer.invoke('get-recording-folder'),
  selectRecordingFolder: () => ipcRenderer.invoke('select-recording-folder'),
  resetRecordingFolder: () => ipcRenderer.invoke('reset-recording-folder'),
  checkRecordingDirStatus: () => ipcRenderer.invoke('check-recording-dir-status'),
  openRecordingsFolder: () => ipcRenderer.invoke('open-recordings-folder'),
  openExternal: (url: string) => ipcRenderer.invoke('open-external', url),
  minimize: () => ipcRenderer.send('minimize-window'),
  close: () => ipcRenderer.send('close-window'),
};

contextBridge.exposeInMainWorld('electronAPI', api);


