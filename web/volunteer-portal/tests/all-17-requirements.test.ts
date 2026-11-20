import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { authenticateOperator, clearSession, isSessionValid } from '../src/services/auth';
import { MediaCaptureManager } from '../src/services/media';
import { PiConnectionClient } from '../src/services/piClient';
import { PiNodeConfig } from '../src/types';

describe('AWARESPAN Volunteer Portal — 17 Mandatory Test Scenarios', () => {
  const baseConfig: PiNodeConfig = {
    piHost: '192.168.1.50',
    piPort: 8766,
    gatewayPort: 8443,
    useSsl: false,
    nodeId: 'sip-pi-001',
    mockMode: true,
  };

  beforeEach(() => {
    vi.clearAllMocks();
    clearSession();
  });

  afterEach(() => {
    clearSession();
  });

  // ─────────────────────────────────────────────────────────────
  // 1. Successful authentication
  // ─────────────────────────────────────────────────────────────
  it('Scenario 1: Successful authentication issues short-lived session token', async () => {
    const result = await authenticateOperator('operator-1', '123456', baseConfig);
    expect(result.success).toBe(true);
    expect(result.session).toBeDefined();
    expect(result.session?.isAuthenticated).toBe(true);
    expect(result.session?.operatorId).toBe('operator-1');
    expect(result.session?.token).toContain('mock-vol-tok-');
    expect(isSessionValid(result.session!)).toBe(true);
  });

  // ─────────────────────────────────────────────────────────────
  // 2. Failed authentication
  // ─────────────────────────────────────────────────────────────
  it('Scenario 2: Failed authentication rejects invalid credentials without creating session', async () => {
    // Test invalid format
    const resInvalidFormat = await authenticateOperator('operator-1', '12', baseConfig);
    expect(resInvalidFormat.success).toBe(false);
    expect(resInvalidFormat.errorMessage).toContain('must be exactly 6 digits');

    // Test rejection code
    const resRejected = await authenticateOperator('operator-1', '000000', baseConfig);
    expect(resRejected.success).toBe(false);
    expect(resRejected.errorMessage).toContain('rejected');
  });

  // ─────────────────────────────────────────────────────────────
  // 3. Camera permission granted
  // ─────────────────────────────────────────────────────────────
  it('Scenario 3: Camera permission granted initializes video stream and canvas', async () => {
    const media = new MediaCaptureManager();
    const stream = await media.startCapture({ video: true, audio: false });
    expect(stream).toBeDefined();
    expect(media.hasVideo()).toBe(true);
    expect(media.hasAudio()).toBe(false);
    expect(stream.getVideoTracks().length).toBe(1);
    media.stopCapture();
  });

  // ─────────────────────────────────────────────────────────────
  // 4. Camera permission denied
  // ─────────────────────────────────────────────────────────────
  it('Scenario 4: Camera permission denied throws NotAllowedError and stops state', async () => {
    const media = new MediaCaptureManager();
    const originalGetUserMedia = navigator.mediaDevices.getUserMedia;

    navigator.mediaDevices.getUserMedia = vi.fn().mockRejectedValue(
      new DOMException('Permission denied by user', 'NotAllowedError')
    );

    await expect(media.startCapture({ video: true, audio: false })).rejects.toThrow(
      'Permission denied by user'
    );
    expect(media.hasVideo()).toBe(false);

    navigator.mediaDevices.getUserMedia = originalGetUserMedia;
  });

  // ─────────────────────────────────────────────────────────────
  // 5. Microphone permission granted
  // ─────────────────────────────────────────────────────────────
  it('Scenario 5: Microphone permission granted initializes audio stream and analyser', async () => {
    const media = new MediaCaptureManager();
    const stream = await media.startCapture({ video: false, audio: true });
    expect(stream).toBeDefined();
    expect(media.hasAudio()).toBe(true);
    expect(media.hasVideo()).toBe(false);
    expect(stream.getAudioTracks().length).toBe(1);

    const levels = media.getAudioLevels();
    expect(levels).toHaveProperty('rms');
    expect(levels).toHaveProperty('peak');
    media.stopCapture();
  });

  // ─────────────────────────────────────────────────────────────
  // 6. Microphone permission denied
  // ─────────────────────────────────────────────────────────────
  it('Scenario 6: Microphone permission denied throws NotAllowedError', async () => {
    const media = new MediaCaptureManager();
    const originalGetUserMedia = navigator.mediaDevices.getUserMedia;

    navigator.mediaDevices.getUserMedia = vi.fn().mockRejectedValue(
      new DOMException('Permission denied', 'NotAllowedError')
    );

    await expect(media.startCapture({ video: false, audio: true })).rejects.toThrow();
    expect(media.hasAudio()).toBe(false);

    navigator.mediaDevices.getUserMedia = originalGetUserMedia;
  });

  // ─────────────────────────────────────────────────────────────
  // 7. Camera-only volunteering
  // ─────────────────────────────────────────────────────────────
  it('Scenario 7: Camera-only volunteering initiates session and confirms only camera ACK', async () => {
    const acks: string[] = [];
    const client = new PiConnectionClient(baseConfig, {
      onStatusChange: vi.fn(),
      onSourceAcknowledged: (src) => acks.push(src),
      onLatencyUpdate: vi.fn(),
      onHeartbeat: vi.fn(),
      onError: vi.fn(),
      onClose: vi.fn(),
    });

    const connected = await client.connectAndVolunteer('camera', 'valid-token');
    expect(connected).toBe(true);

    await new Promise((r) => setTimeout(r, 200));
    expect(acks).toContain('camera');
    expect(acks).not.toContain('microphone');
    client.disconnect();
  });

  // ─────────────────────────────────────────────────────────────
  // 8. Microphone-only volunteering
  // ─────────────────────────────────────────────────────────────
  it('Scenario 8: Microphone-only volunteering initiates session and confirms only mic ACK', async () => {
    const acks: string[] = [];
    const client = new PiConnectionClient(baseConfig, {
      onStatusChange: vi.fn(),
      onSourceAcknowledged: (src) => acks.push(src),
      onLatencyUpdate: vi.fn(),
      onHeartbeat: vi.fn(),
      onError: vi.fn(),
      onClose: vi.fn(),
    });

    const connected = await client.connectAndVolunteer('microphone', 'valid-token');
    expect(connected).toBe(true);

    await new Promise((r) => setTimeout(r, 350));
    expect(acks).toContain('microphone');
    expect(acks).not.toContain('camera');
    client.disconnect();
  });

  // ─────────────────────────────────────────────────────────────
  // 9. Combined volunteering (Camera + Microphone)
  // ─────────────────────────────────────────────────────────────
  it('Scenario 9: Combined volunteering independently acknowledges both camera and mic', async () => {
    const acks: string[] = [];
    const client = new PiConnectionClient(baseConfig, {
      onStatusChange: vi.fn(),
      onSourceAcknowledged: (src) => acks.push(src),
      onLatencyUpdate: vi.fn(),
      onHeartbeat: vi.fn(),
      onError: vi.fn(),
      onClose: vi.fn(),
    });

    await client.connectAndVolunteer('both', 'valid-token');
    await new Promise((r) => setTimeout(r, 350));

    expect(acks).toContain('camera');
    expect(acks).toContain('microphone');
    expect(acks.length).toBe(2);
    client.disconnect();
  });

  // ─────────────────────────────────────────────────────────────
  // 10. Raspberry Pi rejects a connection
  // ─────────────────────────────────────────────────────────────
  it('Scenario 10: Raspberry Pi rejects a connection and surfaces error message', async () => {
    let finalStatus = '';
    let errorMessage = '';

    const client = new PiConnectionClient(
      { ...baseConfig, mockMode: false },
      {
        onStatusChange: (st) => {
          finalStatus = st;
        },
        onSourceAcknowledged: vi.fn(),
        onLatencyUpdate: vi.fn(),
        onHeartbeat: vi.fn(),
        onError: (err) => {
          errorMessage = err;
        },
        onClose: vi.fn(),
      }
    );

    // Mock WebSocket to simulate Pi rejecting connection with a 'reject' message
    const mockWs = {
      send: vi.fn(),
      close: vi.fn(),
      readyState: 1, // OPEN
      onopen: null as any,
      onmessage: null as any,
      onerror: null as any,
      onclose: null as any,
    };

    // @ts-ignore
    global.WebSocket = vi.fn().mockImplementation(() => {
      setTimeout(() => {
        if (mockWs.onopen) mockWs.onopen({} as any);
        // Simulate Pi sending reject packet
        setTimeout(() => {
          if (mockWs.onmessage) {
            mockWs.onmessage({
              data: JSON.stringify({
                type: 'error',
                message: 'Capacity exceeded: maximum volunteer nodes (limit: 1)',
              }),
            } as any);
          }
        }, 50);
      }, 10);
      return mockWs;
    });

    await client.connectAndVolunteer('camera', 'mock-token');
    await new Promise((r) => setTimeout(r, 100));

    expect(finalStatus).toBe('rejected');
    expect(errorMessage).toContain('Capacity exceeded');
  });

  // ─────────────────────────────────────────────────────────────
  // 11. Raspberry Pi becomes unreachable
  // ─────────────────────────────────────────────────────────────
  it('Scenario 11: Raspberry Pi becomes unreachable and triggers timeout or error', async () => {
    let errorFired = false;
    let disconnectedFired = false;

    // @ts-ignore
    global.WebSocket = vi.fn().mockImplementation(() => {
      const mockWs = {
        close: vi.fn(),
        onopen: null as any,
        onerror: null as any,
        onclose: null as any,
      };
      setTimeout(() => {
        if (mockWs.onerror) mockWs.onerror(new Event('error'));
        if (mockWs.onclose) mockWs.onclose({ reason: 'Connection refused' } as any);
      }, 50);
      return mockWs;
    });

    const client = new PiConnectionClient(
      { ...baseConfig, mockMode: false },
      {
        onStatusChange: (st) => {
          if (st === 'disconnected') disconnectedFired = true;
        },
        onSourceAcknowledged: vi.fn(),
        onLatencyUpdate: vi.fn(),
        onHeartbeat: vi.fn(),
        onError: () => {
          errorFired = true;
        },
        onClose: vi.fn(),
      }
    );

    const result = await client.connectAndVolunteer('camera', 'some-token');
    expect(result).toBe(false);
    expect(errorFired).toBe(true);
    expect(disconnectedFired).toBe(true);
  });

  // ─────────────────────────────────────────────────────────────
  // 12. Browser tab closes (cleanup)
  // ─────────────────────────────────────────────────────────────
  it('Scenario 12: Browser tab close triggers full teardown of tracks and sockets', async () => {
    const media = new MediaCaptureManager();
    const stream = await media.startCapture({ video: true, audio: true });
    const tracks = stream.getTracks();

    const client = new PiConnectionClient(baseConfig, {
      onStatusChange: vi.fn(),
      onSourceAcknowledged: vi.fn(),
      onLatencyUpdate: vi.fn(),
      onHeartbeat: vi.fn(),
      onError: vi.fn(),
      onClose: vi.fn(),
    });

    await client.connectAndVolunteer('both', 'token');

    // Simulate pageunload
    media.stopCapture();
    client.disconnect();

    // Verify all tracks stopped
    tracks.forEach((t) => {
      expect(t.readyState).toBe('ended');
    });
    expect(client.getIsConnected()).toBe(false);
    expect(client.getIsVolunteering()).toBe(false);
  });

  // ─────────────────────────────────────────────────────────────
  // 13. User manually stops volunteering
  // ─────────────────────────────────────────────────────────────
  it('Scenario 13: User manually stops volunteering halts streams and resets client state', async () => {
    const media = new MediaCaptureManager();
    const stream = await media.startCapture({ video: true, audio: false });
    const track = stream.getVideoTracks()[0];

    let status = '';
    const client = new PiConnectionClient(baseConfig, {
      onStatusChange: (st) => {
        status = st;
      },
      onSourceAcknowledged: vi.fn(),
      onLatencyUpdate: vi.fn(),
      onHeartbeat: vi.fn(),
      onError: vi.fn(),
      onClose: vi.fn(),
    });

    await client.connectAndVolunteer('camera', 'token');
    expect(client.getIsVolunteering()).toBe(true);

    // Stop
    media.stopCapture();
    client.disconnect();

    expect(track.readyState).toBe('ended');
    expect(client.getIsVolunteering()).toBe(false);
    expect(status).toBe('disconnected');
  });

  // ─────────────────────────────────────────────────────────────
  // 14. Network changes during active session
  // ─────────────────────────────────────────────────────────────
  it('Scenario 14: Network loss during active session detects drop', async () => {
    const statuses: string[] = [];
    const client = new PiConnectionClient(
      { ...baseConfig, mockMode: false },
      {
        onStatusChange: (st) => statuses.push(st),
        onSourceAcknowledged: vi.fn(),
        onLatencyUpdate: vi.fn(),
        onHeartbeat: vi.fn(),
        onError: vi.fn(),
        onClose: vi.fn(),
      }
    );

    const mockWs = {
      send: vi.fn(),
      close: vi.fn(),
      readyState: 1,
      onopen: null as any,
      onmessage: null as any,
      onerror: null as any,
      onclose: null as any,
    };

    // @ts-ignore
    global.WebSocket = vi.fn().mockImplementation(() => {
      setTimeout(() => {
        if (mockWs.onopen) mockWs.onopen({} as any);
        if (mockWs.onmessage) mockWs.onmessage({ data: JSON.stringify({ type: 'authorized', granted_capabilities: ['camera'] }) });
      }, 10);
      return mockWs;
    });

    await client.connectAndVolunteer('camera', 'tok');
    expect(statuses).toContain('connected');

    // Pairing tokens are single-use; a dropped production stream requires fresh TOTP.
    mockWs.onclose({ reason: 'Network offline' });
    expect(statuses).toContain('disconnected');
    client.disconnect();
  });

  // ─────────────────────────────────────────────────────────────
  // 15. Reconnection after temporary connectivity loss
  // ─────────────────────────────────────────────────────────────
  it('Scenario 15: Production reconnect requires a fresh one-use pairing token', async () => {
    let reconnectReported = false;
    let errorMessage = '';
    const client = new PiConnectionClient(
      { ...baseConfig, mockMode: false },
      {
        onStatusChange: (st) => { if (st === 'reconnecting') reconnectReported = true; },
        onSourceAcknowledged: vi.fn(),
        onLatencyUpdate: vi.fn(),
        onHeartbeat: vi.fn(),
        onError: (message) => { errorMessage = message; },
        onClose: vi.fn(),
      }
    );
    const mockWs = {
      send: vi.fn(), close: vi.fn(), readyState: 1,
      onopen: null as any, onmessage: null as any, onclose: null as any,
    };
    // @ts-ignore
    global.WebSocket = vi.fn().mockImplementation(() => {
      setTimeout(() => {
        mockWs.onopen?.({} as any);
        mockWs.onmessage?.({ data: JSON.stringify({ type: 'authorized', granted_capabilities: ['camera'] }) });
      }, 10);
      return mockWs;
    });
    await client.connectAndVolunteer('camera', 'one-use-token');
    mockWs.onclose({ reason: 'Temporary glitch' });
    expect(reconnectReported).toBe(false);
    expect(errorMessage).toContain('single-use');
    client.disconnect();
  });

  // ─────────────────────────────────────────────────────────────
  // 16. Session expiration
  // ─────────────────────────────────────────────────────────────
  it('Scenario 16: Expired session is detected and invalidated', () => {
    const expiredSession = {
      token: 'tok-123',
      operatorId: 'operator-alpha',
      issuedAt: Date.now() - 30 * 60 * 1000,
      expiresAt: Date.now() - 5 * 1000, // expired 5 seconds ago
      isAuthenticated: true,
      nodeId: 'sip-pi-001',
    };

    expect(isSessionValid(expiredSession)).toBe(false);
  });

  // ─────────────────────────────────────────────────────────────
  // 17. Device does not continue capturing media after stopping
  // ─────────────────────────────────────────────────────────────
  it('Scenario 17: Device does not continue capturing media after stopping capture', async () => {
    const media = new MediaCaptureManager();
    const stream = await media.startCapture({ video: true, audio: true });
    const videoTrack = stream.getVideoTracks()[0];
    const audioTrack = stream.getAudioTracks()[0];

    expect(videoTrack.readyState).toBe('live');
    expect(audioTrack.readyState).toBe('live');

    // Trigger frame capture while live
    const mockVideoEl = {
      readyState: 4, // HAVE_ENOUGH_DATA
    } as HTMLVideoElement;

    const frameWhileLive = media.captureFrame(mockVideoEl);
    expect(frameWhileLive).not.toBeNull();

    // Now stop capture completely
    media.stopCapture();

    // Verify tracks are ended
    expect(videoTrack.readyState).toBe('ended');
    expect(audioTrack.readyState).toBe('ended');
    expect(media.hasVideo()).toBe(false);
    expect(media.hasAudio()).toBe(false);
    expect(media.getStream()).toBeNull();

    // Subsequent frame capture attempts must return null
    const frameAfterStop = media.captureFrame(mockVideoEl);
    expect(frameAfterStop).toBeNull();
  });
});
