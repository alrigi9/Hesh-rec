import { app, BrowserWindow, session, ipcMain, shell, desktopCapturer, safeStorage, screen, dialog } from 'electron';
import * as path from 'path';
import * as fs from 'fs';
// Standard WebM Container Validator (verifies EBML, Segment, Tracks, Opus, and Clusters)
export function validateWebmBuffer(buffer: Buffer): { valid: boolean; reason?: string } {
  if (!buffer || buffer.length < 100) return { valid: false, reason: 'File too small (<100 bytes)' };
  if (buffer.readUInt32BE(0) !== 0x1a45dfa3) return { valid: false, reason: 'Missing EBML magic 0x1A45DFA3' };
  
  const hasSegment = buffer.indexOf(Buffer.from([0x18, 0x53, 0x80, 0x67])) !== -1;
  if (!hasSegment) return { valid: false, reason: 'Missing Segment element' };

  const hasTracks = buffer.indexOf(Buffer.from([0x16, 0x54, 0xae, 0x6b])) !== -1;
  if (!hasTracks) return { valid: false, reason: 'Missing Tracks element' };

  const hasOpus = buffer.indexOf(Buffer.from('A_OPUS', 'utf-8')) !== -1;
  if (!hasOpus) return { valid: false, reason: 'Missing Opus audio track' };

  const hasCluster = buffer.indexOf(Buffer.from([0x1f, 0x43, 0xb6, 0x75])) !== -1;
  if (!hasCluster) return { valid: false, reason: 'Missing audio Cluster packets' };

  return { valid: true };
}


let isAppReady = false;
let userDataDir = '';


function log(msg: string) {
  const ts = new Date().toISOString();
  const line = `[${ts}] ${msg}`;
  console.log(line);
  if (isAppReady && userDataDir) {
    try {
      const logPath = path.join(userDataDir, 'app.log');
      fs.appendFileSync(logPath, line + '\n', 'utf-8');
    } catch (e) {}
  }
}

// --- Session Store Interfaces ---
export interface AuthSession {
  access_token: string;
  refresh_token?: string | null;
  expires_at?: number | null; // Unix timestamp in seconds
  user_email?: string | null;
}

interface PersistedAuthFile {
  encryptedSession?: string; // base64 ciphertext from safeStorage
  // Legacy fields (for migration only):
  auth_token?: string;
  user_email?: string;
}

// --- App Settings Store ---
interface AppSettings {
  recordingFolder?: string;
}

class AppSettingsStore {
  private filePath: string;
  private settings: AppSettings = {};

  constructor(baseDir: string) {
    this.filePath = path.join(baseDir, 'recmap-settings.json');
    this.load();
  }

  private load() {
    try {
      if (fs.existsSync(this.filePath)) {
        const raw = fs.readFileSync(this.filePath, 'utf-8');
        this.settings = JSON.parse(raw);
      }
    } catch (e) {
      log('[SettingsStore] Error loading settings: ' + e);
      this.settings = {};
    }
  }

  private save() {
    try {
      fs.writeFileSync(this.filePath, JSON.stringify(this.settings, null, 2), 'utf-8');
    } catch (e) {
      log('[SettingsStore] Error saving settings: ' + e);
    }
  }

  getRecordingFolder(): string | null {
    return this.settings.recordingFolder || null;
  }

  setRecordingFolder(folderPath: string | null) {
    if (folderPath) {
      this.settings.recordingFolder = folderPath;
    } else {
      delete this.settings.recordingFolder;
    }
    this.save();
  }
}

// --- Secure AuthStore with Electron safeStorage ---
class SecureAuthStore {
  private filePath: string;
  private sessionData: AuthSession | null = null;

  constructor(baseDir: string) {
    this.filePath = path.join(baseDir, 'recmap-auth.json');
    this.loadAndMigrate();
  }

