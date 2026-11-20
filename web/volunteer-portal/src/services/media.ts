/**
 * AWARESPAN Volunteer Portal — Media Management Service
 * Controls camera and microphone permissions, device enumeration, live stream capture,
 * audio analysis (VU-meter), frame extraction, and complete hardware release.
 */

export interface DeviceLists {
  cameras: MediaDeviceInfo[];
  microphones: MediaDeviceInfo[];
}

export interface AudioLevels {
  rms: number;  // 0 - 100
  peak: number; // 0 - 100
}

export class MediaCaptureManager {
  private mediaStream: MediaStream | null = null;
  private audioContext: AudioContext | null = null;
  private analyserNode: AnalyserNode | null = null;
  private audioSourceNode: MediaStreamAudioSourceNode | null = null;
  private offscreenCanvas: HTMLCanvasElement | null = null;
  private offscreenCtx: CanvasRenderingContext2D | null = null;
  private frameSequence: number = 0;

  /**
   * Enumerate connected audio/video input devices.
   */
  public async getAvailableDevices(): Promise<DeviceLists> {
    if (!navigator.mediaDevices || !navigator.mediaDevices.enumerateDevices) {
      return { cameras: [], microphones: [] };
    }

    try {
      const devices = await navigator.mediaDevices.enumerateDevices();
      const cameras = devices.filter((d) => d.kind === 'videoinput');
      const microphones = devices.filter((d) => d.kind === 'audioinput');
      return { cameras, microphones };
    } catch (err) {
      console.error('[MediaCaptureManager] Error enumerating devices:', err);
      return { cameras: [], microphones: [] };
    }
  }

  /**
   * Request media stream according to specified mode and device IDs.
   */
  public async startCapture(options: {
    video: boolean;
    audio: boolean;
    cameraId?: string;
    microphoneId?: string;
    width?: number;
    height?: number;
  }): Promise<MediaStream> {
    // Release any previous active streams before opening new hardware
    this.stopCapture();

    const videoConstraints: MediaTrackConstraints | boolean = options.video
      ? {
          deviceId: options.cameraId ? { exact: options.cameraId } : undefined,
          width: { ideal: options.width || 640 },
          height: { ideal: options.height || 360 },
          frameRate: { ideal: 15, max: 20 },
        }
      : false;

    const audioConstraints: MediaTrackConstraints | boolean = options.audio
      ? {
          deviceId: options.microphoneId ? { exact: options.microphoneId } : undefined,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        }
      : false;

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: videoConstraints,
        audio: audioConstraints,
      });

      this.mediaStream = stream;

      // If audio is requested, initialize Web Audio API analyzer
      if (options.audio && stream.getAudioTracks().length > 0) {
        this.initAudioAnalyser(stream);
      }

      // Initialize offscreen canvas for frame capture
      if (options.video && stream.getVideoTracks().length > 0) {
        this.offscreenCanvas = document.createElement('canvas');
        this.offscreenCanvas.width = options.width || 640;
        this.offscreenCanvas.height = options.height || 360;
        this.offscreenCtx = this.offscreenCanvas.getContext('2d');
      }

      this.frameSequence = 0;
      return stream;
    } catch (err: unknown) {
      this.stopCapture();
      throw err;
    }
  }

  /**
   * Initializes Web Audio analyser for VU meter monitoring.
   */
  private initAudioAnalyser(stream: MediaStream): void {
    try {
      const AudioCtx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      if (!AudioCtx) return;

      this.audioContext = new AudioCtx();
      this.analyserNode = this.audioContext.createAnalyser();
      this.analyserNode.fftSize = 256;
      this.analyserNode.smoothingTimeConstant = 0.5;

      this.audioSourceNode = this.audioContext.createMediaStreamSource(stream);
      this.audioSourceNode.connect(this.analyserNode);
    } catch (e) {
      console.warn('[MediaCaptureManager] Web Audio API init error:', e);
    }
  }

  /**
   * Reads current real-time audio levels (RMS and Peak) for the VU meter.
   */
  public getAudioLevels(): AudioLevels {
    if (!this.analyserNode) {
      return { rms: 0, peak: 0 };
    }

    const dataArray = new Uint8Array(this.analyserNode.frequencyBinCount);
    this.analyserNode.getByteTimeDomainData(dataArray);

    let sumSquares = 0;
    let peak = 0;

    for (let i = 0; i < dataArray.length; i++) {
      // Time-domain data is centered around 128
      const normalized = (dataArray[i] - 128) / 128;
      const absVal = Math.abs(normalized);
      if (absVal > peak) {
        peak = absVal;
      }
      sumSquares += normalized * normalized;
    }

    const rms = Math.sqrt(sumSquares / dataArray.length);
    return {
      rms: Math.min(100, Math.round(rms * 160)),
      peak: Math.min(100, Math.round(peak * 120)),
    };
  }

  /**
   * Captures the current video frame from a video element, encodes to JPEG,
   * and returns base64 payload matching node_runtime protocol:
   * { type: "frame", frame_id: int, ts_ms: int, jpeg_b64: string }
   */
  public captureFrame(
    videoElement: HTMLVideoElement,
    quality: number = 0.65
  ): { frameId: number; tsMs: number; jpegB64: string } | null {
    if (!this.mediaStream || !this.offscreenCanvas || !this.offscreenCtx) {
      return null;
    }

    if (videoElement.readyState < HTMLMediaElement.HAVE_CURRENT_DATA) {
      return null;
    }

    const width = this.offscreenCanvas.width;
    const height = this.offscreenCanvas.height;

    try {
      this.offscreenCtx.drawImage(videoElement, 0, 0, width, height);
      const dataUrl = this.offscreenCanvas.toDataURL('image/jpeg', quality);
      // Strip 'data:image/jpeg;base64,' prefix
      const commaIdx = dataUrl.indexOf(',');
      const jpegB64 = commaIdx >= 0 ? dataUrl.substring(commaIdx + 1) : dataUrl;

      this.frameSequence += 1;
      return {
        frameId: this.frameSequence,
        tsMs: Date.now(),
        jpegB64,
      };
    } catch (e) {
      console.warn('[MediaCaptureManager] Frame capture error:', e);
      return null;
    }
  }

  /**
   * Stops all active audio and video tracks immediately.
   * Releases hardware handles so camera/mic LEDs turn off.
   */
  public stopCapture(): void {
    if (this.mediaStream) {
      this.mediaStream.getTracks().forEach((track) => {
        track.stop();
      });
      this.mediaStream = null;
    }

    if (this.audioSourceNode) {
      this.audioSourceNode.disconnect();
      this.audioSourceNode = null;
    }

    if (this.analyserNode) {
      this.analyserNode.disconnect();
      this.analyserNode = null;
    }

    if (this.audioContext && this.audioContext.state !== 'closed') {
      try {
        this.audioContext.close();
      } catch (e) {
        console.warn('[MediaCaptureManager] AudioContext close error:', e);
      }
      this.audioContext = null;
    }

    this.offscreenCanvas = null;
    this.offscreenCtx = null;
  }

  public getStream(): MediaStream | null {
    return this.mediaStream;
  }

  public hasVideo(): boolean {
    return !!(this.mediaStream && this.mediaStream.getVideoTracks().length > 0 && this.mediaStream.getVideoTracks()[0].readyState === 'live');
  }

  public hasAudio(): boolean {
    return !!(this.mediaStream && this.mediaStream.getAudioTracks().length > 0 && this.mediaStream.getAudioTracks()[0].readyState === 'live');
  }
}
