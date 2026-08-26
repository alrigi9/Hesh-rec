interface Window {
  electronAPI: {
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
  };
}

const RECMAP_BASE = 'https://recmap.tech';

export type AppState =
  | 'idle'
  | 'preparing'
  | 'recording'
  | 'saving'
  | 'saved'
  | 'uploading'
  | 'processing'
  | 'completed'
  | 'disk_error'
  | 'upload_error';

// ==========================================
// 🎚️ Audio Gain & Volume Calibration Config
// ==========================================
export const AUDIO_CONFIG = {
  MIC_GAIN: 1.5,       // Boost microphone volume (1.5x)
  SYSTEM_GAIN: 0.7,    // Reduce system loopback volume (0.7x)
};

let mediaRecorder: MediaRecorder | null = null;

let audioContext: AudioContext | null = null;
let micStream: MediaStream | null = null;
let systemStream: MediaStream | null = null;
let elapsedSeconds = 0;
let recordingStartTime = 0;
let timerInterval: ReturnType<typeof setInterval> | null = null;
let animationFrameId: number | null = null;
let analyser: AnalyserNode | null = null;
let lastBackupPath: string | null = null;

// DOM Elements
const toggleBtn = document.getElementById('toggleBtn') as HTMLButtonElement;
const btnLabel = document.getElementById('btnLabel') as HTMLSpanElement;
const btnIcon = document.getElementById('btnIcon') as HTMLSpanElement;
const timerEl = document.getElementById('timerEl') as HTMLDivElement;
const statusBadge = document.getElementById('statusBadge') as HTMLSpanElement;
const canvas = document.getElementById('audioVisualizer') as HTMLCanvasElement;
const canvasCtx = canvas.getContext('2d');

const settingsBtn = document.getElementById('settingsBtn') as HTMLButtonElement;
const settingsPanel = document.getElementById('settingsPanel') as HTMLDivElement;
const closeSettingsBtn = document.getElementById('closeSettingsBtn') as HTMLButtonElement;
const folderPathText = document.getElementById('folderPathText') as HTMLDivElement;
const changeFolderBtn = document.getElementById('changeFolderBtn') as HTMLButtonElement;
const openCurrentFolderBtn = document.getElementById('openCurrentFolderBtn') as HTMLButtonElement;
const resetFolderBtn = document.getElementById('resetFolderBtn') as HTMLButtonElement;

const folderBtn = document.getElementById('folderBtn') as HTMLButtonElement;
const logoutBtn = document.getElementById('logoutBtn') as HTMLButtonElement;
const minBtn = document.getElementById('minBtn') as HTMLButtonElement;
const closeBtn = document.getElementById('closeBtn') as HTMLButtonElement;

// Settings Panel Handlers
async function refreshSettingsPath() {
  try {
    const res = await window.electronAPI.getRecordingFolder();
    if (folderPathText) {
      folderPathText.textContent = res.folderPath;
      folderPathText.title = res.folderPath + (res.isDefault ? ' (المجلد الافتراضي)' : '');
    }
  } catch (e) {}
}

if (settingsBtn && settingsPanel) {
  settingsBtn.addEventListener('click', () => {
    const isHidden = settingsPanel.classList.contains('hidden');
    if (isHidden) {
      refreshSettingsPath();
      settingsPanel.classList.remove('hidden');
    } else {
      settingsPanel.classList.add('hidden');
    }
  });
}

if (closeSettingsBtn && settingsPanel) {
  closeSettingsBtn.addEventListener('click', () => {
    settingsPanel.classList.add('hidden');
  });
}

if (changeFolderBtn) {
  changeFolderBtn.addEventListener('click', async () => {
    try {
      const res = await window.electronAPI.selectRecordingFolder();
      if (res.success && res.folderPath) {
        folderPathText.textContent = res.folderPath;
        folderPathText.title = res.folderPath;
      } else if (res.error) {
        alert(res.error);
      }
    } catch (e) {}
  });
}

if (openCurrentFolderBtn) {
  openCurrentFolderBtn.addEventListener('click', () => {
    window.electronAPI.openRecordingsFolder();
  });
}

if (resetFolderBtn) {
  resetFolderBtn.addEventListener('click', async () => {
    try {
      const res = await window.electronAPI.resetRecordingFolder();
      if (res.folderPath) {
        folderPathText.textContent = res.folderPath;
        folderPathText.title = res.folderPath + ' (المجلد الافتراضي)';
      }
    } catch (e) {}
  });
}