  private loadAndMigrate() {
    try {
      if (!fs.existsSync(this.filePath)) {
        this.sessionData = null;
        return;
      }

      const raw = fs.readFileSync(this.filePath, 'utf-8');
      const parsed: PersistedAuthFile = JSON.parse(raw);

      // 1. Migration of legacy plaintext auth file
      if (parsed.auth_token) {
        log('[AuthStore] Found legacy plaintext auth. Migrating immediately to safeStorage...');
        const legacySession: AuthSession = {
          access_token: parsed.auth_token,
          user_email: parsed.user_email || null,
        };

        // Extract expires_at from JWT if present
        try {
          const parts = parsed.auth_token.split('.');
          if (parts.length === 3) {
            const payload = JSON.parse(Buffer.from(parts[1], 'base64').toString('utf-8'));
            if (payload.exp && typeof payload.exp === 'number') {
              legacySession.expires_at = payload.exp;
            }
          }
        } catch (e) {}

        this.sessionData = legacySession;
        // Save immediately in encrypted format (this wipes plaintext fields from disk)
        this.save();
        log('[AuthStore] Migration complete. Plaintext credentials eliminated.');
        return;
      }

      // 2. Load encrypted session
      if (parsed.encryptedSession) {
        if (!safeStorage.isEncryptionAvailable()) {
          log('[AuthStore] WARNING: safeStorage is not available on this environment.');
          this.sessionData = null;
          return;
        }

        const cipherBuffer = Buffer.from(parsed.encryptedSession, 'base64');
        const decryptedJson = safeStorage.decryptString(cipherBuffer);
        this.sessionData = JSON.parse(decryptedJson);
        log('[AuthStore] Successfully decrypted and loaded auth session via safeStorage.');
      } else {
        this.sessionData = null;
      }
    } catch (err) {
      log('[AuthStore] Failed to load/decrypt auth store: ' + err);
      this.sessionData = null;
    }
  }

  private save() {
    try {
      if (!this.sessionData) {
        if (fs.existsSync(this.filePath)) {
          fs.unlinkSync(this.filePath);
        }
        log('[AuthStore] Deleted auth store file on logout.');
        return;
      }

      if (!safeStorage.isEncryptionAvailable()) {
        log('[AuthStore] Cannot save: safeStorage is not available.');
        return;
      }

      const plainJson = JSON.stringify(this.sessionData);
      const encryptedBuffer = safeStorage.encryptString(plainJson);
      const base64Cipher = encryptedBuffer.toString('base64');

      const fileContent: PersistedAuthFile = {
        encryptedSession: base64Cipher,
      };

      fs.writeFileSync(this.filePath, JSON.stringify(fileContent, null, 2), 'utf-8');
      log('[AuthStore] Encrypted session safely written to disk.');
    } catch (err) {
      log('[AuthStore] Failed to save encrypted auth store: ' + err);
    }
  }

  getSession(): AuthSession | null {
    return this.sessionData;
  }

  setSession(session: AuthSession) {
    this.sessionData = session;
    this.save();
  }

  getEmail(): string | null {
    return this.sessionData?.user_email || null;
  }

  clear() {
    this.sessionData = null;
    this.save();
  }
}

let store: SecureAuthStore;
let settingsStore: AppSettingsStore;
let mainWindow: BrowserWindow | null = null;
let loginWindow: BrowserWindow | null = null;
let loginCheckInterval: NodeJS.Timeout | null = null;

const RECMAP_URL = 'https://recmap.tech';

function getDefaultRecordingsDir(): string {
  try {
    const docsDir = app.getPath('documents');
    if (docsDir) {
      const defaultRecDir = path.join(docsDir, 'RecMap Recordings');
      if (!fs.existsSync(defaultRecDir)) {
        fs.mkdirSync(defaultRecDir, { recursive: true });
      }
      return defaultRecDir;
    }
  } catch (e) {
    log('[Settings] Could not resolve Documents path: ' + e);
  }
  const fallback = path.join(userDataDir || process.cwd(), 'Recordings');
  if (!fs.existsSync(fallback)) {
    fs.mkdirSync(fallback, { recursive: true });
  }
  return fallback;
}

