import React, { useState } from 'react';
import { useVolunteer } from '../context/VolunteerContext';
import { Cpu, Wifi, Activity, CheckCircle, AlertTriangle } from 'lucide-react';

export const OverviewSection: React.FC = () => {
  const { config, connectionState, telemetry, piCapabilities } = useVolunteer();
  const [probing, setProbing] = useState(false);
  const [probeResult, setProbeResult] = useState<string | null>(null);

  const endpointUrl = `${config.useSsl ? 'wss' : 'ws'}://${config.piHost}:${config.gatewayPort}/ws/volunteer`;

  const handleTestProbe = async () => {
    setProbing(true);
    setProbeResult(null);

    if (config.mockMode) {
      setTimeout(() => {
        setProbing(false);
        setProbeResult('MOCK NODE RESPONDED: OK (Simulated latency: 22ms)');
      }, 500);
      return;
    }

    try {
      const protocol = config.useSsl ? 'wss' : 'ws';
      const healthUrl = `${protocol}://${config.piHost}:${config.piPort}/health`;
      const ws = new WebSocket(healthUrl);

      const timeout = setTimeout(() => {
        try { ws.close(); } catch (_) { /* ignore */ }
        setProbing(false);
        setProbeResult(`PROBE TIMEOUT: Node at ${healthUrl} did not respond within 3s.`);
      }, 3000);

      ws.onmessage = (ev) => {
        clearTimeout(timeout);
        setProbing(false);
        setProbeResult(`NODE RESPONDED: ${ev.data}`);
      };

      ws.onerror = () => {
        clearTimeout(timeout);
        setProbing(false);
        setProbeResult(`PROBE ERROR: Connection refused to ${healthUrl}`);
      };
    } catch (e: unknown) {
      setProbing(false);
      setProbeResult(`PROBE FAILED: ${(e as Error).message}`);
    }
  };

  const getSourceCount = () => {
    let count = 0;
    if (telemetry.cameraActive) count++;
    if (telemetry.microphoneActive) count++;
    return count;
  };

  return (
    <div className="border border-[#3c3c3c] bg-[#1a1a1a] p-5 mb-6">
      <div className="flex flex-col md:flex-row md:items-center justify-between pb-4 border-b border-[#3c3c3c] gap-4">
        <div>
          <div className="flex items-center gap-2">
            <Cpu className="w-4 h-4 text-[#ff4f2b]" />
            <h2 className="text-xs font-mono uppercase tracking-wider text-[#bfbfbf]">
              TARGET RASPBERRY PI EDGE NODE
            </h2>
          </div>
          <div className="text-lg font-mono font-medium text-[#f5f5f5] mt-1 flex items-center gap-3">
            <span>{config.nodeId}</span>
            <span className="text-xs font-normal text-[#737373] bg-[#000000] px-2 py-0.5 border border-[#3c3c3c]">
              {endpointUrl}
            </span>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={handleTestProbe}
            disabled={probing}
            className="px-3 py-1.5 text-xs font-mono uppercase tracking-wider text-[#bfbfbf] hover:text-[#f5f5f5] bg-[#000000] border border-[#3c3c3c] hover:border-[#bfbfbf] transition-colors cursor-pointer disabled:opacity-50 flex items-center gap-1.5"
          >
            <Activity className="w-3.5 h-3.5 text-[#ff4f2b]" />
            <span>{probing ? 'Probing...' : 'Probe Node Health'}</span>
          </button>
        </div>
      </div>

      {probeResult && (
        <div className="mt-3 p-2.5 bg-[#000000] border border-[#3c3c3c] text-xs font-mono text-[#bfbfbf] flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 bg-[#ff4f2b]" />
            <span>{probeResult}</span>
          </div>
          <button
            onClick={() => setProbeResult(null)}
            className="text-[#737373] hover:text-[#f5f5f5] text-[11px] cursor-pointer"
          >
            [dismiss]
          </button>
        </div>
      )}

      {/* Grid of operational indicators */}
      <div className="grid grid-cols-1 min-[360px]:grid-cols-2 sm:grid-cols-4 gap-3 sm:gap-4 mt-4">
        <div className="bg-[#000000] border border-[#3c3c3c] p-3">
          <span className="text-[11px] font-mono uppercase text-[#737373] block mb-1">
            NODE STATUS
          </span>
          <div className="flex items-center gap-2">
            {connectionState === 'NOT_CONNECTED' ? (
              <span className="text-xs font-mono text-[#bfbfbf]">READY / STANDBY</span>
            ) : connectionState.includes('CONNECTED') ? (
              <div className="flex items-center gap-1.5 text-xs font-mono text-emerald-400">
                <CheckCircle className="w-3.5 h-3.5" />
                <span>ONLINE (ACTIVE)</span>
              </div>
            ) : (
              <div className="flex items-center gap-1.5 text-xs font-mono text-amber-400">
                <AlertTriangle className="w-3.5 h-3.5" />
                <span>{connectionState}</span>
              </div>
            )}
          </div>
        </div>

        <div className="bg-[#000000] border border-[#3c3c3c] p-3">
          <span className="text-[11px] font-mono uppercase text-[#737373] block mb-1">
            ACTIVE SOURCES
          </span>
          <div className="text-xs font-mono text-[#f5f5f5] flex items-center gap-2">
            <span className="text-base font-semibold text-[#ff4f2b]">
              {getSourceCount()}
            </span>
            <span className="text-[#737373]">
              / 2 (Cam: {telemetry.cameraActive ? 'ON' : 'OFF'} | Mic: {piCapabilities?.browser_microphone_allowed ? (telemetry.microphoneActive ? 'ON' : 'OFF') : 'LOCKED'})
            </span>
          </div>
        </div>

        <div className="bg-[#000000] border border-[#3c3c3c] p-3">
          <span className="text-[11px] font-mono uppercase text-[#737373] block mb-1">
            RTT LATENCY
          </span>
          <div className="flex items-center gap-1 text-xs font-mono text-[#f5f5f5]">
            <Wifi className="w-3.5 h-3.5 text-[#ff4f2b]" />
            <span>{telemetry.latencyMs > 0 ? `${telemetry.latencyMs} ms` : '—'}</span>
          </div>
        </div>

        <div className="bg-[#000000] border border-[#3c3c3c] p-3">
          <span className="text-[11px] font-mono uppercase text-[#737373] block mb-1">
            HEARTBEAT
          </span>
          <div className="text-xs font-mono text-[#f5f5f5]">
            {telemetry.lastHeartbeatTs ? (
              <span>{new Date(telemetry.lastHeartbeatTs).toLocaleTimeString()}</span>
            ) : (
              <span className="text-[#737373]">Awaiting Stream</span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