// Window Control Listeners
folderBtn.addEventListener('click', () => window.electronAPI.openRecordingsFolder());
logoutBtn.addEventListener('click', async () => {
  if (confirm('هل تريد تسجيل الخروج والتبديل لحساب آخر؟')) {
    await window.electronAPI.logout();
  }
});
minBtn.addEventListener('click', () => window.electronAPI.minimize());
closeBtn.addEventListener('click', () => window.electronAPI.close());


// Visualizer function
function drawVisualizer() {
  if (!analyser || !canvasCtx) return;
  const bufferLength = analyser.frequencyBinCount;
  const dataArray = new Uint8Array(bufferLength);
  analyser.getByteFrequencyData(dataArray);

  canvasCtx.clearRect(0, 0, canvas.width, canvas.height);

  const barWidth = 4;
  const gap = 2;
  const totalBars = Math.floor(canvas.width / (barWidth + gap));
  const step = Math.max(1, Math.floor(bufferLength / totalBars));

  for (let i = 0; i < totalBars; i++) {
    const value = dataArray[i * step] || 0;
    const percent = value / 255;
    const barHeight = Math.max(2, percent * canvas.height);
    const x = i * (barWidth + gap);
    const y = (canvas.height - barHeight) / 2;

    const gradient = canvasCtx.createLinearGradient(0, 0, 0, canvas.height);
    gradient.addColorStop(0, '#60a5fa');
    gradient.addColorStop(1, '#3b82f6');

    canvasCtx.fillStyle = gradient;
    canvasCtx.beginPath();
    canvasCtx.roundRect(x, y, barWidth, barHeight, 2);
    canvasCtx.fill();
  }

  animationFrameId = requestAnimationFrame(drawVisualizer);
}

function clearVisualizer() {
  if (animationFrameId) {
    cancelAnimationFrame(animationFrameId);
    animationFrameId = null;
  }
  if (canvasCtx) {
    canvasCtx.clearRect(0, 0, canvas.width, canvas.height);
  }
}

// --- Central Authenticated Request Helper with Single 401 Retry ---
async function fetchWithAuth(url: string, options: RequestInit = {}, retryOn401 = true): Promise<Response> {
  const token = await window.electronAPI.getValidToken();
  if (!token) {
    throw new Error('انتهت صلاحية الجلسة، يرجى تسجيل الدخول مجدداً');
  }

  const reqHeaders: Record<string, string> = {
    ...(options.headers as Record<string, string> || {}),
    Authorization: `Bearer ${token}`,
  };

  let res = await fetch(url, { ...options, headers: reqHeaders });

  // 401 Single Retry Guard
  if (res.status === 401 && retryOn401) {
    console.warn('[RECORDER API] 401 received. Forcing token refresh and retrying once...');
    const freshToken = await window.electronAPI.getValidToken(true);
    if (freshToken) {
      reqHeaders.Authorization = `Bearer ${freshToken}`;
      res = await fetch(url, { ...options, headers: reqHeaders });
    }
  }

  return res;
}

let currentState: AppState = 'idle';
let hasDiskWriteError = false;
let chunkQueue: Promise<void> = Promise.resolve();