function isUsingDefaultFolder(): boolean {
  return !settingsStore?.getRecordingFolder();
}

function getRecordingsDir(): string {
  const custom = settingsStore?.getRecordingFolder();
  let target = custom || getDefaultRecordingsDir();

  try {
    if (!fs.existsSync(target)) {
      fs.mkdirSync(target, { recursive: true });
    }
    fs.accessSync(target, fs.constants.W_OK);
    return target;
  } catch (err: any) {
    log(`[Settings] Target recording folder "${target}" is not accessible/writable (${err.message}). Falling back.`);
    const fallback = getDefaultRecordingsDir();
    return fallback;
  }
}


// --- Automatic Token Refresh Lifecycle Helper (Main Process Only) ---
async function refreshAuthSession(force = false): Promise<string | null> {
  const sess = store.getSession();
  if (!sess || !sess.access_token) {
    log('[Auth] No session found.');
    return null;
  }

  // 1. Proactive Expiration Check (Refresh if expires within 60s)
  if (!force) {
    let expSec = sess.expires_at;

    if (!expSec) {
      // Parse exp from JWT if not explicitly stored
      try {
        const parts = sess.access_token.split('.');
        if (parts.length === 3) {
          const payload = JSON.parse(Buffer.from(parts[1], 'base64').toString('utf-8'));
          if (payload.exp && typeof payload.exp === 'number') {
            expSec = payload.exp;
            sess.expires_at = expSec;
          }
        }
      } catch (e) {}
    }

    if (expSec) {
      const nowSec = Math.floor(Date.now() / 1000);
      const remainingSec = expSec - nowSec;
      if (remainingSec > 60) {
        // Token is valid and fresh
        return sess.access_token;
      }
      log(`[Auth] Access token near expiration (${remainingSec}s remaining). Triggering refresh.`);
    }
  }

  // 2. Perform refresh using refresh_token
  if (!sess.refresh_token) {
    log('[Auth] No refresh_token stored in session.');
    if (!force) return sess.access_token;
    store.clear();
    return null;
  }

  log('[Auth] Calling backend token refresh endpoint...');

  try {
    const refreshRes = await fetch(`${RECMAP_URL}/api/auth/refresh`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        refresh_token: sess.refresh_token,
      }),
    });

    if (refreshRes.ok) {
      const data = await refreshRes.json();
      if (data && data.access_token) {
        const updatedSession: AuthSession = {
          access_token: data.access_token,
          refresh_token: data.refresh_token || sess.refresh_token,
          expires_at: data.expires_at || (data.expires_in ? Math.floor(Date.now() / 1000) + data.expires_in : null),
          user_email: data.user?.email || sess.user_email,
        };
        store.setSession(updatedSession);
        log('[Auth] Token refresh successful. Encrypted session updated.');
        return updatedSession.access_token;
      }
    }

    const errStatus = refreshRes.status;
    const errText = await refreshRes.text().catch(() => '');
    log(`[Auth] Refresh endpoint returned status ${errStatus}: ${errText}`);

    if (errStatus === 400 || errStatus === 401) {
      log('[Auth] Refresh token is invalid or revoked. Clearing stored credentials.');
      store.clear();
      return null;
    }
  } catch (netErr: any) {
    log('[Auth] Network error during token refresh: ' + netErr.message);
  }

  // If refresh failed due to network error, return current access token if not forced
  return force ? null : sess.access_token;
}

