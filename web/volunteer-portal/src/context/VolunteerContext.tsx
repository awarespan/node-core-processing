/**
 * AWARESPAN Volunteer Portal — Centralized State Machine & Context
 * Orchestrates connection lifecycle, permissions, media loop, and node communications.
 */

import React, {
  createContext,
  useContext,
  useState,
  useEffect,
  useRef,
  useCallback,
  ReactNode,
} from 'react';
import {
  AuthSession,
  AvailableDevices,
  AnnotatedFramePayload,
  ConnectionState,
  DetectionEvidence,
  PiDetectionEvent,
  MediaPermissionState,
  PiNodeConfig,
  PortalLog,
  SessionTelemetry,
  VolunteerMode,
  PiNodeCapabilities,
} from '../types';
import { getInitialConfig } from '../services/config';
import {
  authenticateOperator,
  clearSession,
  getActiveSession,
  isSessionValid,
} from '../services/auth';
import { MediaCaptureManager } from '../services/media';
import { PiConnectionClient } from '../services/piClient';

interface VolunteerContextValue {
  // State machine
  connectionState: ConnectionState;
  volunteerMode: VolunteerMode;
  setVolunteerMode: (mode: VolunteerMode) => void;

  // Configuration
  config: PiNodeConfig;
  updateConfig: (patch: Partial<PiNodeConfig>) => void;

  // Authentication
  session: AuthSession | null;
  login: (operatorId: string, totpCode: string) => Promise<{ success: boolean; error?: string }>;
  logout: () => void;

  // Media Devices & Permissions
  devices: AvailableDevices;
  permissionState: MediaPermissionState;
  selectCamera: (deviceId: string) => void;
  selectMicrophone: (deviceId: string) => void;
  refreshDevices: () => Promise<void>;
  localStream: MediaStream | null;
  videoRef: React.RefObject<HTMLVideoElement | null>;

  // Controls
  startVolunteering: () => Promise<void>;
  stopVolunteering: () => void;

  // Telemetry & Logs
  telemetry: SessionTelemetry;
  logs: PortalLog[];
  clearLogs: () => void;
  detectionEvidence: DetectionEvidence[];
  piCapabilities: PiNodeCapabilities | null;
}

const VolunteerContext = createContext<VolunteerContextValue | undefined>(undefined);