// --- Central State Machine & UI Manager ---
function setAppState(state: AppState, message?: string) {
  currentState = state;
  statusBadge.onclick = null;

  switch (state) {
    case 'idle':
      statusBadge.textContent = message || 'جاهز للتسجيل';
      statusBadge.className = 'status-badge';
      btnLabel.textContent = 'ابدأ التسجيل';
      toggleBtn.removeAttribute('disabled');
      toggleBtn.classList.remove('recording');
      break;

    case 'preparing':
      statusBadge.textContent = message || 'جاري إعداد مصادر الصوت...';
      statusBadge.className = 'status-badge';
      btnLabel.textContent = 'ابدأ التسجيل';
      toggleBtn.setAttribute('disabled', 'true');
      toggleBtn.classList.remove('recording');
      break;

    case 'recording':
      statusBadge.textContent = message || '🔴 تسجيل النظام + المايك (محفوظ على القرص)';
      statusBadge.className = 'status-badge recording';
      btnLabel.textContent = 'إيقاف التسجيل';
      toggleBtn.removeAttribute('disabled');
      toggleBtn.classList.add('recording');
      break;

    case 'saving':
      statusBadge.textContent = message || '⏳ جاري حفظ التسجيل...';
      statusBadge.className = 'status-badge uploading';
      btnLabel.textContent = 'جاري الحفظ والمعالجة...';
      toggleBtn.setAttribute('disabled', 'true');
      toggleBtn.classList.remove('recording');
      break;

    case 'saved':
      statusBadge.textContent = message || 'تم حفظ التسجيل';
      statusBadge.className = 'status-badge uploading';
      btnLabel.textContent = 'جاري الحفظ والمعالجة...';
      toggleBtn.setAttribute('disabled', 'true');
      toggleBtn.classList.remove('recording');
      break;

    case 'uploading':
      statusBadge.textContent = message || 'جاري الرفع والمعالجة...';
      statusBadge.className = 'status-badge uploading';
      btnLabel.textContent = 'جاري الحفظ والمعالجة...';
      toggleBtn.setAttribute('disabled', 'true');
      toggleBtn.classList.remove('recording');
      break;

    case 'processing':
      statusBadge.textContent = message || 'جاري الرفع والمعالجة...';
      statusBadge.className = 'status-badge uploading';
      btnLabel.textContent = 'جاري الحفظ والمعالجة...';
      toggleBtn.setAttribute('disabled', 'true');
      toggleBtn.classList.remove('recording');
      break;

    case 'completed':
      statusBadge.textContent = message || 'تم إرسال التسجيل بنجاح';
      statusBadge.className = 'status-badge success';
      statusBadge.onclick = () => window.electronAPI.openExternal(RECMAP_BASE);
      btnLabel.textContent = 'ابدأ التسجيل';
      toggleBtn.removeAttribute('disabled');
      toggleBtn.classList.remove('recording');
      break;

    case 'disk_error':
      statusBadge.textContent = message || '❌ خطأ في الحفظ على القرص (اضغط للفتح)';
      statusBadge.className = 'status-badge error';
      statusBadge.onclick = () => window.electronAPI.openRecordingsFolder();
      btnLabel.textContent = 'ابدأ التسجيل';
      toggleBtn.removeAttribute('disabled');
      toggleBtn.classList.remove('recording');
      break;

    case 'upload_error':
      statusBadge.textContent = message || '❌ فشل الرفع - تم الحفظ محلياً (اضغط للفتح)';
      statusBadge.className = 'status-badge error';
      statusBadge.onclick = () => window.electronAPI.openRecordingsFolder();
      btnLabel.textContent = 'ابدأ التسجيل';
      toggleBtn.removeAttribute('disabled');
      toggleBtn.classList.remove('recording');
      break;
  }
}

