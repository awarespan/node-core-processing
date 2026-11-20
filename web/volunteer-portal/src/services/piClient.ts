/**
 * AWARESPAN Volunteer Portal — AWARESPAN Node Integration Client
 *
 * Implements communication with the AWARESPAN edge node runtime:
 * - Production Mode: Connects directly to verified AWARESPAN node endpoints
 *   (ws://<host>:8766/ingest and ws://<host>:8766/health).
 *   Strictly adheres to node_runtime protocol: NEVER fabricates responses.
 * - Dev/Mock Mode: High-fidelity simulator for end-to-end testing without hardware.
 */

import { AnnotatedFramePayload, FramePayload, PiDetectionEvent, PiNodeCapabilities, PiNodeConfig, VolunteerMode } from '../types';

export interface PiClientCallbacks {
  onStatusChange: (status: 'connecting' | 'connected' | 'reconnecting' | 'disconnected' | 'rejected') => void;
  onSourceAcknowledged: (source: 'camera' | 'microphone') => void;
  onLatencyUpdate: (latencyMs: number) => void;
  onHeartbeat: (timestamp: number) => void;
  onError: (error: string) => void;
  onClose: (reason: string) => void;
  onAnnotatedFrame?: (frame: AnnotatedFramePayload) => void;
  onDetectionEvent?: (event: PiDetectionEvent) => void;
  onCapabilities?: (capabilities: PiNodeCapabilities) => void;
  onSourceRejected?: (source: 'camera' | 'microphone', reason: string) => void;
}

/**
 * Encode a JPEG frame using node_runtime.volunteer_gateway.transport.protocol:
 * AWSP | type | source length | source | sequence | timestamp | payload length | JPEG bytes.
 */
export const encodeVolunteerFrame = (payload: FramePayload): ArrayBuffer => {
  const source = new TextEncoder().encode('portal');
  const binary = atob(payload.jpeg_b64);
  const jpeg = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) jpeg[i] = binary.charCodeAt(i);

  const headerLength = 6 + source.length + 16;
  const buffer = new ArrayBuffer(headerLength + jpeg.length);
  const bytes = new Uint8Array(buffer);
  bytes.set([0x41, 0x57, 0x53, 0x50, 0x01, source.length], 0); // AWSP + FRAME_JPEG
  bytes.set(source, 6);
  const view = new DataView(buffer);
  let offset = 6 + source.length;
  view.setUint32(offset, payload.frame_id >>> 0, false);
  offset += 4;
  view.setBigUint64(offset, BigInt(Math.max(0, Math.trunc(payload.ts_ms))), false);
  offset += 8;
  view.setUint32(offset, jpeg.length, false);
  offset += 4;
  bytes.set(jpeg, offset);
  return buffer;
};

export class PiConnectionClient {
  private config: PiNodeConfig;
  private callbacks: PiClientCallbacks;
  private ws: WebSocket | null = null;
  private dashboardWs: WebSocket | null = null;
  private dashboardReconnectTimer: number | null = null;
  private isConnecting: boolean = false;
  private isConnected: boolean = false;
  private isVolunteering: boolean = false;
  private activeMode: VolunteerMode = 'camera';
  private pingInterval: number | null = null;
  private mockHeartbeatInterval: number | null = null;
  private reconnectTimer: number | null = null;
  private reconnectAttempts: number = 0;
  private maxReconnectAttempts: number = 5;
  private manualStop: boolean = false;
  private isRejected: boolean = false;
  private lastPingSentTs: number = 0;

  constructor(config: PiNodeConfig, callbacks: PiClientCallbacks) {
    this.config = config;
    this.callbacks = callbacks;
  }

  public updateConfig(config: PiNodeConfig): void {
    this.config = config;
  }

  /**
   * Check if AWARESPAN node is online by probing /health.
   */
  public async checkHealth(): Promise<{ online: boolean; nodeId?: string; capabilities?: PiNodeCapabilities; error?: string }> {
    if (this.config.mockMode) {
      return { online: true, nodeId: this.config.nodeId };
    }

    return new Promise((resolve) => {
      try {
        const protocol = this.config.useSsl ? 'wss' : 'ws';
        const url = `${protocol}://${this.config.piHost}:${this.config.piPort}/health`;
        const socket = new WebSocket(url);
        let resolved = false;

        const timer = setTimeout(() => {
          if (!resolved) {
            resolved = true;
            try { socket.close(); } catch (_) { /* ignore */ }
            resolve({ online: false, error: 'Health probe timed out (2500ms)' });
          }
        }, 2500);

        socket.onmessage = (event) => {
          if (!resolved) {
            resolved = true;
            clearTimeout(timer);
            try {
              const data = JSON.parse(event.data);
              const capabilities = data.capabilities as PiNodeCapabilities | undefined;
              if (capabilities) this.callbacks.onCapabilities?.(capabilities);
              resolve({ online: data.status === 'ok', nodeId: data.node, capabilities });
            } catch {
              resolve({ online: true, nodeId: this.config.nodeId });
            }
          }
        };

        socket.onerror = () => {
          if (!resolved) {
            resolved = true;
            clearTimeout(timer);
            resolve({ online: false, error: `Connection refused at ${url}` });
          }
        };

        socket.onclose = () => {
          if (!resolved) {
            resolved = true;
            clearTimeout(timer);
            resolve({ online: false, error: 'Health socket closed without response' });
          }
        };
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : String(err);
        resolve({ online: false, error: msg });
      }
    });
  }

