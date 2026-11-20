/**
 * AWARESPAN Volunteer Portal — Configuration Service
 * Reads environment variables with secure defaults.
 */

import { PiNodeConfig } from '../types';

export const getInitialConfig = (): PiNodeConfig => {
  const envHost = import.meta.env.VITE_PI_HOST as string | undefined;
  const envPort = import.meta.env.VITE_PI_PORT as string | undefined;
  const envGatewayPort = import.meta.env.VITE_PI_GATEWAY_PORT as string | undefined;
  const envSsl = import.meta.env.VITE_PI_USE_SSL as string | undefined;
  const envNodeId = import.meta.env.VITE_PI_NODE_ID as string | undefined;
  const envMockMode = import.meta.env.VITE_MOCK_MODE as string | undefined;

  const isBrowser = typeof window !== 'undefined';
  const defaultHost = envHost || (isBrowser ? window.location.hostname : '127.0.0.1');
  const defaultPort = envPort ? parseInt(envPort, 10) : 8766;
  const defaultSsl = envSsl !== undefined
    ? envSsl === 'true'
    : (isBrowser && window.location.protocol === 'https:');

  // In development/test, default to mock mode if not explicitly disabled or if on localhost without node
  const defaultMock = envMockMode !== undefined ? envMockMode === 'true' : false;

  return {
    piHost: defaultHost,
    piPort: defaultPort,
    gatewayPort: envGatewayPort ? parseInt(envGatewayPort, 10) : (isBrowser && window.location.port ? parseInt(window.location.port, 10) : 8443),
    useSsl: defaultSsl,
    nodeId: envNodeId || 'sip-pi-001',
    mockMode: defaultMock,
  };
};

export const formatWsUrl = (config: PiNodeConfig, path: string = '/ingest'): string => {
  const protocol = config.useSsl ? 'wss' : 'ws';
  const cleanPath = path.startsWith('/') ? path : `/${path}`;
  return `${protocol}://${config.piHost}:${config.piPort}${cleanPath}`;
};