async function startRecording() {
  try {
    if (settingsPanel) settingsPanel.classList.add('hidden');

    // Pre-flight check: Verify target recording folder is accessible and writable
    const folderStatus = await window.electronAPI.checkRecordingDirStatus();
    if (!folderStatus.ok) {
      throw new Error(folderStatus.error || 'مجلد التسجيلات غير متاح، يرجى اختيار مجلد آخر');
    }

    setAppState('preparing', 'جاري إعداد مصادر الصوت...');
    hasDiskWriteError = false;
    chunkQueue = Promise.resolve();


    // 1. Microphone capture
    try {
      micStream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });
    } catch (e) {
      console.warn('Microphone capture failed:', e);
      micStream = null;
    }

    // 2. Windows System Loopback Audio
    try {
      systemStream = await navigator.mediaDevices.getDisplayMedia({
        video: true,
        audio: true,
      });
    } catch (e) {
      console.error('getDisplayMedia error:', e);
      systemStream = null;
    }

    const systemAudioTracks = systemStream ? systemStream.getAudioTracks() : [];
    const micAudioTracks = micStream ? micStream.getAudioTracks() : [];

    if (micAudioTracks.length === 0 && systemAudioTracks.length === 0) {
      throw new Error('لم يتم العثور على أي قناة صوتية نشطة');
    }

    // 3. Audio Mixing via AudioContext with Separate Gain Calibration
    audioContext = new AudioContext();
    if (audioContext.state === 'suspended') {
      await audioContext.resume();
    }

    const destination = audioContext.createMediaStreamDestination();
    const masterGain = audioContext.createGain();

    analyser = audioContext.createAnalyser();
    analyser.fftSize = 64;

    masterGain.connect(destination);
    masterGain.connect(analyser);

    // Microphone Gain Pipeline (Boost: 1.5x)
    if (micStream && micAudioTracks.length > 0) {
      const micSource = audioContext.createMediaStreamSource(micStream);
      const micGain = audioContext.createGain();
      micGain.gain.value = AUDIO_CONFIG.MIC_GAIN;
      micSource.connect(micGain).connect(masterGain);
      console.log(`✅ Connected Microphone (Gain: ${AUDIO_CONFIG.MIC_GAIN}x)`);
    }

    // System Audio Loopback Gain Pipeline (Reduce: 0.7x)
    if (systemStream && systemAudioTracks.length > 0) {
      const sysSource = audioContext.createMediaStreamSource(systemStream);
      const sysGain = audioContext.createGain();
      sysGain.gain.value = AUDIO_CONFIG.SYSTEM_GAIN;
      sysSource.connect(sysGain).connect(masterGain);
      console.log(`✅ Connected System Audio (Gain: ${AUDIO_CONFIG.SYSTEM_GAIN}x)`);
    }

    // 4. Initialize Active Recovery File on Disk via Main Process IPC
    const initDiskRes = await window.electronAPI.startActiveRecording();
    if (!initDiskRes.success) {
      throw new Error(initDiskRes.error || 'تعذر إنشاء ملف التسجيل على القرص');
    }
    console.log('✅ Active recording session initiated on disk:', initDiskRes.sessionId);

    // 5. MediaRecorder setup with direct disk streaming
    const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
      ? 'audio/webm;codecs=opus'
      : 'audio/webm';

    mediaRecorder = new MediaRecorder(destination.stream, { mimeType });

    mediaRecorder.ondataavailable = (event) => {
      if (!event.data || event.data.size === 0) return;
      const blob = event.data;

      // Sequential promise queue to guarantee strict write order
      chunkQueue = chunkQueue.then(async () => {
        try {
          const arrayBuffer = await blob.arrayBuffer();
          const appendRes = await window.electronAPI.appendRecordingChunk(arrayBuffer);

          if (!appendRes.success) {
            // Check if this was a genuine disk write error while recording
            if (appendRes.diskError || (!appendRes.sessionClosed && currentState === 'recording')) {
              console.error('Disk chunk write failure:', appendRes.error);
              hasDiskWriteError = true;
              if (currentState === 'recording') {
                statusBadge.textContent = '⚠️ تحذير: خطأ في الحفظ على القرص';
                statusBadge.className = 'status-badge error';
              }
            }
          }
        } catch (chunkErr) {
          console.error('Error handling recorded chunk:', chunkErr);
          if (currentState === 'recording') {
            hasDiskWriteError = true;
            statusBadge.textContent = '⚠️ تحذير: خطأ في الحفظ على القرص';
            statusBadge.className = 'status-badge error';
          }
        }
      });
    };

    recordingStartTime = Date.now();
    mediaRecorder.start(2000);

    // Start Timer
    elapsedSeconds = 0;
    timerEl.textContent = '00:00';
    timerInterval = setInterval(() => {
      elapsedSeconds++;
      const m = String(Math.floor(elapsedSeconds / 60)).padStart(2, '0');
      const s = String(elapsedSeconds % 60).padStart(2, '0');
      timerEl.textContent = `${m}:${s}`;
    }, 1000);

    // Determine channel description
    let channelStatus = '🔴 تسجيل النظام + المايك (محفوظ على القرص)';
    if (systemAudioTracks.length > 0 && micAudioTracks.length > 0) {
      channelStatus = '🔴 تسجيل النظام + المايك (محفوظ على القرص)';
    } else if (systemAudioTracks.length > 0) {
      channelStatus = '🔴 تسجيل صوت النظام فقط (محفوظ على القرص)';
    } else {
      channelStatus = '⚠️ المايك فقط (صوت النظام غير متوفر)';
    }

    setAppState('recording', channelStatus);
    drawVisualizer();
  } catch (err: any) {
    console.error('Failed to start recording:', err);
    cleanupAudio();
    setAppState('disk_error', '❌ ' + (err.message || 'تعذر بدء التسجيل'));
  }
}

async function stopRecording() {
  if (currentState !== 'recording') return;

  if (timerInterval) {
    clearInterval(timerInterval);
    timerInterval = null;
  }
  clearVisualizer();

  setAppState('saving', '⏳ جاري حفظ التسجيل...');

  // 1. Stop MediaRecorder and wait for the final dataavailable + onstop events
  if (mediaRecorder && mediaRecorder.state !== 'inactive') {
    await new Promise<void>((resolve) => {
      if (!mediaRecorder) return resolve();
      mediaRecorder.onstop = () => resolve();
      try {
        mediaRecorder.stop();
      } catch (e) {
        resolve();
      }
    });
  }

  // 2. Detach event listeners to prevent any further events
  if (mediaRecorder) {
    mediaRecorder.ondataavailable = null;
    mediaRecorder.onstop = null;
  }

  // 3. Guarantee ALL in-flight sequential chunk writes are fully completed and acknowledged!
  await chunkQueue;

  // 4. Clean up audio tracks
  cleanupAudio();

  // 5. Finalize on disk and upload
  await handleRecordingFinalizeAndUpload();
}

