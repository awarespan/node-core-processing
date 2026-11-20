import { afterEach, describe, expect, it, vi } from 'vitest';
import { authenticateOperator, clearSession, getActiveSession } from '../src/services/auth';
import type { PiNodeConfig } from '../src/types';

const liveConfig: PiNodeConfig = {
  piHost: '127.0.0.1',
  piPort: 8766,
  gatewayPort: 8443,
  useSsl: false,
  nodeId: 'sip-pi-001',
  mockMode: false,
};

afterEach(() => {
  clearSession();
  vi.restoreAllMocks();
});

describe('production volunteer gateway authentication contract', () => {
  it('POSTs the TOTP in headers and returns separate pairing and session expiries', async () => {
    const responseBody = {
      success: true,
      pairing_token: 'single-use-pairing-token',
      pairing_expires_in: 300,
      session_expires_in: 3600,
      expires_at: Date.now() + 3600_000,
      node_id: 'sip-pi-001',
      granted_capabilities: ['camera'],
    };
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(responseBody), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    );
    vi.stubGlobal('fetch', fetchMock);

    const result = await authenticateOperator(' bch_benjamin ', '123456', liveConfig);

    expect(result.success).toBe(true);
    expect(result.session?.token).toBe('single-use-pairing-token');
    expect(result.session?.operatorId).toBe('bch_benjamin');
    expect(result.session?.nodeId).toBe('sip-pi-001');
    expect(result.session?.pairingExpiresAt).toBeGreaterThan(Date.now());
    expect(result.session?.expiresAt).toBe(responseBody.expires_at);
    expect(getActiveSession()?.token).toBe('single-use-pairing-token');

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, options] = fetchMock.mock.calls[0];
    expect(url).toBe('http://127.0.0.1:8443/api/volunteer/auth');
    expect(options.method).toBe('POST');
    expect(options.headers['X-TOTP-Code']).toBe('123456');
    expect(options.headers['X-Operator-ID']).toBe('bch_benjamin');
    expect(options.headers['X-Volunteer-Capability']).toBe('both');
    expect(options.body).toBeUndefined();
    expect(url).not.toContain('123456');
  });

  it('surfaces an authentication rejection without creating a session', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ success: false }), { status: 401 }),
    ));
    const result = await authenticateOperator('bch_benjamin', '000001', liveConfig);
    expect(result.success).toBe(false);
    expect(result.errorMessage).toContain('Authentication rejected');
    expect(getActiveSession()).toBeNull();
  });
});