function setupSystemAudioCapture() {
  log('[MAIN] Registering setDisplayMediaRequestHandler for loopback audio...');
  
  session.defaultSession.setDisplayMediaRequestHandler(async (request, callback) => {
    log('[MAIN] setDisplayMediaRequestHandler CALLED! Request: ' + JSON.stringify(request));
    try {
      const sources = await desktopCapturer.getSources({ types: ['screen'] });
      const primarySource = sources[0];
      log(`[MAIN] Found screen source: ${primarySource ? primarySource.name : 'none'} (id: ${primarySource?.id})`);
      
      callback({
        video: primarySource, // Pass screen source to satisfy Chromium display media
        audio: 'loopback',    // Capture Windows loopback audio
      });
      log('[MAIN] Callback executed with audio: loopback');
    } catch (err) {
      log('[MAIN] Error in setDisplayMediaRequestHandler: ' + err);
      callback({ audio: 'loopback' });
    }
  }, { useSystemPicker: false });

  session.defaultSession.setPermissionRequestHandler((webContents, permission, callback) => {
    log('[MAIN] Permission requested: ' + permission + ' -> GRANTED');
    callback(true);
  });
}

function createMainWindow() {
  log('Creating main recorder floating window...');
  if (mainWindow) {
    if (mainWindow.isMinimized()) mainWindow.restore();
    mainWindow.show();
    mainWindow.focus();
    return;
  }

  // Safe initial positioning anchored to primary display bottom-right work area
  let x: number | undefined;
  let y: number | undefined;
  const winWidth = 320;
  const winHeight = 230;

  try {
    const primary = screen.getPrimaryDisplay();
    const { width: screenWidth, height: screenHeight } = primary.workAreaSize;
    x = Math.max(10, Math.round(screenWidth - winWidth - 25));
    y = Math.max(10, Math.round(screenHeight - winHeight - 25));
  } catch (e) {
    log('Could not get primary display bounds: ' + e);
  }

  mainWindow = new BrowserWindow({
    width: winWidth,
    height: winHeight,
    minWidth: 300,
    minHeight: 200,
    x: x,
    y: y,
    alwaysOnTop: true,
    resizable: false,
    frame: false,
    transparent: true,
    backgroundColor: '#00000000',
    hasShadow: true,
    show: false,
    skipTaskbar: false,
    title: 'RecMap Desktop Recorder',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      backgroundThrottling: false,
      devTools: true,
    },
  });

  mainWindow.loadFile(path.join(__dirname, 'renderer', 'index.html'));

  mainWindow.once('ready-to-show', () => {
    log('MAIN WINDOW READY TO SHOW FIRED');
    mainWindow?.show();
    mainWindow?.focus();
  });

  mainWindow.webContents.on('did-finish-load', () => {
    log('Main window content loaded successfully');
  });

  mainWindow.on('closed', () => {
    log('Main window closed');
    mainWindow = null;
  });
}


