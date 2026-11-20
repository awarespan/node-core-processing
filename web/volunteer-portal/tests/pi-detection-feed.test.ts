import { describe, expect, it, vi } from 'vitest';
import { PiConnectionClient } from '../src/services/piClient';
import type { PiDetectionEvent, AnnotatedFramePayload } from '../src/types';

describe('Pi annotated detection dashboard feed', () => {
  it('subscribes to the read-only dashboard stream and forwards the event and boxed frame', async () => {
    const sockets: Array<any> = [];
    // The first socket is the authenticated volunteer gateway; the second is the read-only core dashboard socket.
    // @ts-ignore
    global.WebSocket = vi.fn().mockImplementation((url: string) => {
      const socket: any = {
        url,
        readyState: 1,
        send: vi.fn(),
        close: vi.fn(),
        onopen: null,
        onmessage: null,
        onerror: null,
        onclose: null,
      };
      sockets.push(socket);
      return socket;
    });

    const receivedEvents: PiDetectionEvent[] = [];
    const receivedFrames: AnnotatedFramePayload[] = [];
    const acknowledgedSources: string[] = [];
    const receivedCapabilities: unknown[] = [];
    const client = new PiConnectionClient(
      { piHost: 'node.example.test', piPort: 8766, gatewayPort: 8443, useSsl: true, nodeId: 'node-01', mockMode: false },
      {
        onStatusChange: vi.fn(),
        onSourceAcknowledged: (source) => acknowledgedSources.push(source),
        onLatencyUpdate: vi.fn(),
        onHeartbeat: vi.fn(),
        onError: vi.fn(),
        onClose: vi.fn(),
        onDetectionEvent: (event) => receivedEvents.push(event),
        onAnnotatedFrame: (frame) => receivedFrames.push(frame),
        onCapabilities: (capabilities) => receivedCapabilities.push(capabilities),
      },
    );

    const connecting = client.connectAndVolunteer('camera', 'session-token');
    expect(sockets).toHaveLength(1);
    expect(sockets[0].url).toBe('wss://node.example.test:8443/ws/volunteer');
    sockets[0].onopen?.({});
    expect(sockets[0].send).toHaveBeenCalledWith(JSON.stringify({ type: 'pairing_token', token: 'session-token' }));
    sockets[0].onmessage?.({ data: JSON.stringify({ type: 'authorized', granted_capabilities: ['camera'] }) });
    await expect(connecting).resolves.toBe(true);

    expect(sockets).toHaveLength(2);
    expect(sockets[1].url).toBe('wss://node.example.test:8766/');
    // Only the authenticated gateway's authorised capability grants camera access.
    expect(acknowledgedSources).toEqual(['camera']);

    const capabilities = {
      type: 'capabilities', speaker_output_available: true,
      browser_microphone_allowed: false, audio_owner: 'raspberry_pi',
    };
    sockets[1].onmessage?.({ data: JSON.stringify(capabilities) });
    expect(receivedCapabilities).toEqual([capabilities]);

    const event: PiDetectionEvent = {
      event_id: 'evt-test-01', ts_ms: 1794424649000, tier: 'tier1', labels: ['dog'],
      max_confidence: 0.91, action: 'alert', frame_id: 42, source_id: 'ws-ingest',
    };
    const frame: AnnotatedFramePayload = {
      type: 'frame', frame_id: 42, ts_ms: event.ts_ms, source_id: 'ws-ingest',
      annotated_b64: '/9j/annotated-image-with-boxes', latency_ms: 55, fps: 9,
    };
    sockets[1].onmessage?.({ data: JSON.stringify({ type: 'log', event }) });
    sockets[1].onmessage?.({ data: JSON.stringify(frame) });

    expect(receivedEvents).toEqual([event]);
    expect(receivedFrames).toEqual([frame]);
    client.disconnect();
  });
});
