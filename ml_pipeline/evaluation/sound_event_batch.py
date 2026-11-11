"""
AWARESPAN — Batch Sound Event Evaluation
Evaluates WAV audio files using YAMNet for scream and acoustic threat detection.

Project: AWARESPAN
Tagline: Awareness Without Boundaries.
Official problem statement: An AI-Powered Safety Device.
Contact: awarespan@bchbenjamin.in
"""

import argparse
import os
import numpy as np
import scipy.io.wavfile as wavfile


def main():
    parser = argparse.ArgumentParser(description="Batch Audio Evaluation")
    parser.add_argument("--input-dir", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--confidence", type=float, default=0.5)
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)
    print("Loading YAMNet model...")
    try:
        import tensorflow_hub as hub
        model = hub.load("https://tfhub.dev/google/yamnet/1")
    except Exception as exc:
        print(f"TensorFlow / YAMNet not available: {exc}")
        return

    for filename in os.listdir(args.input_dir):
        if not filename.endswith(".wav"):
            continue

        filepath = os.path.join(args.input_dir, filename)
        print(f"Processing audio {filepath}...")
        try:
            sample_rate, wav_data = wavfile.read(filepath)
            if len(wav_data.shape) > 1:
                wav_data = np.mean(wav_data, axis=1)

            if wav_data.dtype == np.int16:
                wav_data = wav_data / 32768.0
            elif wav_data.dtype == np.int32:
                wav_data = wav_data / 2147483648.0
            wav_data = wav_data.astype(np.float32)

            chunk_size = int(sample_rate * 0.96)
            for i in range(0, len(wav_data), chunk_size):
                chunk = wav_data[i:i + chunk_size]
                if len(chunk) < chunk_size:
                    chunk = np.pad(chunk, (0, chunk_size - len(chunk)), "constant")
                scores, _, _ = model(chunk)
                scores_np = scores.numpy()
                scream_prob = max(scores_np[:, 11].max(), scores_np[:, 12].max())
                if scream_prob > args.confidence:
                    print(f"Detected threat sound in {filename}! Prob: {scream_prob:.2f}")

        except Exception as exc:
            print(f"Failed to process {filepath}: {exc}")


if __name__ == "__main__":
    main()