function openLoginWindow() {
  log('Opening login window for ' + RECMAP_URL + '/login ...');
  if (loginWindow) {
    loginWindow.focus();
    return;
  }

  loginWindow = new BrowserWindow({
    width: 800,
    height: 850,
    center: true,
    title: 'RecMap — تسجيل الدخول',
    autoHideMenuBar: false,
    show: true,
    alwaysOnTop: true,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      devTools: true,
    },
  });

  loginWindow.once('ready-to-show', () => {
    log('READY TO SHOW FIRED');
    loginWindow?.show();
    loginWindow?.focus();
  });

  loginWindow.maximize();
  loginWindow.show();
  loginWindow.focus();

  loginWindow.loadURL(`${RECMAP_URL}/login`);

  loginWindow.webContents.on('did-finish-load', () => {
    log('Login window finished loading URL: ' + loginWindow?.webContents.getURL());
    loginWindow?.show();
    loginWindow?.focus();
  });

  loginWindow.webContents.on('did-fail-load', (_event, errorCode, errorDescription, validatedURL) => {
    log(`Login window failed to load ${validatedURL}: ${errorDescription} (${errorCode})`);
  });

  const extractTokenScript = `
    (() => {
      try {
        for (let i = 0; i < localStorage.length; i++) {
          const key = localStorage.key(i);
          if (key && (key.includes('auth-token') || key.startsWith('sb-'))) {
            const raw = localStorage.getItem(key);
            if (raw) {
              const parsed = JSON.parse(raw);
              const accessToken = parsed.access_token || (Array.isArray(parsed) ? parsed[0] : null);
              const refreshToken = parsed.refresh_token || (Array.isArray(parsed) ? parsed[1] : null);
              const expiresAt = parsed.expires_at || (parsed.expires_in ? Math.floor(Date.now() / 1000) + parsed.expires_in : null);
              const email = parsed.user?.email || null;

              if (accessToken && typeof accessToken === 'string' && accessToken.length > 20) {
                return {
                  access_token: accessToken,
                  refresh_token: refreshToken,
                  expires_at: expiresAt,
                  user_email: email,
                };
              }
            }
          }
        }
      } catch (e) {}
      return null;
    })()
  `;

  const checkAuth = async () => {
    if (!loginWindow || loginWindow.isDestroyed()) return;
    try {
      const result = await loginWindow.webContents.executeJavaScript(extractTokenScript);
      if (result && result.access_token) {
        log('Extracted valid Supabase session for user: ' + (result.user_email || 'unknown'));
        if (loginCheckInterval) {
          clearInterval(loginCheckInterval);
          loginCheckInterval = null;
        }

        store.setSession({
          access_token: result.access_token,
          refresh_token: result.refresh_token || null,
          expires_at: result.expires_at || null,
          user_email: result.user_email || null,
        });

        const win = loginWindow;
        loginWindow = null;
        win.close();
        createMainWindow();
      }
    } catch (e) {
      // Ignored
    }
  };

  loginWindow.webContents.on('did-navigate', (_event, url) => {
    log('Login window navigated to: ' + url);
    checkAuth();
  });

  loginCheckInterval = setInterval(checkAuth, 1000);

  loginWindow.on('closed', () => {
    log('Login window closed by user');
    loginWindow = null;
    if (loginCheckInterval) {
      clearInterval(loginCheckInterval);
      loginCheckInterval = null;
    }
    if (!store?.getSession() && !mainWindow) {
      log('No token and no main window. Exiting app.');
      app.quit();
    }
  });
}

interface ActiveRecordingSession {
  sessionId: string;
  partFilePath: string;
  fd: number | null;
  startTime: number;
  totalBytes: number;
  lastSyncTime: number;
  chunksCount: number;
}

let activeRecording: ActiveRecordingSession | null = null;

async function recoverDirectory(recDir: string) {
  try {
    if (!fs.existsSync(recDir)) return;
    const files = fs.readdirSync(recDir);
    const partFiles = files.filter(f => f.startsWith('.recmap-active-') && f.endsWith('.webm.part'));

    if (partFiles.length === 0) return;

    log(`[CrashRecovery] Found ${partFiles.length} unfinished recording recovery file(s) in: ${recDir}`);

    for (const partName of partFiles) {
      const partPath = path.join(recDir, partName);
      try {
        const stat = fs.statSync(partPath);
        if (stat.size > 2048) {
          const rawBuffer = fs.readFileSync(partPath);
          const validation = validateWebmBuffer(rawBuffer);

          const match = partName.match(/\.recmap-active-(\d+)\.webm\.part/);
          const timestamp = match ? match[1] : Date.now().toString();

          if (validation.valid) {
            const recoveredName = `recovered_rec_${timestamp}.webm`;
            const recoveredPath = path.join(recDir, recoveredName);
            fs.writeFileSync(recoveredPath, rawBuffer);
            
            if (fs.existsSync(recoveredPath) && fs.statSync(recoveredPath).size > 0) {
              fs.unlinkSync(partPath);
              log(`[CrashRecovery] Successfully recovered valid WebM: ${recoveredPath} (${stat.size} bytes)`);
            }
          } else {
            const corruptName = `unrecovered_corrupt_${timestamp}.webm.part`;
            log(`[CrashRecovery] Recovery file lacks valid container (${validation.reason}). Preserving as: ${corruptName}`);
            fs.renameSync(partPath, path.join(recDir, corruptName));
          }
        } else {
          log(`[CrashRecovery] Removing empty/tiny part file (${stat.size} bytes): ${partPath}`);
          fs.unlinkSync(partPath);
        }
      } catch (partErr: any) {
        log(`[CrashRecovery] Error recovering ${partName}: ${partErr.message}`);
      }
    }
  } catch (err: any) {
    log(`[CrashRecovery] Scan error in ${recDir}: ${err.message}`);
  }
}

