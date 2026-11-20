/**
 * AWARESPAN Volunteer Portal — Type Definitions
 */

export type ConnectionState =
  | 'NOT_CONNECTED'
  | 'AUTHENTICATING'
  | 'CONNECTING'
  | 'AWAITING_PI_ACK'
  | 'CAMERA_CONNECTED'
  | 'MICROPHONE_CONNECTED'
  | 'BOTH_CONNECTED'
  | 'RECONNECTING'
  | 'CONNECTION_LOST'
  | 'STOPPED_BY_USER'
  | 'SESSION_EXPIRED'
  | 'PERMISSION_DENIED'
  | 'BACKEND_UNAVAILABLE';

export type VolunteerMode = 'camera' | 'microphone' | 'both';

export interface AuthSession {
  token: string;
  operatorId: string;
  issuedAt: number;
  expiresAt: number;
  pairingExpiresAt?: number;
  isAuthenticated: boolean;
  nodeId: string;
}

export interface AvailableDevices {
  cameras: MediaDeviceInfo[];
  microphones: MediaDeviceInfo[];
  selectedCameraId: string;
  selectedMicrophoneId: string;
}

export interface MediaPermissionState {
  camera: 'prompt' | 'granted' | 'denied' | 'unavailable';
  microphone: 'prompt' | 'granted' | 'denied' | 'unavailable';
}

export interface SessionTelemetry {
  durationSeconds: number;
  framesSent: number;
  fps: number;
  latencyMs: number;
  bytesSent: number;
  audioPeakLevel: number; // 0-100
  audioRmsLevel: number;  // 0-100
  lastHeartbeatTs: number | null;
  reconnectAttempts: number;
  cameraActive: boolean;
  microphoneActive: boolean;
  piNodeId: string;
}

export type LogLevel = 'info' | 'warn' | 'error' | 'success';
export type LogCategory = 'system' | 'auth' | 'network' | 'media' | 'ack';

export interface PortalLog {
  id: string;
  timestamp: string;
  level: LogLevel;
  category: LogCategory;
  message: string;
}

export interface FramePayload {
  type: 'frame';
  frame_id: number;
  ts_ms: number;
  jpeg_b64: string;
}

export interface PiNodeCapabilities {
  speaker_output_available: boolean;
  speaker_output_device?: string;
  speaker_output_cards?: string[];
  speaker_output_reason?: string;
  browser_microphone_allowed: boolean;
  audio_owner: 'raspberry_pi' | 'none';
}

export interface PiNodeConfig {
  piHost: string;
  piPort: number;
  gatewayPort: number;
  useSsl: boolean;
  nodeId: string;
  mockMode: boolean;
}


export interface PiDetectionEvent {
  event_id: string;
  ts_ms: number;
  tier: string;
  labels: string[];
  max_confidence: number;
  action: string;
  latency_ms?: number;
  frame_id: number;
  model?: string;
  source_id?: string;
}

export interface AnnotatedFramePayload {
  type: 'frame';
  frame_id: number;
  ts_ms?: number;
  source_id?: string;
  annotated_b64: string;
  latency_ms?: number;
  fps?: number;
}

export interface DetectionEvidence {
  event: PiDetectionEvent;
  imageUrl: string;
  capturedAt: number;
}