  /**
   * Connect and initiate volunteer media session.
   */
  public async connectAndVolunteer(
    mode: VolunteerMode,
    sessionToken: string,
    pairingExpiresAt?: number,
  ): Promise<boolean> {
    this.manualStop = false;
    this.isRejected = false;
    this.activeMode = mode;
    this.reconnectAttempts = 0;

    if (!this.config.mockMode && pairingExpiresAt !== undefined && Date.now() >= pairingExpiresAt) {
      this.callbacks.onError('The one-use pairing token expired. Authenticate again before starting a stream.');
      this.callbacks.onStatusChange('disconnected');
      return false;
    }

    return this.initiateSession(sessionToken);
  }

  private async initiateSession(sessionToken: string): Promise<boolean> {
    this.isConnecting = true;
    this.callbacks.onStatusChange('connecting');

    if (this.config.mockMode) {
      return this.initiateMockSession(sessionToken);
    }

    return new Promise((resolve) => {
      let settled = false;
      let connectionTimeout: number | null = null;
      const finish = (value: boolean) => {
        if (settled) return;
        settled = true;
        if (connectionTimeout !== null) clearTimeout(connectionTimeout);
        resolve(value);
      };

      try {
        const protocol = this.config.useSsl ? 'wss' : 'ws';
        const url = `${protocol}://${this.config.piHost}:${this.config.gatewayPort}/ws/volunteer`;
        this.ws = new WebSocket(url);

        connectionTimeout = window.setTimeout(() => {
          if (this.isConnecting) {
            this.isConnecting = false;
            this.callbacks.onError(`Volunteer gateway at ${url} did not authorise the one-use pairing token within 8 seconds.`);
            this.callbacks.onStatusChange('disconnected');
            try { this.ws?.close(); } catch { /* ignore */ }
            finish(false);
          }
        }, 8000);

        this.ws.onopen = () => {
          // The bearer token is sent inside the encrypted WebSocket, not in the URL.
          try {
            this.ws?.send(JSON.stringify({ type: 'pairing_token', token: sessionToken }));
          } catch (error) {
            const message = error instanceof Error ? error.message : String(error);
            this.callbacks.onError(`Could not send pairing token: ${message}`);
            this.callbacks.onStatusChange('disconnected');
            finish(false);
            try { this.ws?.close(); } catch { /* ignore */ }
          }
        };

        this.ws.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            if (data.type === 'authorized') {
              this.isConnecting = false;
              this.isConnected = true;
              this.isVolunteering = true;
              this.callbacks.onStatusChange('connected');
              // Pairing capabilities are permissions, not proof that each source
              // is active. A node may grant both while the portal intentionally
              // falls back to camera-only (for example, when node audio owns output).
              // Acknowledge only the media tracks this browser actually opened.
              if (this.activeMode === 'camera' || this.activeMode === 'both') {
                this.callbacks.onSourceAcknowledged('camera');
              }
              if (this.activeMode === 'microphone' || this.activeMode === 'both') {
                this.callbacks.onSourceAcknowledged('microphone');
              }
              this.connectDashboardFeed();
              this.startHeartbeatMonitor();
              this.callbacks.onHeartbeat(Date.now());
              finish(true);
              return;
            }
            if (data.type === 'error' || data.type === 'reject') {
              this.isRejected = true;
              const message = String(data.message || 'Volunteer gateway rejected the session.');
              this.callbacks.onError(message);
              this.callbacks.onStatusChange('rejected');
              this.isConnecting = false;
              finish(false);
              try { this.ws?.close(); } catch { /* ignore */ }
              return;
            }
            if (data.type === 'pong' && this.lastPingSentTs > 0) {
              this.callbacks.onLatencyUpdate(Date.now() - this.lastPingSentTs);
              this.callbacks.onHeartbeat(Date.now());
            }
            if (data.type === 'capabilities') {
              this.callbacks.onCapabilities?.(data as PiNodeCapabilities);
            }
            if (data.type === 'source_rejected' && (data.source === 'camera' || data.source === 'microphone')) {
              this.callbacks.onSourceRejected?.(data.source, String(data.reason || 'Source rejected by node.'));
            }
          } catch {
            // Ignore non-JSON application messages; binary frames are server-to-client only here.
          }
        };

        this.ws.onerror = () => {
          if (this.isConnecting) {
            this.isConnecting = false;
            this.callbacks.onError(`Failed to connect to volunteer gateway at ${url}`);
            this.callbacks.onStatusChange('disconnected');
            finish(false);
          }
        };

        this.ws.onclose = (event) => {
          const wasConnected = this.isConnected;
          this.isConnected = false;
          this.isVolunteering = false;
          this.isConnecting = false;
          this.stopHeartbeatMonitor();
          this.closeDashboardFeed();
          if (!settled) {
            this.callbacks.onStatusChange(this.isRejected ? 'rejected' : 'disconnected');
            finish(false);
          } else if (this.isRejected) {
            this.callbacks.onClose(event.reason || 'Session rejected by gateway');
          } else if (!this.manualStop && wasConnected) {
            this.handleUnexpectedDisconnect(event.reason || 'Volunteer gateway connection closed');
          } else {
            this.callbacks.onStatusChange('disconnected');
            this.callbacks.onClose(event.reason || 'Session closed');
          }
        };
      } catch (err: unknown) {
        this.isConnecting = false;
        const msg = err instanceof Error ? err.message : String(err);
        this.callbacks.onError(`WebSocket instantiation error: ${msg}`);
        this.callbacks.onStatusChange('disconnected');
        finish(false);
      }
    });
  }

  /**
   * Subscribe to the node's read-only dashboard stream. Annotated JPEG frames
   * already contain boxes drawn by the node inference pipeline.
   */
  private connectDashboardFeed(): void {
    if (this.config.mockMode || !this.isConnected || this.manualStop) return;
    if (!this.callbacks.onAnnotatedFrame && !this.callbacks.onDetectionEvent) return;
    if (this.dashboardWs && (this.dashboardWs.readyState === WebSocket.OPEN || this.dashboardWs.readyState === WebSocket.CONNECTING)) return;
    const protocol = this.config.useSsl ? 'wss' : 'ws';
    const url = `${protocol}://${this.config.piHost}:${this.config.piPort}/`;
    try {
      const socket = new WebSocket(url);
      this.dashboardWs = socket;
      socket.onmessage = (message) => {
        try {
          const data = JSON.parse(message.data);
          if (data.type === 'capabilities') {
            this.callbacks.onCapabilities?.(data as PiNodeCapabilities);
          } else if (data.type === 'frame' && typeof data.annotated_b64 === 'string') {
            this.callbacks.onAnnotatedFrame?.(data as AnnotatedFramePayload);
          } else if (data.type === 'log' && data.event?.event_id) {
            this.callbacks.onDetectionEvent?.(data.event as PiDetectionEvent);
          }
        } catch { /* Ignore unrelated dashboard messages. */ }
      };
      socket.onclose = () => {
        if (this.dashboardWs === socket) this.dashboardWs = null;
        if (this.isConnected && !this.manualStop) {
          this.dashboardReconnectTimer = window.setTimeout(() => this.connectDashboardFeed(), 2000);
        }
      };
      socket.onerror = () => { /* Dashboard reconnects independently of media ingest. */ };
    } catch {
      this.dashboardWs = null;
    }
  }

  private closeDashboardFeed(): void {
    if (this.dashboardReconnectTimer !== null) {
      clearTimeout(this.dashboardReconnectTimer);
      this.dashboardReconnectTimer = null;
    }
    if (this.dashboardWs) {
      const socket = this.dashboardWs;
      this.dashboardWs = null;
      socket.onclose = null;
      try { socket.close(); } catch { /* already closed */ }
    }
  }

  /**
   * Mock implementation for development & testing without live hardware.
   */
  private async initiateMockSession(_sessionToken: string): Promise<boolean> {
    return new Promise((resolve) => {
      setTimeout(() => {
        if (this.manualStop) {
          resolve(false);
          return;
        }

        this.isConnecting = false;
        this.isConnected = true;
        this.isVolunteering = true;
        this.callbacks.onStatusChange('connected');

        // Simulate node individual source acknowledgements
        if (this.activeMode === 'camera' || this.activeMode === 'both') {
          setTimeout(() => {
            this.callbacks.onSourceAcknowledged('camera');
          }, 150);
        }

        if (this.activeMode === 'microphone' || this.activeMode === 'both') {
          setTimeout(() => {
            this.callbacks.onSourceAcknowledged('microphone');
          }, 300);
        }

        // Start mock heartbeat and latency updates
        this.startMockHeartbeat();
        resolve(true);
      }, 400);
    });
  }

  private startMockHeartbeat(): void {
    this.stopHeartbeatMonitor();
    this.mockHeartbeatInterval = window.setInterval(() => {
      if (this.isConnected) {
        const simulatedRtt = Math.floor(18 + Math.random() * 20); // 18-38 ms
        this.callbacks.onLatencyUpdate(simulatedRtt);
        this.callbacks.onHeartbeat(Date.now());
      }
    }, 4000);
  }

  private startHeartbeatMonitor(): void {
    this.stopHeartbeatMonitor();
    this.pingInterval = window.setInterval(() => {
      if (this.ws && this.ws.readyState === WebSocket.OPEN) {
        this.lastPingSentTs = Date.now();
        try {
          this.ws.send(JSON.stringify({ type: 'ping', ts_ms: this.lastPingSentTs }));
        } catch {
          // ignore
        }
      }
    }, 5000);
  }

  private stopHeartbeatMonitor(): void {
    if (this.pingInterval !== null) {
      clearInterval(this.pingInterval);
      this.pingInterval = null;
    }
    if (this.mockHeartbeatInterval !== null) {
      clearInterval(this.mockHeartbeatInterval);
      this.mockHeartbeatInterval = null;
    }
  }

  /**
   * Handle unexpected network drops with exponential backoff.
   */
  private handleUnexpectedDisconnect(reason: string): void {
    if (this.manualStop) return;

    if (!this.config.mockMode) {
      this.callbacks.onStatusChange('disconnected');
      this.callbacks.onError(`Volunteer connection lost (${reason}). Pairing tokens are single-use; authenticate again to reconnect.`);
      this.callbacks.onClose(reason);
      return;
    }

    if (this.reconnectAttempts < this.maxReconnectAttempts) {
      this.reconnectAttempts += 1;
      const delayMs = Math.min(1000 * Math.pow(2, this.reconnectAttempts - 1), 8000);
      this.callbacks.onStatusChange('reconnecting');
      this.callbacks.onError(`Connection lost (${reason}). Retrying in ${delayMs / 1000}s (attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts})...`);

      this.reconnectTimer = window.setTimeout(() => {
        this.initiateSession('reconnect-token');
      }, delayMs);
    } else {
      this.callbacks.onStatusChange('disconnected');
      this.callbacks.onError(`Connection failed after ${this.maxReconnectAttempts} reconnect attempts. AWARESPAN node unreachable.`);
      this.disconnect();
    }
  }

  /**
   * Transmit captured video frame through the authenticated volunteer gateway.
   * Uses the AWSP binary packet framing expected by VolunteerGatewayServer.
   */
  public sendFrame(payload: FramePayload): boolean {
    if (!this.isConnected) return false;

    if (this.config.mockMode) {
      // In mock mode, simply simulate transmission latency
      return true;
    }

    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      try {
        this.ws.send(encodeVolunteerFrame(payload));
        return true;
      } catch (e) {
        console.warn('[PiClient] Frame send error:', e);
        return false;
      }
    }

    return false;
  }

  /**
   * Transmit audio chunk to AWARESPAN node (when audio ingestion endpoint is available).
   */
  public sendAudioChunk(_chunk: ArrayBuffer | Blob): boolean {
    if (!this.isConnected) return false;

    if (this.config.mockMode) {
      return true;
    }

    // Browser MediaRecorder Blob/WebM chunks aren't pcm_s16le. The edge runtime
    // currently advertises browser microphone ingestion as unavailable, so do not
    // send an incompatible or misleading audio payload.
    this.callbacks.onSourceRejected?.('microphone', 'Browser microphone PCM ingestion is not enabled by the deployed edge runtime.');
    return false;
  }

  /**
   * Gracefully stop volunteering and close connection.
   */
  public disconnect(suppressStatusUpdate: boolean = false): void {
    this.manualStop = true;
    this.isVolunteering = false;
    this.isConnected = false;
    this.isConnecting = false;

    if (this.reconnectTimer !== null) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }

    this.stopHeartbeatMonitor();
    this.closeDashboardFeed();

    if (this.ws) {
      try {
        if (this.ws.readyState === WebSocket.OPEN) {
          this.ws.send(JSON.stringify({ type: 'disconnect', ts_ms: Date.now() }));
        }
        this.ws.close();
      } catch (e) {
        console.warn('[PiClient] Disconnect error:', e);
      }
      this.ws = null;
    }

    if (!suppressStatusUpdate) {
      this.callbacks.onStatusChange('disconnected');
    }
  }

  public getIsConnected(): boolean {
    return this.isConnected;
  }

  public getIsVolunteering(): boolean {
    return this.isVolunteering;
  }
}