async function scanAndRecoverInterruptedRecordings(recDir: string) {
  // 1. Scan currently active/configured recording folder
  await recoverDirectory(recDir);

  // 2. Scan legacy AppData Recordings directory if different (read-only scan)
  const legacyAppDataDir = path.join(userDataDir || process.cwd(), 'Recordings');
  if (path.resolve(legacyAppDataDir) !== path.resolve(recDir)) {
    await recoverDirectory(legacyAppDataDir);
  }
}

// --- IPC Registration ---
function setupIPC() {
  ipcMain.handle('get-valid-token', async (_event, forceRefresh?: boolean) => {
    return await refreshAuthSession(Boolean(forceRefresh));
  });

  ipcMain.handle('get-user-email', () => store.getEmail());

  ipcMain.handle('logout', async () => {
    log('User triggered logout');
    store.clear();

    try {
      await session.defaultSession.clearStorageData({
        storages: ['cookies', 'localstorage'],
      });
    } catch (e) {}

    if (mainWindow) {
      mainWindow.close();
      mainWindow = null;
    }
    openLoginWindow();
  });

  // --- Custom Recording Folder Settings IPC Handlers ---

  ipcMain.handle('get-recording-folder', () => {
    const folderPath = getRecordingsDir();
    return { folderPath, isDefault: isUsingDefaultFolder() };
  });

  ipcMain.handle('select-recording-folder', async () => {
    try {
      const current = getRecordingsDir();
      const result = await dialog.showOpenDialog(mainWindow || (undefined as any), {
        title: 'اختر مجلد حفظ تسجيلات RecMap',
        defaultPath: current,
        properties: ['openDirectory', 'createDirectory', 'promptToCreate'],
        buttonLabel: 'اختيار هذا المجلد',
      });

      if (result.canceled || result.filePaths.length === 0) {
        return { canceled: true, folderPath: getRecordingsDir() };
      }

      const selectedPath = result.filePaths[0];

      // Verify folder writability
      try {
        if (!fs.existsSync(selectedPath)) {
          fs.mkdirSync(selectedPath, { recursive: true });
        }
        fs.accessSync(selectedPath, fs.constants.W_OK);

        settingsStore.setRecordingFolder(selectedPath);
        log(`[Settings] Custom recording folder updated to: ${selectedPath}`);
        return { success: true, folderPath: selectedPath };
      } catch (writeErr: any) {
        log(`[Settings] Selected folder is not writable: ${selectedPath} (${writeErr.message})`);
        return {
          success: false,
          error: 'المجلد المختار غير متاح للكتابة، يرجى اختيار مجلد آخر',
          folderPath: getRecordingsDir(),
        };
      }
    } catch (err: any) {
      log(`[Settings] Error picking folder: ${err.message}`);
      return { success: false, error: err.message, folderPath: getRecordingsDir() };
    }
  });

  ipcMain.handle('reset-recording-folder', () => {
    settingsStore.setRecordingFolder(null);
    const defaultDir = getDefaultRecordingsDir();
    log(`[Settings] Reset recording folder to default: ${defaultDir}`);
    return { folderPath: defaultDir };
  });

  ipcMain.handle('check-recording-dir-status', () => {
    const target = getRecordingsDir();
    try {
      if (!fs.existsSync(target)) {
        fs.mkdirSync(target, { recursive: true });
      }
      fs.accessSync(target, fs.constants.W_OK);
      return { ok: true, folderPath: target };
    } catch (err: any) {
      return { ok: false, folderPath: target, error: `مجلد الحفظ غير متاح للكتابة: ${err.message}` };
    }
  });

  // --- Incremental Crash-Safe Recording IPC Handlers ---

  ipcMain.handle('recording-start', async () => {
    try {
      const recDir = getRecordingsDir();
      const sessionId = Date.now().toString();
      const partFileName = `.recmap-active-${sessionId}.webm.part`;
      const partFilePath = path.join(recDir, partFileName);

      // Open in write mode for sequential chunk appending
      const fd = fs.openSync(partFilePath, 'w');

      activeRecording = {
        sessionId,
        partFilePath,
        fd,
        startTime: Date.now(),
        totalBytes: 0,
        lastSyncTime: Date.now(),
        chunksCount: 0,
      };

      log(`[Recorder] Active recording initialized on disk: ${partFilePath}`);
      return { success: true, sessionId };
    } catch (err: any) {
      log(`[Recorder] ERROR initializing active recording: ${err.message}`);
      return { success: false, error: err.message };
    }
  });

  ipcMain.handle('recording-append-chunk', async (_event, arrayBuffer: ArrayBuffer) => {
    if (!activeRecording || activeRecording.fd === null) {
      return { success: false, error: 'No active recording session', sessionClosed: true };
    }
    if (!arrayBuffer || arrayBuffer.byteLength === 0) {
      return { success: true, totalBytes: activeRecording.totalBytes };
    }

    try {
      const nodeBuf = Buffer.from(arrayBuffer);
      fs.writeSync(activeRecording.fd, nodeBuf);
      activeRecording.totalBytes += nodeBuf.length;
      activeRecording.chunksCount++;

      // Periodic physical disk flush every 15 seconds to ensure durability
      const now = Date.now();
      if (now - activeRecording.lastSyncTime > 15000) {
        try {
          fs.fdatasyncSync(activeRecording.fd);
          activeRecording.lastSyncTime = now;
        } catch (syncErr) {}
      }

      return { success: true, totalBytes: activeRecording.totalBytes };
    } catch (err: any) {
      log(`[Recorder] CRITICAL: Failed to append chunk to disk: ${err.message}`);
      return { success: false, error: err.message, diskError: true };
    }
  });

  ipcMain.handle('recording-finalize', async (_event, durationMs: number, customFilename?: string) => {
    if (!activeRecording) {
      return { success: false, error: 'No active recording session to finalize' };
    }

    const sessionData = activeRecording;
    activeRecording = null;

    try {
      // 1. Flush & close active file descriptor
      if (sessionData.fd !== null) {
        try {
          fs.fsyncSync(sessionData.fd);
          fs.closeSync(sessionData.fd);
        } catch (e) {}
        sessionData.fd = null;
      }

      const recDir = getRecordingsDir();
      const finalFilename = customFilename || `desktop_rec_${sessionData.sessionId}.webm`;
      const finalFilePath = path.join(recDir, finalFilename);

      if (!fs.existsSync(sessionData.partFilePath)) {
        throw new Error(`Part file not found: ${sessionData.partFilePath}`);
      }

      // 2. Read full incrementally accumulated buffer
      const rawBuffer = fs.readFileSync(sessionData.partFilePath);
      if (rawBuffer.length === 0) {
        throw new Error('Recorded file is empty (0 bytes).');
      }

      log(`[Recorder] Finalizing recording (${rawBuffer.length} bytes, ${sessionData.chunksCount} chunks, ${(durationMs / 1000).toFixed(1)}s)...`);

      // 3. Validate WebM container integrity before saving
      const validation = validateWebmBuffer(rawBuffer);
      if (!validation.valid) {
        log(`[Recorder] WARNING: WebM validation warning: ${validation.reason}`);
      } else {
        log('[Recorder] WebM container verified (EBML, Segment, Tracks, Opus, Clusters OK).');
      }

      // 4. Write final verified recording to disk (pure unaltered standard WebM stream)
      fs.writeFileSync(finalFilePath, rawBuffer);

      // 5. Verify final file on disk
      const stat = fs.statSync(finalFilePath);
      if (stat.size === 0) {
        throw new Error('Finalized recording is 0 bytes.');
      }

      log(`[Recorder] Finalized recording verified on disk: ${finalFilePath} (${stat.size} bytes)`);

      // 6. ATOMIC CLEANUP: Safely delete .part recovery file only after final file is verified
      try {
        if (fs.existsSync(sessionData.partFilePath)) {
          fs.unlinkSync(sessionData.partFilePath);
        }
      } catch (unlinkErr) {}

      return {
        success: true,
        filePath: finalFilePath,
        filename: finalFilename,
        size: rawBuffer.length,
        buffer: rawBuffer.buffer.slice(rawBuffer.byteOffset, rawBuffer.byteOffset + rawBuffer.byteLength),
        isValid: validation.valid,
        validationReason: validation.reason,
      };
    } catch (err: any) {
      log(`[Recorder] Finalization error: ${err.message}`);
      return { success: false, error: err.message };
    }
  });

  ipcMain.handle('recording-cancel', async () => {
    if (!activeRecording) return { success: true };
    try {
      if (activeRecording.fd !== null) {
        try {
          fs.closeSync(activeRecording.fd);
        } catch (e) {}
      }
      if (fs.existsSync(activeRecording.partFilePath)) {
        fs.unlinkSync(activeRecording.partFilePath);
      }
    } catch (e) {}
    activeRecording = null;
    return { success: true };
  });

  ipcMain.handle('save-audio-backup', async (_event, buffer: ArrayBuffer, filename: string) => {
    try {
      const recDir = getRecordingsDir();
      const safeName = filename.replace(/[^a-zA-Z0-9._-]/g, '_');
      const targetPath = path.join(recDir, safeName);
      const nodeBuffer = Buffer.from(buffer);
      fs.writeFileSync(targetPath, nodeBuffer);
      log('Audio backup saved to: ' + targetPath);
      return { success: true, filePath: targetPath };
    } catch (err: any) {
      log('Failed to save audio backup: ' + err.message);
      return { success: false, error: err.message };
    }
  });

  ipcMain.handle('open-recordings-folder', () => {
    const dir = getRecordingsDir();
    log('Opening recordings folder: ' + dir);
    shell.openPath(dir);
  });

  ipcMain.handle('open-external', (_event, url: string) => {
    if (url.startsWith('https://') || url.startsWith('http://')) {
      log('Opening external URL: ' + url);
      shell.openExternal(url);
    }
  });

  ipcMain.on('minimize-window', () => {
    mainWindow?.minimize();
  });

  ipcMain.on('close-window', () => {
    log('User closed application');
    app.quit();
  });
}

