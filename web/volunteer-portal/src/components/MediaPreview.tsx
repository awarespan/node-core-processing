import React, { useState } from 'react';
import { useVolunteer } from '../context/VolunteerContext';
import { Camera, Mic, FlipHorizontal, Eye, Volume2 } from 'lucide-react';

export const MediaPreview: React.FC = () => {
  const {
    localStream,
    videoRef,
    volunteerMode,
    telemetry,
    permissionState,
    connectionState,
    devices,
  } = useVolunteer();

  const [mirror, setMirror] = useState(false);

  const hasVideoMode = volunteerMode === 'camera' || volunteerMode === 'both';
  const hasAudioMode = volunteerMode === 'microphone' || volunteerMode === 'both';

  const isTransmitting =
    connectionState === 'CAMERA_CONNECTED' ||
    connectionState === 'MICROPHONE_CONNECTED' ||
    connectionState === 'BOTH_CONNECTED';

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
      {/* ──────────────── Video Preview Card ──────────────── */}
      {hasVideoMode && (
        <div className="border border-[#3c3c3c] bg-[#1a1a1a] flex flex-col">
          <div className="flex items-center justify-between px-4 py-3 border-b border-[#3c3c3c] bg-[#000000]">
            <div className="flex items-center gap-2">
              <Camera className="w-4 h-4 text-[#ff4f2b]" />
              <span className="text-xs font-mono uppercase tracking-wider text-[#f5f5f5]">
                LOCAL CAMERA PREVIEW
              </span>
            </div>

            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => setMirror(!mirror)}
                className={`p-1 border text-xs font-mono transition-colors cursor-pointer ${
                  mirror
                    ? 'border-[#ff4f2b] text-[#ff4f2b] bg-[#1a1a1a]'
                    : 'border-[#3c3c3c] text-[#737373] hover:text-[#f5f5f5]'
                }`}
                title="Mirror / Flip Video"
              >
                <FlipHorizontal className="w-3.5 h-3.5" />
              </button>
              <div className="text-[10px] font-mono px-2 py-0.5 border border-[#3c3c3c] text-[#bfbfbf] bg-[#1a1a1a]">
                640x360 // JPEG
              </div>
            </div>
          </div>

          <div className="relative aspect-video bg-[#000000] flex items-center justify-center overflow-hidden border-b border-[#3c3c3c]">
            {/* Live Video Element */}
            <video
              ref={videoRef}
              autoPlay
              playsInline
              muted
              className={`w-full h-full object-cover transition-transform ${
                mirror ? 'scale-x-[-1]' : ''
              } ${localStream ? 'block' : 'hidden'}`}
            />

            {/* Standby / Permission placeholder */}
            {!localStream && (
              <div className="flex flex-col items-center justify-center p-6 text-center text-[#737373]">
                <Camera className="w-10 h-10 mb-2 stroke-1 text-[#3c3c3c]" />
                {permissionState.camera === 'denied' ? (
                  <span className="text-xs font-mono text-red-400">
                    Camera permission was denied in your browser.
                  </span>
                ) : (
                  <span className="text-xs font-mono">
                    Camera preview inactive. Click &quot;Start Volunteering&quot; to initialize video feed.
                  </span>
                )}
              </div>
            )}

            {/* On-screen status overlays */}
            {localStream && (
              <>
                <div className="absolute top-2 left-2 flex items-center gap-2">
                  <div className="bg-black/80 px-2 py-0.5 border border-[#3c3c3c] text-[10px] font-mono text-emerald-400 flex items-center gap-1.5">
                    <span className="w-1.5 h-1.5 bg-emerald-400 animate-pulse" />
                    <span>LOCAL CAPTURE</span>
                  </div>

                  {telemetry.cameraActive && (
                    <div className="bg-black/80 px-2 py-0.5 border border-[#ff4f2b] text-[10px] font-mono text-[#ff4f2b] flex items-center gap-1.5">
                      <span>PI INGEST LIVE</span>
                    </div>
                  )}
                </div>

                <div className="absolute bottom-2 right-2 bg-black/80 px-2 py-0.5 border border-[#3c3c3c] text-[10px] font-mono text-[#bfbfbf]">
                  FPS: {telemetry.fps}
                </div>
              </>
            )}
          </div>

          <div className="p-3 text-[11px] font-mono text-[#bfbfbf] flex justify-between items-center bg-[#000000]">
            <div>
              <span className="text-[#737373]">SOURCE: </span>
              <span>{devices.selectedCameraId ? 'Selected Camera' : 'Default Hardware Device'}</span>
            </div>
            <div className="flex items-center gap-1">
              <Eye className="w-3.5 h-3.5 text-[#ff4f2b]" />
              <span className={telemetry.cameraActive ? 'text-emerald-400' : 'text-[#737373]'}>
                {telemetry.cameraActive ? 'Transmitting to Pi' : 'Standby'}
              </span>
            </div>
          </div>
        </div>
      )}

      {/* ──────────────── Microphone Activity Card ──────────────── */}
      {hasAudioMode && (
        <div className="border border-[#3c3c3c] bg-[#1a1a1a] flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between px-4 py-3 border-b border-[#3c3c3c] bg-[#000000]">
              <div className="flex items-center gap-2">
                <Mic className="w-4 h-4 text-[#ff4f2b]" />
                <span className="text-xs font-mono uppercase tracking-wider text-[#f5f5f5]">
                  MICROPHONE ACTIVITY INDICATOR
                </span>
              </div>
              <div className="text-[10px] font-mono px-2 py-0.5 border border-[#3c3c3c] text-[#bfbfbf] bg-[#1a1a1a]">
                WEB AUDIO // ANALYSER
              </div>
            </div>

            <div className="p-5 space-y-5">
              {/* RMS VU Meter */}
              <div>
                <div className="flex justify-between text-xs font-mono text-[#bfbfbf] mb-1.5">
                  <span>RMS SIGNAL VOLUME</span>
                  <span>{telemetry.audioRmsLevel} %</span>
                </div>
                <div className="h-4 bg-[#000000] border border-[#3c3c3c] p-0.5 flex">
                  <div
                    className="h-full bg-emerald-500 transition-all duration-75"
                    style={{ width: `${Math.min(100, telemetry.audioRmsLevel * 1.5)}%` }}
                  />
                  {telemetry.audioRmsLevel > 70 && (
                    <div
                      className="h-full bg-red-500 transition-all duration-75"
                      style={{ width: `${Math.min(30, (telemetry.audioRmsLevel - 70) * 3)}%` }}
                    />
                  )}
                </div>
              </div>

              {/* Peak Meter */}
              <div>
                <div className="flex justify-between text-xs font-mono text-[#bfbfbf] mb-1.5">
                  <span>PEAK TRANSIENT LEVEL</span>
                  <span>{telemetry.audioPeakLevel} %</span>
                </div>
                <div className="h-4 bg-[#000000] border border-[#3c3c3c] p-0.5 flex">
                  <div
                    className="h-full bg-[#ff4f2b] transition-all duration-75"
                    style={{ width: `${telemetry.audioPeakLevel}%` }}
                  />
                </div>
              </div>

              {/* Visual equalizer / activity bars */}
              <div>
                <span className="block text-[11px] font-mono uppercase text-[#737373] mb-2">
                  AUDIO ACTIVITY SPECTRUM
                </span>
                <div className="h-16 bg-[#000000] border border-[#3c3c3c] flex items-end justify-between p-2 gap-1">
                  {Array.from({ length: 24 }).map((_, i) => {
                    // Create simulated spectrum bars influenced by actual peak/RMS
                    const baseWeight = Math.sin((i / 24) * Math.PI);
                    const dynamicHeight = Math.min(
                      100,
                      Math.max(
                        6,
                        telemetry.audioRmsLevel * baseWeight * 1.4 + (i % 3 === 0 ? telemetry.audioPeakLevel * 0.4 : 0)
                      )
                    );
                    return (
                      <div
                        key={i}
                        className={`w-full transition-all duration-75 ${
                          dynamicHeight > 80
                            ? 'bg-red-500'
                            : dynamicHeight > 50
                            ? 'bg-[#ff4f2b]'
                            : dynamicHeight > 20
                            ? 'bg-emerald-500'
                            : 'bg-[#3c3c3c]'
                        }`}
                        style={{ height: `${localStream ? dynamicHeight : 6}%` }}
                      />
                    );
                  })}
                </div>
              </div>

              {permissionState.microphone === 'denied' && (
                <div className="p-3 bg-red-950/40 border border-red-800 text-red-300 text-xs font-mono">
                  Microphone permission was denied.
                </div>
              )}
            </div>
          </div>

          <div className="p-3 text-[11px] font-mono text-[#bfbfbf] flex justify-between items-center bg-[#000000] border-t border-[#3c3c3c]">
            <div>
              <span className="text-[#737373]">AUDIO STATUS: </span>
              <span>{isTransmitting ? 'Monitored & Streamed' : 'Standby'}</span>
            </div>
            <div className="flex items-center gap-1.5">
              <Volume2 className="w-3.5 h-3.5 text-[#ff4f2b]" />
              <span className={telemetry.microphoneActive ? 'text-emerald-400' : 'text-[#737373]'}>
                {telemetry.microphoneActive ? 'Mic Active' : 'Muted / Idle'}
              </span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
