import React, { useState } from 'react';
import { useVolunteer } from '../context/VolunteerContext';
import { Settings, X, Save, AlertTriangle } from 'lucide-react';

interface ConfigModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const ConfigModal: React.FC<ConfigModalProps> = ({ isOpen, onClose }) => {
  const { config, updateConfig } = useVolunteer();

  const [piHost, setPiHost] = useState(config.piHost);
  const [piPort, setPiPort] = useState(config.piPort);
  const [gatewayPort, setGatewayPort] = useState(config.gatewayPort);
  const [useSsl, setUseSsl] = useState(config.useSsl);
  const [nodeId, setNodeId] = useState(config.nodeId);
  const [mockMode, setMockMode] = useState(config.mockMode);

  if (!isOpen) return null;

  const handleSave = (e: React.FormEvent) => {
    e.preventDefault();
    updateConfig({
      piHost,
      piPort: Number(piPort),
      gatewayPort: Number(gatewayPort),
      useSsl,
      nodeId,
      mockMode,
    });
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
      <div className="w-full max-w-lg max-h-[90dvh] overflow-y-auto bg-[#000000] border border-[#3c3c3c] shadow-2xl relative">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-[#3c3c3c] bg-[#1a1a1a]">
          <div className="flex items-center gap-2">
            <Settings className="w-4 h-4 text-[#ff4f2b]" />
            <h2 className="font-mono text-sm uppercase tracking-wider text-[#f5f5f5]">
              NODE TARGET CONFIGURATION
            </h2>
          </div>
          <button
            onClick={onClose}
            className="text-[#737373] hover:text-[#f5f5f5] p-1 cursor-pointer transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSave} className="p-4 sm:p-6 space-y-4">
          {/* Mode Switch */}
          <div className="p-3.5 bg-[#1a1a1a] border border-[#3c3c3c] flex items-center justify-between">
            <div>
              <span className="block text-xs font-mono uppercase text-[#f5f5f5] font-semibold">
                Development / Mock Mode
              </span>
              <span className="text-[11px] font-mono text-[#737373]">
                Simulates node handshake and ACKs without live physical hardware
              </span>
            </div>
            <input
              type="checkbox"
              checked={mockMode}
              onChange={(e) => setMockMode(e.target.checked)}
              className="w-5 h-5 accent-[#ff4f2b] cursor-pointer"
            />
          </div>

          {!mockMode && (
            <div className="p-3 bg-amber-950/40 border border-amber-800 text-amber-300 text-xs font-mono flex items-start gap-2">
              <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
              <div>
                <strong>Live Node Mode:</strong> The frontend will connect directly to{' '}
                <code>{useSsl ? 'wss' : 'ws'}://{piHost}:{gatewayPort}/ws/volunteer</code> for authenticated media, plus runtime health/dashboard on port {piPort}. No responses are fabricated.
              </div>
            </div>
          )}

          <div>
            <label className="block text-xs font-mono uppercase text-[#bfbfbf] mb-1">
              Node Hostname or IP
            </label>
            <input
              type="text"
              value={piHost}
              onChange={(e) => setPiHost(e.target.value)}
              placeholder="e.g. 192.168.1.50 or 10.42.0.1"
              className="w-full bg-[#1a1a1a] border border-[#3c3c3c] focus:border-[#ff4f2b] px-3 py-2 text-sm font-mono text-[#f5f5f5] outline-none"
              required
            />
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-mono uppercase text-[#bfbfbf] mb-1">
                Core runtime port (health / dashboard)
              </label>
              <input
                type="number"
                value={piPort}
                onChange={(e) => setPiPort(Number(e.target.value))}
                className="w-full bg-[#1a1a1a] border border-[#3c3c3c] focus:border-[#ff4f2b] px-3 py-2 text-sm font-mono text-[#f5f5f5] outline-none"
                required
              />
            </div>

            <div>
              <label className="block text-xs font-mono uppercase text-[#bfbfbf] mb-1">
                Volunteer gateway port (default 8443)
              </label>
              <input
                type="number"
                value={gatewayPort}
                onChange={(e) => setGatewayPort(Number(e.target.value))}
                className="w-full bg-[#1a1a1a] border border-[#3c3c3c] focus:border-[#ff4f2b] px-3 py-2 text-sm font-mono text-[#f5f5f5] outline-none"
                required
              />
            </div>
            <div>
              <label className="block text-xs font-mono uppercase text-[#bfbfbf] mb-1">
                Node Identifier
              </label>
              <input
                type="text"
                value={nodeId}
                onChange={(e) => setNodeId(e.target.value)}
                className="w-full bg-[#1a1a1a] border border-[#3c3c3c] focus:border-[#ff4f2b] px-3 py-2 text-sm font-mono text-[#f5f5f5] outline-none"
                required
              />
            </div>
          </div>

          <div className="flex items-center gap-2 pt-1">
            <input
              type="checkbox"
              id="useSsl"
              checked={useSsl}
              onChange={(e) => setUseSsl(e.target.checked)}
              className="w-4 h-4 accent-[#ff4f2b] cursor-pointer"
            />
            <label htmlFor="useSsl" className="text-xs font-mono text-[#bfbfbf] cursor-pointer">
              Use Secure Transport (WSS / HTTPS)
            </label>
          </div>

          {/* Quick presets */}
          <div className="pt-2 border-t border-[#1a1a1a]">
            <span className="text-[11px] font-mono text-[#737373] block mb-1">
              QUICK PRESETS:
            </span>
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                onClick={() => {
                  setPiHost('localhost');
                  setPiPort(8766);
                  setGatewayPort(8443);
                  setMockMode(false);
                }}
                className="px-2 py-1 text-[11px] font-mono bg-[#1a1a1a] hover:bg-[#252525] border border-[#3c3c3c] text-[#bfbfbf] cursor-pointer"
              >
                Localhost (8766)
              </button>
              <button
                type="button"
                onClick={() => {
                  setPiHost('10.42.0.1');
                  setPiPort(8766);
                  setGatewayPort(8443);
                  setMockMode(false);
                }}
                className="px-2 py-1 text-[11px] font-mono bg-[#1a1a1a] hover:bg-[#252525] border border-[#3c3c3c] text-[#bfbfbf] cursor-pointer"
              >
                USB-C tether (10.42.0.1)
              </button>
              <button
                type="button"
                onClick={() => {
                  setPiHost('192.168.1.50');
                  setPiPort(8766);
                  setGatewayPort(8443);
                  setMockMode(true);
                }}
                className="px-2 py-1 text-[11px] font-mono bg-[#1a1a1a] hover:bg-[#252525] border border-[#3c3c3c] text-[#ff4f2b] cursor-pointer"
              >
                Mock Simulator
              </button>
            </div>
          </div>

          {/* Footer buttons */}
          <div className="pt-4 flex items-center justify-end gap-3 border-t border-[#3c3c3c]">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-xs font-mono uppercase text-[#bfbfbf] hover:text-[#f5f5f5] border border-[#3c3c3c] hover:border-[#bfbfbf] transition-colors cursor-pointer"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="px-5 py-2 text-xs font-mono uppercase font-semibold text-black bg-[#ff4f2b] hover:bg-[#e04523] transition-colors flex items-center gap-1.5 cursor-pointer"
            >
              <Save className="w-3.5 h-3.5" />
              <span>Apply Configuration</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
