import React from 'react';
import { useVolunteer } from '../context/VolunteerContext';
import { Camera, Mic, Radio, Play, Square, RefreshCw, AlertCircle } from 'lucide-react';

interface VolunteerControlsProps {
  onOpenAuthPrompt: () => void;
}

export const VolunteerControls: React.FC<VolunteerControlsProps> = ({ onOpenAuthPrompt }) => {
  const {
    connectionState,
    volunteerMode,
    setVolunteerMode,
    devices,
    selectCamera,
    selectMicrophone,
    refreshDevices,
    startVolunteering,
    stopVolunteering,
    session,
    piCapabilities,
    config,
  } = useVolunteer();

  const isVolunteering =
    connectionState === 'CAMERA_CONNECTED' ||
    connectionState === 'MICROPHONE_CONNECTED' ||
    connectionState === 'BOTH_CONNECTED' ||
    connectionState === 'CONNECTING' ||
    connectionState === 'AWAITING_PI_ACK' ||
    connectionState === 'RECONNECTING';

  const microphoneBlocked = !config.mockMode && (piCapabilities?.speaker_output_available === true || piCapabilities?.browser_microphone_allowed !== true);
  const showCameraSelect = volunteerMode === 'camera' || volunteerMode === 'both';
  const showMicSelect = volunteerMode === 'microphone' || volunteerMode === 'both';

  const handleStart = async () => {
    if (!session) {
      onOpenAuthPrompt();
      return;
    }
    await startVolunteering();
  };

  return (
    <div className="border border-[#3c3c3c] bg-[#1a1a1a] p-5 mb-6">
      <div className="flex items-center justify-between pb-3 border-b border-[#3c3c3c] mb-4">
        <div className="flex items-center gap-2">
          <Radio className="w-4 h-4 text-[#ff4f2b]" />
          <h2 className="text-xs font-mono uppercase tracking-wider text-[#bfbfbf]">
            VOLUNTEER CONFIGURATION & CONTROLS
          </h2>
        </div>
        <button
          onClick={refreshDevices}
          className="text-xs font-mono text-[#bfbfbf] hover:text-[#f5f5f5] flex items-center gap-1 cursor-pointer"
          title="Rescan audio and video hardware"
        >
          <RefreshCw className="w-3 h-3" />
          <span>Rescan Hardware</span>
        </button>
      </div>

      {/* Mode selection buttons */}
      <div className="mb-5">
        <label className="block text-xs font-mono uppercase text-[#737373] mb-2">
          Select Volunteer Source Mode:
        </label>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
          {/* Option 1: Camera */}
          <button
            type="button"
            disabled={isVolunteering}
            onClick={() => setVolunteerMode('camera')}
            className={`flex items-center justify-center gap-2 py-3 px-4 font-mono text-xs uppercase tracking-wider transition-colors border cursor-pointer disabled:opacity-60 ${
              volunteerMode === 'camera'
                ? 'bg-[#ff4f2b] text-black border-[#ff4f2b] font-semibold'
                : 'bg-[#000000] text-[#f5f5f5] border-[#3c3c3c] hover:border-[#bfbfbf]'
            }`}
          >
            <Camera className="w-4 h-4" />
            <span>01 // Camera</span>
          </button>

          {/* Option 2: Microphone */}
          <button
            type="button"
            disabled={isVolunteering || microphoneBlocked}
            onClick={() => setVolunteerMode('microphone')}
            className={`flex items-center justify-center gap-2 py-3 px-4 font-mono text-xs uppercase tracking-wider transition-colors border cursor-pointer disabled:opacity-60 ${
              volunteerMode === 'microphone'
                ? 'bg-[#ff4f2b] text-black border-[#ff4f2b] font-semibold'
                : 'bg-[#000000] text-[#f5f5f5] border-[#3c3c3c] hover:border-[#bfbfbf]'
            }`}
          >
            <Mic className="w-4 h-4" />
            <span>02 // Microphone</span>
          </button>

          {/* Option 3: Camera + Microphone */}
          <button
            type="button"
            disabled={isVolunteering || microphoneBlocked}
            onClick={() => setVolunteerMode('both')}
            className={`flex items-center justify-center gap-2 py-3 px-4 font-mono text-xs uppercase tracking-wider transition-colors border cursor-pointer disabled:opacity-60 ${
              volunteerMode === 'both'
                ? 'bg-[#ff4f2b] text-black border-[#ff4f2b] font-semibold'
                : 'bg-[#000000] text-[#f5f5f5] border-[#3c3c3c] hover:border-[#bfbfbf]'
            }`}
          >
            <div className="flex items-center gap-1">
              <Camera className="w-3.5 h-3.5" />
              <span>+</span>
              <Mic className="w-3.5 h-3.5" />
            </div>
            <span>03 // Both Sources</span>
          </button>
        </div>

        {microphoneBlocked && (
          <p className="mt-3 text-[11px] font-mono text-amber-300 flex items-center gap-1.5">
            <AlertCircle className="w-3.5 h-3.5 shrink-0" />
            <span>{piCapabilities?.speaker_output_available
              ? 'Pi audio output is present. The browser microphone and audio source options are locked.'
              : 'The Pi has not advertised an operational microphone ingestion path. Audio donation is locked.'}</span>
          </p>
        )}

        {volunteerMode === 'both' && (
          <p className="mt-2 text-[11px] font-mono text-[#bfbfbf] flex items-center gap-1.5">
            <AlertCircle className="w-3.5 h-3.5 text-[#ff4f2b] shrink-0" />
            <span>
              Both source permissions are required. Microphone donation is permitted only after the Pi explicitly advertises an available input path and no Pi-owned output conflict exists.
            </span>
          </p>
        )}
      </div>

      {/* Hardware selection dropdowns */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
        {showCameraSelect && (
          <div>
            <label className="block text-xs font-mono uppercase text-[#737373] mb-1.5 flex items-center gap-1.5">
              <Camera className="w-3.5 h-3.5 text-[#ff4f2b]" />
              <span>Target Video Camera</span>
            </label>
            <select
              disabled={isVolunteering}
              value={devices.selectedCameraId}
              onChange={(e) => selectCamera(e.target.value)}
              className="w-full bg-[#000000] border border-[#3c3c3c] focus:border-[#ff4f2b] px-3 py-2 text-xs font-mono text-[#f5f5f5] outline-none disabled:opacity-60 cursor-pointer"
            >
              {devices.cameras.length === 0 ? (
                <option value="">Default System Camera</option>
              ) : (
                devices.cameras.map((cam, idx) => (
                  <option key={cam.deviceId || idx} value={cam.deviceId}>
                    {cam.label || `Camera Device ${idx + 1}`}
                  </option>
                ))
              )}
            </select>
          </div>
        )}

        {showMicSelect && (
          <div>
            <label className="block text-xs font-mono uppercase text-[#737373] mb-1.5 flex items-center gap-1.5">
              <Mic className="w-3.5 h-3.5 text-[#ff4f2b]" />
              <span>Target Microphone</span>
            </label>
            <select
              disabled={isVolunteering}
              value={devices.selectedMicrophoneId}
              onChange={(e) => selectMicrophone(e.target.value)}
              className="w-full bg-[#000000] border border-[#3c3c3c] focus:border-[#ff4f2b] px-3 py-2 text-xs font-mono text-[#f5f5f5] outline-none disabled:opacity-60 cursor-pointer"
            >
              {devices.microphones.length === 0 ? (
                <option value="">Default System Microphone</option>
              ) : (
                devices.microphones.map((mic, idx) => (
                  <option key={mic.deviceId || idx} value={mic.deviceId}>
                    {mic.label || `Microphone Device ${idx + 1}`}
                  </option>
                ))
              )}
            </select>
          </div>
        )}
      </div>

      {/* Primary Action Button */}
      <div className="pt-2 border-t border-[#3c3c3c] flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3">
        <div className="text-xs font-mono text-[#737373]">
          {isVolunteering ? (
            <span className="text-emerald-400">● Session is transmitting media</span>
          ) : session ? (
            <span>Ready to volunteer. Device permissions will be requested on start.</span>
          ) : (
            <span className="text-amber-400">Authentication required before volunteering.</span>
          )}
        </div>

        <div>
          {isVolunteering ? (
            <button
              type="button"
              onClick={stopVolunteering}
              className="w-full sm:w-auto px-6 py-3 bg-red-600 hover:bg-red-700 text-white font-mono text-xs uppercase tracking-wider font-semibold transition-colors flex items-center justify-center gap-2 cursor-pointer shadow-lg"
            >
              <Square className="w-4 h-4 fill-white" />
              <span>STOP VOLUNTEERING</span>
            </button>
          ) : (
            <button
              type="button"
              onClick={handleStart}
              className="w-full sm:w-auto px-6 py-3 bg-[#ff4f2b] hover:bg-[#e04523] text-black font-mono text-xs uppercase tracking-wider font-semibold transition-colors flex items-center justify-center gap-2 cursor-pointer shadow-lg"
            >
              <Play className="w-4 h-4 fill-black" />
              <span>START VOLUNTEERING NOW</span>
            </button>
          )}
        </div>
      </div>
    </div>
  );
};