const gotTheLock = app.requestSingleInstanceLock();
if (!gotTheLock) {
  console.log('Another instance is running. Quitting.');
  app.quit();
} else {
  app.on('second-instance', () => {
    log('Second instance attempted to launch. Bringing existing window to focus.');
    if (mainWindow) {
      if (mainWindow.isMinimized()) mainWindow.restore();
      mainWindow.show();
      mainWindow.focus();
    } else if (loginWindow) {
      if (loginWindow.isMinimized()) loginWindow.restore();
      loginWindow.show();
      loginWindow.focus();
    }
  });

  app.whenReady().then(async () => {
    isAppReady = true;
    userDataDir = app.getPath('userData');
    log('Electron app is ready. UserData dir: ' + userDataDir);

    store = new SecureAuthStore(userDataDir);
    settingsStore = new AppSettingsStore(userDataDir);
    setupSystemAudioCapture();
    setupIPC();

    // Scan for and recover any unfinished recordings from prior crashes
    const recDir = getRecordingsDir();
    await scanAndRecoverInterruptedRecordings(recDir);

    // Check if stored session is valid or refreshable
    const token = await refreshAuthSession(false);
    if (token) {
      log('Found valid or refreshed auth session. Opening main window.');
      createMainWindow();
    } else {
      log('No valid session found. Opening login window.');
      openLoginWindow();
    }
  });
}

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});