function cleanupAudio() {
  if (micStream) {
    micStream.getTracks().forEach((t) => t.stop());
    micStream = null;
  }
  if (systemStream) {
    systemStream.getTracks().forEach((t) => t.stop());
    systemStream = null;
  }
  if (audioContext && audioContext.state !== 'closed') {
    audioContext.close().catch(() => {});
    audioContext = null;
  }
}

async function handleRecordingFinalizeAndUpload() {
  const exactDurationMs = Math.max(1000, Date.now() - recordingStartTime);
  const durationSeconds = exactDurationMs / 1000;

  console.log(`[RECORDER] Finalizing recording on disk (Duration: ${durationSeconds.toFixed(2)}s)...`);

  // 1. Finalize on disk via Main Process (guaranteed complete standard WebM stream)
  let finalizeRes: {
    success: boolean;
    filePath?: string;
    filename?: string;
    size?: number;
    buffer?: ArrayBuffer;
    isValid?: boolean;
    validationReason?: string;
    error?: string;
  };

  try {
    finalizeRes = await window.electronAPI.finalizeActiveRecording(exactDurationMs);
    if (!finalizeRes.success || !finalizeRes.buffer) {
      throw new Error(finalizeRes.error || 'فشل تثبيت الملف النهائي على القرص');
    }
    lastBackupPath = finalizeRes.filePath || null;
    console.log('✅ Finalized local recording on disk:', lastBackupPath, `(${finalizeRes.size} bytes)`);

    if (finalizeRes.isValid === false) {
      console.warn('WebM validation note:', finalizeRes.validationReason);
    }
  } catch (finErr: any) {
    console.error('Finalization error:', finErr);
    setAppState('disk_error', '❌ خطأ في تثبيت الملف النهائي (اضغط للفتح)');
    return;
  }

  // Local file is verified and safe on disk! Clear any disk warning immediately.
  hasDiskWriteError = false;
  setAppState('saved', 'تم حفظ التسجيل');

  // Brief pause for visual confirmation
  await new Promise((r) => setTimeout(r, 400));

  const filename = finalizeRes.filename || `desktop_rec_${Date.now()}.webm`;
  const blob = new Blob([finalizeRes.buffer], { type: 'audio/webm' });

  // 2. Upload to RecMap API using Centralized fetchWithAuth (Local copy is already guaranteed safe on disk)
  try {
    setAppState('uploading', 'جاري الرفع والمعالجة...');

    const urlRes = await fetchWithAuth(`${RECMAP_BASE}/api/upload-url`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ filename }),
    });

    if (!urlRes.ok) {
      const errText = await urlRes.text().catch(() => '');
      throw new Error(`تعذر إنشاء رابط الرفع (${urlRes.status})`);
    }

    const urlData = await urlRes.json();
    const uploadUrl = urlData.upload_url;
    const storagePath = urlData.storage_path;

    if (!uploadUrl || !storagePath) {
      throw new Error('بيانات رابط الرفع غير مكتملة');
    }

    // Direct PUT to Supabase Storage signed URL
    const uploadRes = await fetch(uploadUrl, {
      method: 'PUT',
      headers: {
        'Content-Type': 'audio/webm',
      },
      body: blob,
    });

    if (!uploadRes.ok) {
      throw new Error(`فشل رفع الملف (${uploadRes.status})`);
    }

    setAppState('processing', 'جاري الرفع والمعالجة...');

    const now = new Date();
    const formattedDate = now.toLocaleDateString('ar-SA', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });

    const meetingTitle = `تسجيل سطح المكتب — ${formattedDate}`;

    // Step A: Register Session in Supabase
    const processRes = await fetchWithAuth(`${RECMAP_BASE}/api/process-audio`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        storage_path: storagePath,
        title: meetingTitle,
        template: 'auto',
        language: 'auto',
        duration_seconds: durationSeconds,
        filename: filename,
      }),
    });

    const processData = await processRes.json().catch(() => ({}));
    if (!processRes.ok) {
      throw new Error(processData.error || `فشل بدء تسجيل الاجتماع (${processRes.status})`);
    }

    const sessionId = processData.session_id || processData.id || '';
    console.log('🎉 Session registered and processing initiated on server:', sessionId);

    setAppState('completed', 'تم إرسال التسجيل بنجاح');

  } catch (err: any) {
    console.error('Upload / Processing error:', err);
    setAppState('upload_error', '❌ فشل الرفع - تم الحفظ محلياً (اضغط للفتح)');
  }
}

toggleBtn.addEventListener('click', () => {
  if (currentState === 'recording') {
    stopRecording();
  } else if (
    currentState === 'idle' ||
    currentState === 'completed' ||
    currentState === 'disk_error' ||
    currentState === 'upload_error'
  ) {
    startRecording();
  }
});


