import React from 'react';
import { useVolunteer } from '../context/VolunteerContext';
import { Clock, Send, Wifi, Server, CheckCircle2, XCircle } from 'lucide-react';

export const SessionMonitor: React.FC = () => {
  const { telemetry, connectionState, piCapabilities, config } = useVolunteer();
  const microphoneAllowed = config.mockMode || piCapabilities?.browser_microphone_allowed === true;

  const formatDuration = (seconds: number) => {
    const hrs = Math.floor(seconds / 3600);
    const mins = Math.floor((seconds % 3600) / 60);
    const secs = seconds % 60;
    return `${hrs > 0 ? `${hrs}:` : ''}${mins < 10 && hrs > 0 ? '0' : ''}${mins}:${
      secs < 10 ? '0' : ''
    }${secs}`;
  };

  const formatBytes = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
  };

  return (
    <div className="border border-[#3c3c3c] bg-[#1a1a1a] p-5 mb-6">
      <div className="flex items-center justify-between pb-3 border-b border-[#3c3c3c] mb-4">
        <div className="flex items-center gap-2">
          <Server className="w-4 h-4 text-[#ff4f2b]" />
          <h2 className="text-xs font-mono uppercase tracking-wider text-[#bfbfbf]">
            LIVE SESSION TELEMETRY & HEALTH
          </h2>
        </div>
        <div className="text-[10px] font-mono text-[#737373]">
          AUTHORITATIVE BACKEND: RASPBERRY PI
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        {/* Metric 1: Duration */}
        <div className="bg-[#000000] border border-[#3c3c3c] p-3">
          <div className="flex items-center gap-1.5 text-[11px] font-mono text-[#737373] mb-1">
            <Clock className="w-3 h-3 text-[#ff4f2b]" />
            <span>SESSION TIME</span>
          </div>
          <div className="text-xl font-mono font-medium text-[#f5f5f5]">
            {formatDuration(telemetry.durationSeconds)}
          </div>
        </div>

        {/* Metric 2: Frames Sent */}
        <div className="bg-[#000000] border border-[#3c3c3c] p-3">
          <div className="flex items-center gap-1.5 text-[11px] font-mono text-[#737373] mb-1">
            <Send className="w-3 h-3 text-[#ff4f2b]" />
            <span>FRAMES SENT</span>
          </div>
          <div className="text-xl font-mono font-medium text-[#f5f5f5]">
            {telemetry.framesSent.toLocaleString()}
          </div>
        </div>

        {/* Metric 3: Data Transfer */}
        <div className="bg-[#000000] border border-[#3c3c3c] p-3">
          <div className="flex items-center gap-1.5 text-[11px] font-mono text-[#737373] mb-1">
            <Wifi className="w-3 h-3 text-[#ff4f2b]" />
            <span>DATA TRANSFERRED</span>
          </div>
          <div className="text-xl font-mono font-medium text-[#f5f5f5]">
            {formatBytes(telemetry.bytesSent)}
          </div>
        </div>

        {/* Metric 4: Camera Source ACK */}
        <div className="bg-[#000000] border border-[#3c3c3c] p-3">
          <div className="text-[11px] font-mono text-[#737373] mb-1">
            CAMERA SOURCE ACK
          </div>
          <div className="flex items-center gap-1.5">
            {telemetry.cameraActive ? (
              <span className="flex items-center gap-1 text-xs font-mono text-emerald-400">
                <CheckCircle2 className="w-4 h-4" />
                <span>CONFIRMED</span>
              </span>
            ) : (
              <span className="flex items-center gap-1 text-xs font-mono text-[#737373]">
                <XCircle className="w-4 h-4" />
                <span>INACTIVE</span>
              </span>
            )}
          </div>
        </div>

        {/* Metric 5: Mic Source ACK / input interlock */}
        <div className="bg-[#000000] border border-[#3c3c3c] p-3">
          <div className="text-[11px] font-mono text-[#737373] mb-1">
            MIC INPUT STATUS
          </div>
          <div className="flex items-center gap-1.5">
            {!microphoneAllowed ? (
              <span className="flex items-center gap-1 text-xs font-mono text-amber-300">
                <XCircle className="w-4 h-4" />
                <span>LOCKED</span>
              </span>
            ) : telemetry.microphoneActive ? (
              <span className="flex items-center gap-1 text-xs font-mono text-emerald-400">
                <CheckCircle2 className="w-4 h-4" />
                <span>CONFIRMED</span>
              </span>
            ) : (
              <span className="flex items-center gap-1 text-xs font-mono text-[#737373]">
                <XCircle className="w-4 h-4" />
                <span>INACTIVE</span>
              </span>
            )}
          </div>
        </div>
      </div>

      {connectionState === 'RECONNECTING' && (
        <div className="mt-4 p-3 bg-amber-950/40 border border-amber-800 text-amber-300 text-xs font-mono flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 bg-amber-400 animate-ping" />
            <span>Connection temporarily interrupted. Auto-reconnection in progress...</span>
          </div>
          <span>Attempt {telemetry.reconnectAttempts}</span>
        </div>
      )}
    </div>
  );
};
