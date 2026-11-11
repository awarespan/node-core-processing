"""
AWARESPAN — Edge Model Benchmarking Utility
Measures loading time, inference latency, memory footprint, and FPS for edge deployment.

Project: AWARESPAN
Tagline: Awareness Without Boundaries.
Official problem statement: An AI-Powered Safety Device.
Contact: awarespan@bchbenjamin.in
"""

import argparse
import json
import os
import time
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional

import numpy as np

try:
    import psutil
except ImportError:
    psutil = None

from shared.logging.logger import get_logger
from ml_pipeline.adapters.audio_adapter import AudioThreatAdapter
from ml_pipeline.adapters.base import ThreatModelAdapter
from ml_pipeline.adapters.yolo_adapter import YOLOv8Adapter

log = get_logger("ml_pipeline.benchmark")


@dataclass
class BenchmarkResult:
    model_id: str
    artifact_path: str
    iterations: int
    load_time_sec: float
    latency_mean_ms: float
    latency_median_ms: float
    latency_p95_ms: float
    latency_min_ms: float
    latency_max_ms: float
    throughput_fps: float
    peak_rss_mb: float
    platform: str
    timestamp: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ModelBenchmarkRunner:
    """Runs controlled inference benchmarks on threat model adapters."""

    def __init__(self, warmup_runs: int = 3, test_runs: int = 15):
        self.warmup_runs = warmup_runs
        self.test_runs = test_runs

    def benchmark_visual_adapter(
        self,
        adapter: ThreatModelAdapter,
        input_resolution: tuple = (640, 640),
    ) -> BenchmarkResult:
        """Benchmark a visual model adapter."""
        # Generate representative synthetic frame
        h, w = input_resolution
        test_frame = np.random.randint(0, 255, (h, w, 3), dtype=np.uint8)

        # Warmup runs
        for _ in range(self.warmup_runs):
            adapter.predict(test_frame)

        # Measured runs
        latencies: List[float] = []
        process = psutil.Process(os.getpid()) if psutil else None
        rss_start = (process.memory_info().rss / (1024 * 1024)) if process else 0.0

        for _ in range(self.test_runs):
            t0 = time.perf_counter()
            pred = adapter.predict(test_frame)
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            latencies.append(elapsed_ms)

        rss_end = (process.memory_info().rss / (1024 * 1024)) if process else 0.0
        peak_rss = max(rss_start, rss_end)

        lat_mean = float(np.mean(latencies))
        lat_median = float(np.median(latencies))
        lat_p95 = float(np.percentile(latencies, 95))
        lat_min = float(np.min(latencies))
        lat_max = float(np.max(latencies))
        fps = round(1000.0 / lat_mean, 2) if lat_mean > 0 else 0.0

        import platform
        uname = f"{platform.system()} {platform.machine()}"

        return BenchmarkResult(
            model_id=adapter.model_id,
            artifact_path=getattr(adapter, "artifact_path", "") or "",
            iterations=self.test_runs,
            load_time_sec=0.0,
            latency_mean_ms=round(lat_mean, 2),
            latency_median_ms=round(lat_median, 2),
            latency_p95_ms=round(lat_p95, 2),
            latency_min_ms=round(lat_min, 2),
            latency_max_ms=round(lat_max, 2),
            throughput_fps=fps,
            peak_rss_mb=round(peak_rss, 2),
            platform=uname,
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        )


def main():
    parser = argparse.ArgumentParser(description="AWARESPAN Model Benchmark")
    parser.add_argument("--model-path", default="shared/models/yolov8n_best_weapon.pt")
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--runs", type=int, default=10)
    args = parser.parse_args()

    t0 = time.perf_counter()
    adapter = YOLOv8Adapter(model_id="benchmark-model")
    loaded = adapter.load(args.model_path, config={"imgsz": args.imgsz})
    load_time = time.perf_counter() - t0

    if not loaded:
        print("Failed to load model from:", args.model_path)
        return

    runner = ModelBenchmarkRunner(warmup_runs=2, test_runs=args.runs)
    res = runner.benchmark_visual_adapter(adapter, input_resolution=(args.imgsz, args.imgsz))
    res.load_time_sec = round(load_time, 3)

    print("\n" + "=" * 50)
    print(f" Benchmark Result for {args.model_path}")
    print("=" * 50)
    print(json.dumps(res.to_dict(), indent=2))
    print("=" * 50)


if __name__ == "__main__":
    main()
