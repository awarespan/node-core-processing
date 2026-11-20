import React from 'react';
import { Radio, X, CheckCircle2, AlertTriangle, FileCode2 } from 'lucide-react';

interface BackendContractDocsProps {
  isOpen: boolean;
  onClose: () => void;
}

export const BackendContractDocs: React.FC<BackendContractDocsProps> = ({ isOpen, onClose }) => {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/85 backdrop-blur-sm p-4 overflow-y-auto">
      <div className="w-full max-w-4xl bg-[#000000] border border-[#3c3c3c] shadow-2xl relative my-8 max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-[#3c3c3c] bg-[#1a1a1a] shrink-0">
          <div className="flex items-center gap-2">
            <Radio className="w-4 h-4 text-[#ff4f2b]" />
            <h2 className="font-mono text-sm uppercase tracking-wider text-[#f5f5f5]">
              AWARESPAN NODE BACKEND SPECIFICATION &amp; INTEGRATION CONTRACT
            </h2>
          </div>
          <button
            onClick={onClose}
            className="text-[#737373] hover:text-[#f5f5f5] p-1 cursor-pointer transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Scrollable Content */}
        <div className="p-6 overflow-y-auto space-y-6 text-xs font-mono leading-relaxed select-text">
          {/* Section 1 */}
          <div className="p-4 bg-[#1a1a1a] border border-[#3c3c3c]">
            <h3 className="text-sm font-semibold text-[#f5f5f5] uppercase mb-2 flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-emerald-400" />
              1. Verified Implementation in `node-core-processing`
            </h3>
            <p className="text-[#bfbfbf] mb-3">
              Inspection of <code>node-backend/node_runtime/main.py</code> and configuration in <code>shared/config/settings.py</code> confirmed the following live mechanisms:
            </p>
            <ul className="list-disc list-inside space-y-1.5 text-[#bfbfbf]">
              <li><strong className="text-white">Port &amp; Host:</strong> WebSocket server binds to <code>0.0.0.0:8766</code> (configurable via <code>RUNTIME_PORT</code>, default 8766).</li>
              <li><strong className="text-white">Health Endpoint:</strong> <code>ws://&lt;host&gt;:8766/health</code> sends node identity plus ALSA playback and microphone-input capability fields, then closes.</li>
              <li><strong className="text-white">Frame Ingestion Endpoint:</strong> <code>ws://&lt;host&gt;:8766/ingest</code> receives client frame packets.</li>
              <li>
                <strong className="text-white">Frame Payload Schema:</strong>
                <pre className="mt-1 p-2 bg-[#000000] border border-[#3c3c3c] text-emerald-300 overflow-x-auto">
{`{
  "type": "frame",
  "frame_id": 1042,
  "ts_ms": 1794424649000,
  "jpeg_b64": "<base64 encoded JPEG buffer>"
}`}
                </pre>
              </li>
              <li><strong className="text-white">Dashboard Broadcast Endpoint:</strong> <code>ws://&lt;host&gt;:8766/</code> broadcasts annotated visual frames, threat evaluation events, and refreshed hardware capabilities.</li>
            </ul>
          </div>

          {/* Section 2 */}
          <div className="p-4 bg-[#1a1a1a] border border-amber-900/60">
            <h3 className="text-sm font-semibold text-amber-400 uppercase mb-2 flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-amber-400" />
              2. Disabled / Future Node Capabilities
            </h3>
            <p className="text-[#bfbfbf] mb-3">
              The current production portal is camera-only until microphone ingestion is implemented. The controls below distinguish existing node behaviour from future proposals.
            </p>

            <div className="space-y-4">
              <div className="p-3 bg-[#000000] border border-[#3c3c3c]">
                <h4 className="text-[#f5f5f5] font-bold mb-1">A. Operator Authentication Handshake</h4>
                <p className="text-[#737373] mb-2">
                  Currently, <code>/ingest</code> accepts connections without credentials. For security, the node must verify the operator TOTP and issue a short-lived volunteer token.
                </p>
                <div className="text-[#bfbfbf]">
                  <strong>Proposed Endpoint:</strong> <code>POST /api/v1/auth/volunteer-session</code>
                  <pre className="mt-1 p-2 bg-[#1a1a1a] border border-[#3c3c3c] text-[#bfbfbf]">
{`Request:  { "operator_id": "operator-alpha", "totp_code": "482910" }
Response: { "status": "authorized", "session_token": "vol-tok-...", "expires_at": 1794425549000 }`}
                  </pre>
                </div>
              </div>

              <div className="p-3 bg-[#000000] border border-[#3c3c3c]">
                <h4 className="text-[#f5f5f5] font-bold mb-1">B. Microphone Ingestion — DISABLED</h4>
                <p className="text-[#737373] mb-2">
                  The Pi currently has no live volunteer-microphone ingestion pipeline. Production capability reports microphone input unavailable; the portal blocks browser microphone permissions and the Pi rejects audio chunks. The browser cannot own or substitute for Pi audio output.
                </p>
                <pre className="p-2 bg-[#1a1a1a] border border-[#3c3c3c] text-[#bfbfbf]">
{`{ "type": "source_rejected", "source": "microphone", "reason": "Pi runtime audio ingestion is not enabled." }`}
                </pre>
              </div>

              <div className="p-3 bg-[#000000] border border-[#3c3c3c]">
                <h4 className="text-[#f5f5f5] font-bold mb-1">C. Bidirectional Source Acknowledgement (ACK)</h4>
                <p className="text-[#737373] mb-2">
                  The frontend must not fake an active state. The Pi currently acknowledges camera input only; microphone input is explicitly rejected:
                </p>
                <pre className="p-2 bg-[#1a1a1a] border border-[#3c3c3c] text-[#bfbfbf]">
{`{ "type": "ack", "source": "camera" }
{ "type": "source_rejected", "source": "microphone", "reason": "Pi runtime audio ingestion is not enabled." }
{ "type": "heartbeat", "ts_ms": 1794424650000 }`}
                </pre>
              </div>

              <div className="p-3 bg-[#000000] border border-[#3c3c3c]">
                <h4 className="text-[#f5f5f5] font-bold mb-1">D. Raspberry Pi &rarr; Telegram Notifications</h4>
                <p className="text-[#737373] mb-2">
                  In compliance with Section 10 of the design requirements, Telegram alerts originate strictly from the Pi node. Below is the Python patch for <code>node_runtime/main.py</code>:
                </p>
                <pre className="p-2 bg-[#1a1a1a] border border-[#3c3c3c] text-emerald-300 overflow-x-auto">
{`from node_runtime.monitoring.telegram_notify import send_message

async def _ingest_handler(self, websocket):
    node_id = self.settings.node_id
    send_message(f"📡 <b>AWARESPAN Source Connected</b>\\nNode: <code>{node_id}</code>\\nSource: <b>Volunteer Device</b>")
    try:
        async for message in websocket:
            ...
    finally:
        send_message(f"⚠️ <b>AWARESPAN Source Disconnected</b>\\nNode: <code>{node_id}</code>\\nSource: <b>Volunteer Device</b>")`}
                </pre>
              </div>
            </div>
          </div>

          {/* Section 3 */}
          <div className="p-4 bg-[#1a1a1a] border border-[#3c3c3c]">
            <h3 className="text-sm font-semibold text-[#f5f5f5] uppercase mb-2 flex items-center gap-2">
              <FileCode2 className="w-4 h-4 text-[#ff4f2b]" />
              3. Client Abstraction Status
            </h3>
            <p className="text-[#bfbfbf]">
              This frontend repository contains a clean integration abstraction (<code>PiConnectionClient</code>, <code>MediaCaptureManager</code>, and <code>auth.ts</code>). It fully supports:
            </p>
            <ul className="list-disc list-inside space-y-1 text-[#bfbfbf] mt-2">
              <li>Direct live streaming to the verified <code>/ingest</code> endpoint using standard Canvas/JPEG encoding.</li>
              <li>Dedicated Dev/Mock Mode with simulated latency, ACKs, and capacity limits for testing without Pi hardware.</li>
              <li>Zero hardcoded backend tokens or Telegram secrets in the frontend repository.</li>
            </ul>
          </div>
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-[#3c3c3c] bg-[#1a1a1a] flex justify-end shrink-0">
          <button
            onClick={onClose}
            className="px-4 py-2 text-xs font-mono uppercase bg-[#ff4f2b] text-black font-semibold hover:bg-[#e04523] transition-colors cursor-pointer"
          >
            Close Documentation
          </button>
        </div>
      </div>
    </div>
  );
};
