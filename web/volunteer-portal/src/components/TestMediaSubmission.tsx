import React, { useState, useEffect, useRef } from 'react';
import { Upload, Image as ImageIcon, Video, Mic, CheckCircle, AlertTriangle, ShieldCheck, ArrowRight } from 'lucide-react';

interface NodeInfo {
  id: string;
  name: string;
  status: string;
  batteryLevel?: number;
}

export const TestMediaSubmission: React.FC = () => {
  const [nodes, setNodes] = useState<NodeInfo[]>([]);
  const [selectedNodeId, setSelectedNodeId] = useState<string>('');
  const [mediaType, setMediaType] = useState<'IMAGE' | 'VIDEO' | 'AUDIO'>('IMAGE');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);

  const [uploadStatus, setUploadStatus] = useState<'IDLE' | 'UPLOADING' | 'DISPATCHED' | 'PROCESSING' | 'COMPLETED' | 'FAILED'>('IDLE');
  const [progress, setProgress] = useState<number>(0);
  const [statusMessage, setStatusMessage] = useState<string>('');
  const [result, setResult] = useState<any>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);

  const backendBaseUrl = 'https://api.awarespan.bchbenjamin.in';

  useEffect(() => {
    // This portal is hosted by the active node. Resolve its backend-assigned
    // identity locally; never fall back to fabricated node IDs.
    fetch(`${window.location.origin}/api/volunteer/config`)
      .then(async (res) => {
        if (!res.ok) throw new Error(`Local node config returned HTTP ${res.status}`);
        return res.json();
      })
      .then((data) => {
        const nodeId = typeof data.node_id === 'string' ? data.node_id.trim() : '';
        if (!nodeId) throw new Error('The local node has not completed backend enrollment.');
        setNodes([{ id: nodeId, name: `Local AWARESPAN node (${nodeId})`, status: 'LOCAL' }]);
        setSelectedNodeId(nodeId);
        setStatusMessage('Connected to the active local node identity.');
      })
      .catch((error: unknown) => {
        const message = error instanceof Error ? error.message : String(error);
        setNodes([]);
        setSelectedNodeId('');
        setUploadStatus('FAILED');
        setStatusMessage(`Cannot identify the active node: ${message}`);
      });
  }, []);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setSelectedFile(file);
    setUploadStatus('IDLE');
    setResult(null);
    setStatusMessage('');

    if (file.type.startsWith('image/')) {
      const url = URL.createObjectURL(file);
      setPreviewUrl(url);
    } else {
      setPreviewUrl(null);
    }
  };

  const handleSubmit = async () => {
    if (!selectedFile || !selectedNodeId) {
      setUploadStatus('FAILED');
      setStatusMessage('No enrolled local node is available.');
      return;
    }

    setUploadStatus('UPLOADING');
    setProgress(10);
    setResult(null);
    setStatusMessage(`Uploading ${mediaType.toLowerCase()} to the AWARESPAN backend...`);
    console.info('[AWARESPAN upload] Starting upload', {
      nodeId: selectedNodeId,
      mediaType,
      filename: selectedFile.name,
      sizeBytes: selectedFile.size,
    });

    try {
      const formData = new FormData();
      formData.append('file', selectedFile);
      formData.append('nodeId', selectedNodeId);
      formData.append('mediaType', mediaType);
      setProgress(35);

      const response = await fetch(`${backendBaseUrl}/api/v1/media/upload`, {
        method: 'POST',
        body: formData,
      });
      if (!response.ok) {
        const detail = (await response.text()).slice(0, 240);
        throw new Error(`Upload rejected (HTTP ${response.status}): ${detail || response.statusText}`);
      }

      const data = await response.json();
      const currentMediaId = String(data.mediaId || '');
      if (!currentMediaId) throw new Error('Backend accepted the request without returning a media ID.');
      console.info('[AWARESPAN upload] Backend accepted media', {
        mediaId: currentMediaId,
        nodeId: selectedNodeId,
        sizeBytes: data.sizeBytes,
        commandId: data.commandId,
      });
      setProgress(55);
      setUploadStatus('PROCESSING');
      setStatusMessage(`Backend accepted ${currentMediaId}. Waiting for node inference...`);

      for (let attempt = 0; attempt < 40; attempt += 1) {
        await new Promise(resolve => window.setTimeout(resolve, 1500));
        const pollRes = await fetch(`${backendBaseUrl}/api/v1/media/${encodeURIComponent(currentMediaId)}/result`);
        if (!pollRes.ok) {
          throw new Error(`Could not read processing result (HTTP ${pollRes.status}).`);
        }
        const resData = await pollRes.json();
        if (resData.status === 'INCIDENT_GENERATED' || resData.status === 'PROCESSED') {
          setProgress(100);
          setUploadStatus('COMPLETED');
          setResult(resData);
          setStatusMessage(
            resData.incidentId
              ? `Inference completed. Incident ${resData.incidentId} was generated.`
              : resData.message || 'Inference completed; no qualifying threat was detected.'
          );
          console.info('[AWARESPAN upload] Node reported processing result', resData);
          return;
        }
        if (resData.status === 'FAILED' || resData.status === 'ERROR') {
          throw new Error(resData.message || 'The node reported a media processing failure.');
        }
        setProgress(Math.min(90, 55 + Math.round(((attempt + 1) / 40) * 35)));
      }

      setUploadStatus('FAILED');
      setProgress(100);
      setStatusMessage(`Backend accepted ${currentMediaId}, but the node did not report an inference result within 60 seconds. Check the node command-polling and runtime logs; this upload is NOT marked completed.`);
      console.error('[AWARESPAN upload] Processing acknowledgement timed out', { mediaId: currentMediaId, nodeId: selectedNodeId });
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : String(err);
      setUploadStatus('FAILED');
      setStatusMessage(`Submission failed: ${message}`);
      console.error('[AWARESPAN upload] Submission failed', err);
    }
  };

  return (
    <section className="border border-[#3c3c3c] bg-[#141414] p-5 mb-6 relative">
      <div className="flex items-center justify-between pb-3 border-b border-[#3c3c3c] mb-4">
        <div className="flex items-center gap-2">
          <Upload className="w-4 h-4 text-[#ff4f2b]" />
          <h2 className="text-xs font-mono uppercase tracking-wider text-[#bfbfbf]">
            TEST MEDIA INGESTION PIPELINE (PHOTO // VIDEO // AUDIO)
          </h2>
        </div>
        <div className="flex items-center gap-1.5 text-[11px] text-[#737373] font-mono">
          <ShieldCheck className="w-3.5 h-3.5 text-[#ff4f2b]" />
          <span>Real Edge Inference Verification</span>
        </div>
      </div>

      {/* Target Node Selection */}
      <div className="mb-4">
        <label className="block text-xs font-mono uppercase text-[#737373] mb-1.5">
          Target AWARESPAN Edge Node:
        </label>
        <div className="relative">
          <select
            value={selectedNodeId}
            onChange={(e) => setSelectedNodeId(e.target.value)}
            className="w-full bg-[#000000] border border-[#3c3c3c] text-[#f5f5f5] text-xs font-mono px-3 py-2.5 rounded-none focus:outline-none focus:border-[#ff4f2b] transition-colors"
          >
            {nodes.length === 0 && <option value="">Resolving enrolled local node...</option>}
            {nodes.map(n => (
              <option key={n.id} value={n.id}>
                {n.name} [{n.status}]
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Media Type Tabs */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 mb-4">
        <button
          type="button"
          onClick={() => { setMediaType('IMAGE'); setSelectedFile(null); setPreviewUrl(null); }}
          className={`flex items-center justify-center gap-2 py-2.5 px-3 text-xs font-mono uppercase border transition-colors cursor-pointer ${
            mediaType === 'IMAGE'
              ? 'bg-[#ff4f2b] text-black border-[#ff4f2b] font-semibold'
              : 'bg-[#000000] text-[#bfbfbf] border-[#3c3c3c] hover:border-[#737373]'
          }`}
        >
          <ImageIcon className="w-3.5 h-3.5" />
          <span>01 // Photo (Image)</span>
        </button>

        <button
          type="button"
          onClick={() => { setMediaType('VIDEO'); setSelectedFile(null); setPreviewUrl(null); }}
          className={`flex items-center justify-center gap-2 py-2.5 px-3 text-xs font-mono uppercase border transition-colors cursor-pointer ${
            mediaType === 'VIDEO'
              ? 'bg-[#ff4f2b] text-black border-[#ff4f2b] font-semibold'
              : 'bg-[#000000] text-[#bfbfbf] border-[#3c3c3c] hover:border-[#737373]'
          }`}
        >
          <Video className="w-3.5 h-3.5" />
          <span>02 // Video</span>
        </button>

        <button
          type="button"
          onClick={() => { setMediaType('AUDIO'); setSelectedFile(null); setPreviewUrl(null); }}
          className={`flex items-center justify-center gap-2 py-2.5 px-3 text-xs font-mono uppercase border transition-colors cursor-pointer ${
            mediaType === 'AUDIO'
              ? 'bg-[#ff4f2b] text-black border-[#ff4f2b] font-semibold'
              : 'bg-[#000000] text-[#bfbfbf] border-[#3c3c3c] hover:border-[#737373]'
          }`}
        >
          <Mic className="w-3.5 h-3.5" />
          <span>03 // Audio</span>
        </button>
      </div>

      {/* File Drop / Select Area */}
      <div
        onClick={() => fileInputRef.current?.click()}
        className="border border-dashed border-[#3c3c3c] hover:border-[#ff4f2b] bg-[#000000] p-6 text-center cursor-pointer transition-colors mb-4 flex flex-col items-center justify-center min-h-[140px]"
      >
        <input
          ref={fileInputRef}
          type="file"
          accept={
            mediaType === 'IMAGE' ? 'image/jpeg,image/png,image/webp' :
            mediaType === 'VIDEO' ? 'video/mp4,video/webm,video/quicktime' :
            'audio/wav,audio/mp3,audio/mpeg,audio/ogg'
          }
          onChange={handleFileChange}
          className="hidden"
        />

        {selectedFile ? (
          <div className="space-y-2">
            <div className="text-xs text-[#ff4f2b] font-mono font-semibold flex items-center justify-center gap-2">
              <CheckCircle className="w-4 h-4" />
              <span>{selectedFile.name} ({(selectedFile.size / 1024).toFixed(1)} KB)</span>
            </div>
            {previewUrl && (
              <img
                src={previewUrl}
                alt="Upload preview"
                className="max-h-40 mx-auto border border-[#3c3c3c] object-contain mt-2"
              />
            )}
            <p className="text-[11px] text-[#737373]">Click to choose a different file</p>
          </div>
        ) : (
          <div className="space-y-1.5">
            <Upload className="w-6 h-6 text-[#737373] mx-auto mb-1" />
            <div className="text-xs text-[#f5f5f5] font-mono">
              Click to browse or drop {mediaType.toLowerCase()} file here
            </div>
            <div className="text-[10px] text-[#737373] font-mono">
              {mediaType === 'IMAGE' && 'Supported: JPG, PNG, WEBP • Evaluated as single camera observation'}
              {mediaType === 'VIDEO' && 'Supported: MP4, WEBM • Decoded to frames with bounded backpressure'}
              {mediaType === 'AUDIO' && 'Supported: WAV, MP3 • Verified by edge audio ingestion interface'}
            </div>
          </div>
        )}
      </div>

      {/* Action Button & Status Bar */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-3">
        <button
          type="button"
          disabled={!selectedFile || !selectedNodeId || uploadStatus === 'UPLOADING' || uploadStatus === 'PROCESSING'}
          onClick={handleSubmit}
          className="w-full sm:w-auto px-6 py-2.5 bg-[#ff4f2b] hover:bg-[#e03d1b] text-black font-mono text-xs font-semibold uppercase tracking-wider transition-colors disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer flex items-center justify-center gap-2"
        >
          <span>Submit to {selectedNodeId}</span>
          <ArrowRight className="w-3.5 h-3.5" />
        </button>

        {uploadStatus !== 'IDLE' && (
          <div className="text-xs font-mono text-[#bfbfbf] flex items-center gap-2">
            <span className={`w-2 h-2 rounded-full ${
              uploadStatus === 'COMPLETED' ? 'bg-emerald-500' :
              uploadStatus === 'FAILED' ? 'bg-rose-500' : 'bg-[#ff4f2b] animate-pulse'
            }`} />
            <span>{statusMessage}</span>
          </div>
        )}
      </div>

      {/* Progress Bar */}
      {uploadStatus !== 'IDLE' && (
        <div className="w-full bg-[#000000] h-1.5 mt-3 border border-[#3c3c3c] overflow-hidden">
          <div
            className={`h-full transition-all duration-300 ${
              uploadStatus === 'COMPLETED' ? 'bg-emerald-500' :
              uploadStatus === 'FAILED' ? 'bg-rose-500' : 'bg-[#ff4f2b]'
            }`}
            style={{ width: `${progress}%` }}
          />
        </div>
      )}

      {/* Incident Result Card */}
      {result && result.incidentId && (
        <div className="mt-4 border border-[#ff4f2b] bg-[#1a0a05] p-3 text-xs font-mono space-y-1">
          <div className="text-[#ff4f2b] font-semibold flex items-center gap-2">
            <AlertTriangle className="w-4 h-4" />
            <span>THREAT INCIDENT GENERATED BY AWARESPAN EDGE NODE</span>
          </div>
          <div className="text-[#f5f5f5]">
            Incident ID: <code className="bg-[#000000] px-1 py-0.5 border border-[#3c3c3c] text-[#ff4f2b]">{result.incidentId}</code>
          </div>
          <div className="text-[#bfbfbf]">
            Threat Type: <b>{result.tier?.toUpperCase()} ({result.labels?.join(', ')})</b> • Confidence: <b>{(result.confidence * 100).toFixed(1)}%</b>
          </div>
          <div className="text-emerald-400 text-[11px] pt-1">
            ✓ Incident persisted by backend • ✓ Broadcast to connected Android clients
          </div>
        </div>
      )}
    </section>
  );
};