export const VolunteerProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [config, setConfig] = useState<PiNodeConfig>(getInitialConfig);
  const [session, setSession] = useState<AuthSession | null>(getActiveSession);
  const [connectionState, setConnectionState] = useState<ConnectionState>('NOT_CONNECTED');
  const [volunteerMode, setVolunteerMode] = useState<VolunteerMode>('camera');
  const [piCapabilities, setPiCapabilities] = useState<PiNodeCapabilities | null>(null);

  const [devices, setDevices] = useState<AvailableDevices>({
    cameras: [],
    microphones: [],
    selectedCameraId: '',
    selectedMicrophoneId: '',
  });

  const [permissionState, setPermissionState] = useState<MediaPermissionState>({
    camera: 'prompt',
    microphone: 'prompt',
  });

  const [localStream, setLocalStream] = useState<MediaStream | null>(null);
  const videoRef = useRef<HTMLVideoElement | null>(null);

  const [telemetry, setTelemetry] = useState<SessionTelemetry>({
    durationSeconds: 0,
    framesSent: 0,
    fps: 0,
    latencyMs: 0,
    bytesSent: 0,
    audioPeakLevel: 0,
    audioRmsLevel: 0,
    lastHeartbeatTs: null,
    reconnectAttempts: 0,
    cameraActive: false,
    microphoneActive: false,
    piNodeId: config.nodeId,
  });

  const [logs, setLogs] = useState<PortalLog[]>([]);
  const [detectionEvidence, setDetectionEvidence] = useState<DetectionEvidence[]>([]);
  const pendingDetectionsRef = useRef<Map<string, { event: PiDetectionEvent; timer: number }>>(new Map());

  // Services instances refs
  const mediaManagerRef = useRef<MediaCaptureManager>(new MediaCaptureManager());
  const piClientRef = useRef<PiConnectionClient | null>(null);

  // Intervals and counters
  const frameIntervalRef = useRef<number | null>(null);
  const audioIntervalRef = useRef<number | null>(null);
  const durationTimerRef = useRef<number | null>(null);
  const framesSentCountRef = useRef<number>(0);
  const bytesSentCountRef = useRef<number>(0);
  const fpsWindowRef = useRef<{ count: number; start: number }>({ count: 0, start: Date.now() });

  const addLog = useCallback((level: PortalLog['level'], category: PortalLog['category'], message: string) => {
    const newEntry: PortalLog = {
      id: Math.random().toString(36).substring(2, 9),
      timestamp: new Date().toLocaleTimeString(),
      level,
      category,
      message,
    };
    setLogs((prev) => [newEntry, ...prev.slice(0, 199)]);
  }, []);

  const clearLogs = useCallback(() => {
    setLogs([]);
  }, []);

  // Update telemetry helper
  const updateTelemetry = useCallback((patch: Partial<SessionTelemetry>) => {
    setTelemetry((prev) => ({ ...prev, ...patch }));
  }, []);

  // Match node threat events to the annotated frame emitted for the same frame_id.
  const handleDetectionEvent = useCallback((event: PiDetectionEvent) => {
    const eventKey = `${event.source_id || 'unknown'}:${event.frame_id}`;
    const previous = pendingDetectionsRef.current.get(eventKey);
    if (previous) window.clearTimeout(previous.timer);
    const timer = window.setTimeout(() => {
      const pending = pendingDetectionsRef.current.get(eventKey);
      if (pending?.event.event_id !== event.event_id) return;
      pendingDetectionsRef.current.delete(eventKey);
      setDetectionEvidence((items) => [{ event, imageUrl: '', capturedAt: Date.now() }, ...items].slice(0, 8));
      addLog('warn', 'media', `Detection ${event.event_id} arrived without its annotated frame.`);
    }, 2500);
    pendingDetectionsRef.current.set(eventKey, { event, timer });
    addLog('success', 'ack', `Node reported ${event.labels.join(', ') || 'a threat'}; waiting for annotated evidence.`);
  }, [addLog]);

  const handleAnnotatedFrame = useCallback((frame: AnnotatedFramePayload) => {
    const frameKey = `${frame.source_id || 'unknown'}:${frame.frame_id}`;
    const pending = pendingDetectionsRef.current.get(frameKey);
    if (!pending) return;
    window.clearTimeout(pending.timer);
    pendingDetectionsRef.current.delete(frameKey);
    const imageUrl = `data:image/jpeg;base64,${frame.annotated_b64}`;
    setDetectionEvidence((items) => [
      { event: pending.event, imageUrl, capturedAt: Date.now() },
      ...items.filter((item) => item.event.event_id !== pending.event.event_id),
    ].slice(0, 8));
    addLog('success', 'media', `Annotated evidence received for ${pending.event.event_id}.`);
  }, [addLog]);

  useEffect(() => () => {
    pendingDetectionsRef.current.forEach((pending) => window.clearTimeout(pending.timer));
    pendingDetectionsRef.current.clear();
  }, []);

  // Initialize PiConnectionClient
  useEffect(() => {
    const client = new PiConnectionClient(config, {
      onStatusChange: (status) => {
        if (status === 'connecting') {
          setConnectionState('CONNECTING');
          addLog('info', 'network', `Connecting to AWARESPAN node at ${config.piHost}:${config.piPort}...`);
        } else if (status === 'connected') {
          setConnectionState('AWAITING_PI_ACK');
          addLog('info', 'network', 'WebSocket connection established. Awaiting source acknowledgement...');
        } else if (status === 'reconnecting') {
          setConnectionState('RECONNECTING');
          addLog('warn', 'network', 'Network connection interrupted. Attempting reconnection...');
        } else if (status === 'disconnected') {
          // If we were volunteering and disconnected unintentionally
          setConnectionState((curr) => {
            if (curr === 'STOPPED_BY_USER' || curr === 'SESSION_EXPIRED') return curr;
            return 'CONNECTION_LOST';
          });
          updateTelemetry({ cameraActive: false, microphoneActive: false });
        } else if (status === 'rejected') {
          setConnectionState('BACKEND_UNAVAILABLE');
          addLog('error', 'network', 'AWARESPAN node rejected volunteer session.');
        }
      },
      onSourceAcknowledged: (source) => {
        addLog('success', 'ack', `AWARESPAN node acknowledged active source: [${source.toUpperCase()}]`);

        setConnectionState((curr) => {
          if (source === 'camera') {
            updateTelemetry({ cameraActive: true });
            return curr === 'MICROPHONE_CONNECTED' ? 'BOTH_CONNECTED' : 'CAMERA_CONNECTED';
          } else {
            updateTelemetry({ microphoneActive: true });
            return curr === 'CAMERA_CONNECTED' ? 'BOTH_CONNECTED' : 'MICROPHONE_CONNECTED';
          }
        });
      },
      onLatencyUpdate: (latencyMs) => {
        updateTelemetry({ latencyMs });
      },
      onHeartbeat: (timestamp) => {
        updateTelemetry({ lastHeartbeatTs: timestamp });
      },
      onError: (error) => {
        addLog('error', 'network', error);
      },
      onClose: (reason) => {
        addLog('info', 'network', `Node connection closed: ${reason}`);
      },
      onAnnotatedFrame: handleAnnotatedFrame,
      onDetectionEvent: handleDetectionEvent,
      onCapabilities: (capabilities) => {
        setPiCapabilities(capabilities);
        if (capabilities.speaker_output_available) {
          setVolunteerMode((current) => current === 'microphone' || current === 'both' ? 'camera' : current);
        }
      },
      onSourceRejected: (source, reason) => {
        addLog('error', 'media', `Node rejected ${source} input: ${reason}`);
        if (source === 'microphone') {
          // Audio is an optional capability. A microphone rejection must not
          // terminate an already-authorized camera stream.
          const remainingStream = mediaManagerRef.current.stopAudioCapture();
          setLocalStream(remainingStream);
          if (videoRef.current) videoRef.current.srcObject = remainingStream;
          if (audioIntervalRef.current !== null) clearInterval(audioIntervalRef.current);
          audioIntervalRef.current = null;
          updateTelemetry({ microphoneActive: false, audioPeakLevel: 0, audioRmsLevel: 0 });
          setVolunteerMode('camera');
          return;
        }
        mediaManagerRef.current.stopCapture();
        setLocalStream(null);
        if (videoRef.current) videoRef.current.srcObject = null;
        if (frameIntervalRef.current !== null) clearInterval(frameIntervalRef.current);
        if (audioIntervalRef.current !== null) clearInterval(audioIntervalRef.current);
        if (durationTimerRef.current !== null) clearInterval(durationTimerRef.current);
        frameIntervalRef.current = null;
        audioIntervalRef.current = null;
        durationTimerRef.current = null;
        updateTelemetry({ cameraActive: false, microphoneActive: false, audioPeakLevel: 0, audioRmsLevel: 0 });
        setConnectionState('BACKEND_UNAVAILABLE');
        client.disconnect();
      },
    });

    piClientRef.current = client;

    return () => {
      client.disconnect();
    };
  }, [config, addLog, updateTelemetry, handleAnnotatedFrame, handleDetectionEvent]);

  // Update config wrapper
  const updateConfig = useCallback((patch: Partial<PiNodeConfig>) => {
    setConfig((prev) => {
      const updated = { ...prev, ...patch };
      if (piClientRef.current) {
        piClientRef.current.updateConfig(updated);
      }
      return updated;
    });
  }, []);

  // Device enumeration
  const refreshDevices = useCallback(async () => {
    const { cameras, microphones } = await mediaManagerRef.current.getAvailableDevices();
    setDevices((prev) => ({
      cameras,
      microphones,
      selectedCameraId: prev.selectedCameraId || (cameras[0]?.deviceId ?? ''),
      selectedMicrophoneId: prev.selectedMicrophoneId || (microphones[0]?.deviceId ?? ''),
    }));
  }, []);

  useEffect(() => {
    refreshDevices();
    navigator.mediaDevices?.addEventListener?.('devicechange', refreshDevices);
    return () => {
      navigator.mediaDevices?.removeEventListener?.('devicechange', refreshDevices);
    };
  }, [refreshDevices]);

  // Login handler
  const login = useCallback(
    async (operatorId: string, totpCode: string) => {
      setConnectionState('AUTHENTICATING');
      addLog('info', 'auth', `Authenticating operator [${operatorId}] via TOTP...`);

      const result = await authenticateOperator(operatorId, totpCode, config);
      if (result.success && result.session) {
        setSession(result.session);
        setConnectionState('NOT_CONNECTED');
        addLog('success', 'auth', `Operator [${operatorId}] authenticated. Single-use session token issued.`);
        return { success: true };
      } else {
        setConnectionState('NOT_CONNECTED');
        const err = result.errorMessage || 'Authentication failed.';
        addLog('error', 'auth', `Authentication error: ${err}`);
        return { success: false, error: err };
      }
    },
    [config, addLog]
  );

  // Logout handler
  const logout = useCallback(() => {
    // Stop any active volunteering session
    if (connectionState !== 'NOT_CONNECTED') {
      stopVolunteering();
    }
    clearSession();
    setSession(null);
    setConnectionState('NOT_CONNECTED');
    addLog('info', 'auth', 'Operator logged out. In-memory session credentials revoked.');
  }, [connectionState, addLog]);

  // Check session validity periodically
  useEffect(() => {
    const timer = setInterval(() => {
      if (session && !isSessionValid(session)) {
        addLog('warn', 'auth', 'Operator session expired. Terminating volunteer pipeline.');
        stopVolunteering();
        clearSession();
        setSession(null);
        setConnectionState('SESSION_EXPIRED');
      }
    }, 5000);
    return () => clearInterval(timer);
  }, [session, addLog]);

  // Start volunteering workflow
  const startVolunteering = useCallback(async () => {
    // 1. Session check
    if (!session || !isSessionValid(session)) {
      setConnectionState('SESSION_EXPIRED');
      addLog('error', 'auth', 'Cannot start: Active session required.');
      return;
    }

    // 2. Confirm node capabilities BEFORE requesting any browser media permission.
    let effectiveMode = volunteerMode;
    if (!config.mockMode) {
      if (!piClientRef.current) {
        addLog('error', 'network', 'Node client is unavailable; no media permission was requested.');
        return;
      }
      const health = await piClientRef.current.checkHealth();
      if (!health.online) {
        setConnectionState('BACKEND_UNAVAILABLE');
        addLog('error', 'network', `Node capability check failed: ${health.error || 'node offline'}. No media permission was requested.`);
        return;
      }
      const capabilities = health.capabilities;
      if (capabilities) setPiCapabilities(capabilities);
      const microphoneAllowed = capabilities?.browser_microphone_allowed === true
        && capabilities?.speaker_output_available !== true;
      if ((effectiveMode === 'microphone' || effectiveMode === 'both') && !microphoneAllowed) {
        const reason = capabilities?.speaker_output_available
          ? 'Node audio output is owned by the active node.'
          : 'The node has not advertised a working microphone ingestion path.';
        if (effectiveMode === 'both') {
          effectiveMode = 'camera';
          setVolunteerMode('camera');
          addLog('warn', 'media', `${reason} Browser microphone donation is disabled; continuing with camera only.`);
        } else {
          setConnectionState('BACKEND_UNAVAILABLE');
          addLog('error', 'media', `${reason} Browser microphone capture is disabled.`);
          return;
        }
      }
    }

    const wantVideo = effectiveMode === 'camera' || effectiveMode === 'both';
    const wantAudio = effectiveMode === 'microphone' || effectiveMode === 'both';

    setConnectionState('CONNECTING');
    addLog('info', 'system', `Initiating volunteer session: Mode = ${effectiveMode.toUpperCase()}`);

    // 3. Request Browser Permissions and Media Stream
    let stream: MediaStream;
    try {
      stream = await mediaManagerRef.current.startCapture({
        video: wantVideo,
        audio: wantAudio,
        cameraId: devices.selectedCameraId,
        microphoneId: devices.selectedMicrophoneId,
      });

      setLocalStream(stream);
      if (videoRef.current && wantVideo) {
        videoRef.current.srcObject = stream;
      }

      setPermissionState({
        camera: wantVideo ? 'granted' : permissionState.camera,
        microphone: wantAudio ? 'granted' : permissionState.microphone,
      });

      addLog('success', 'media', 'Browser hardware permissions granted. Capturing local media stream.');
      refreshDevices();
    } catch (err: unknown) {
      const errName = (err as Error).name || '';
      console.error('[VolunteerContext] Media capture error:', err);

      if (errName === 'NotAllowedError' || errName === 'PermissionDeniedError') {
        setConnectionState('PERMISSION_DENIED');
        setPermissionState({
          camera: wantVideo ? 'denied' : permissionState.camera,
          microphone: wantAudio ? 'denied' : permissionState.microphone,
        });
        addLog('error', 'media', 'Device access denied by user. Please grant camera/microphone permission.');
      } else {
        setConnectionState('NOT_CONNECTED');
        addLog('error', 'media', `Hardware access failed: ${(err as Error).message}`);
      }
      return;
    }

    // 3. Initiate node connection
    if (!piClientRef.current) return;

    framesSentCountRef.current = 0;
    bytesSentCountRef.current = 0;
    fpsWindowRef.current = { count: 0, start: Date.now() };

    updateTelemetry({
      durationSeconds: 0,
      framesSent: 0,
      fps: 0,
      bytesSent: 0,
      audioPeakLevel: 0,
      audioRmsLevel: 0,
    });

    const connected = await piClientRef.current.connectAndVolunteer(effectiveMode, session.token, session.pairingExpiresAt);

    if (!connected) {
      mediaManagerRef.current.stopCapture();
      setLocalStream(null);
      return;
    }

    // 4. Start Session Duration Clock
    const sessionStartTime = Date.now();
    if (durationTimerRef.current !== null) clearInterval(durationTimerRef.current);
    durationTimerRef.current = window.setInterval(() => {
      const elapsed = Math.floor((Date.now() - sessionStartTime) / 1000);
      updateTelemetry({ durationSeconds: elapsed });
    }, 1000);

    // 5. Start Frame Capture Loop (if camera enabled)
    if (wantVideo) {
      // 10 FPS = 100ms interval (balances responsiveness and edge-node inference load)
      const FPS_INTERVAL = 100;
      frameIntervalRef.current = window.setInterval(() => {
        if (!videoRef.current) return;
        const frameData = mediaManagerRef.current.captureFrame(videoRef.current, 0.65);
        if (frameData && piClientRef.current) {
          const payload = {
            type: 'frame' as const,
            frame_id: frameData.frameId,
            ts_ms: frameData.tsMs,
            jpeg_b64: frameData.jpegB64,
          };

          const sent = piClientRef.current.sendFrame(payload);
          if (sent) {
            framesSentCountRef.current += 1;
            const approxBytes = frameData.jpegB64.length;
            bytesSentCountRef.current += approxBytes;

            // Calculate rolling FPS
            fpsWindowRef.current.count += 1;
            const now = Date.now();
            const windowDuration = (now - fpsWindowRef.current.start) / 1000;
            let currentFps = telemetry.fps;
            if (windowDuration >= 1.0) {
              currentFps = Math.round(fpsWindowRef.current.count / windowDuration);
              fpsWindowRef.current = { count: 0, start: now };
            }

            updateTelemetry({
              framesSent: framesSentCountRef.current,
              bytesSent: bytesSentCountRef.current,
              fps: currentFps,
            });
          }
        }
      }, FPS_INTERVAL);
    }

    // 6. Start Audio Meter Loop (if microphone enabled)
    if (wantAudio) {
      audioIntervalRef.current = window.setInterval(() => {
        const levels = mediaManagerRef.current.getAudioLevels();
        updateTelemetry({
          audioRmsLevel: levels.rms,
          audioPeakLevel: levels.peak,
        });
      }, 100);
    }
  }, [session, volunteerMode, devices, permissionState, config, updateTelemetry, addLog, refreshDevices]);

  // Stop volunteering workflow
  const stopVolunteering = useCallback(() => {
    // 1. Clear intervals
    if (frameIntervalRef.current !== null) {
      clearInterval(frameIntervalRef.current);
      frameIntervalRef.current = null;
    }
    if (audioIntervalRef.current !== null) {
      clearInterval(audioIntervalRef.current);
      audioIntervalRef.current = null;
    }
    if (durationTimerRef.current !== null) {
      clearInterval(durationTimerRef.current);
      durationTimerRef.current = null;
    }

    // 2. Stop all hardware media tracks immediately
    mediaManagerRef.current.stopCapture();
    setLocalStream(null);
    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }

    // 3. Disconnect from node
    if (piClientRef.current) {
      piClientRef.current.disconnect();
    }

    setConnectionState('STOPPED_BY_USER');
    updateTelemetry({
      cameraActive: false,
      microphoneActive: false,
      fps: 0,
      audioPeakLevel: 0,
      audioRmsLevel: 0,
    });

    addLog('info', 'system', 'Volunteer session terminated by user. Media tracks stopped.');
  }, [addLog, updateTelemetry]);

  useEffect(() => {
    if (piCapabilities?.speaker_output_available && telemetry.microphoneActive) {
      // A node-owned speaker/microphone conflict must not tear down an otherwise
      // healthy donated camera. Release only the browser microphone and retain
      // the authenticated WebSocket plus video capture loop.
      const remainingStream = mediaManagerRef.current.stopAudioCapture();
      setLocalStream(remainingStream);
      if (videoRef.current) videoRef.current.srcObject = remainingStream;
      if (audioIntervalRef.current !== null) {
        clearInterval(audioIntervalRef.current);
        audioIntervalRef.current = null;
      }
      updateTelemetry({ microphoneActive: false, audioPeakLevel: 0, audioRmsLevel: 0 });
      setVolunteerMode('camera');
      addLog('warn', 'media', 'Node audio output owns the audio path. Released the donated microphone; camera donation remains connected.');
    }
  }, [piCapabilities, telemetry.microphoneActive, updateTelemetry, addLog]);

  // Handle browser tab close, unload, and network status changes
  useEffect(() => {
    const handleBeforeUnload = () => {
      stopVolunteering();
    };

    const handleOffline = () => {
      addLog('warn', 'network', 'Host device lost network connectivity.');
      setConnectionState('CONNECTION_LOST');
    };

    const handleOnline = () => {
      addLog('info', 'network', 'Host device network restored.');
    };

    window.addEventListener('beforeunload', handleBeforeUnload);
    window.addEventListener('offline', handleOffline);
    window.addEventListener('online', handleOnline);

    return () => {
      window.removeEventListener('beforeunload', handleBeforeUnload);
      window.removeEventListener('offline', handleOffline);
      window.removeEventListener('online', handleOnline);
    };
  }, [stopVolunteering, addLog]);

  const selectCamera = useCallback((deviceId: string) => {
    setDevices((prev) => ({ ...prev, selectedCameraId: deviceId }));
  }, []);

  const selectMicrophone = useCallback((deviceId: string) => {
    setDevices((prev) => ({ ...prev, selectedMicrophoneId: deviceId }));
  }, []);

  return (
    <VolunteerContext.Provider
      value={{
        connectionState,
        volunteerMode,
        setVolunteerMode,
        config,
        updateConfig,
        session,
        login,
        logout,
        devices,
        permissionState,
        selectCamera,
        selectMicrophone,
        refreshDevices,
        localStream,
        videoRef,
        startVolunteering,
        stopVolunteering,
        telemetry,
        logs,
        clearLogs,
        detectionEvidence,
        piCapabilities,
      }}
    >
      {children}
    </VolunteerContext.Provider>
  );
};

export const useVolunteer = (): VolunteerContextValue => {
  const context = useContext(VolunteerContext);
  if (!context) {
    throw new Error('useVolunteer must be used within a VolunteerProvider');
  }
  return context;
};
