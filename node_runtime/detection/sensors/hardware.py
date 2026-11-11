"""
AWARESPAN — Hardware Sensor Interface
Reads GPIO, I2C, SPI, and motion/tamper sensor state.

Project: AWARESPAN
Tagline: Awareness Without Boundaries.
Official problem statement: An AI-Powered Safety Device.
Contact: awarespan@bchbenjamin.in
"""

from dataclasses import dataclass
from typing import Dict, Optional

from shared.logging.logger import get_logger

log = get_logger("node_runtime.hardware_sensors")


@dataclass
class SensorReading:
    pir_motion: bool
    tamper_active: bool
    lux: Optional[float]
    extra: Dict[str, str]


class HardwareSensorInterface:
    """Interface to physical or mock edge sensors on Raspberry Pi."""

    def __init__(self):
        self._gpio_available = False
        log.info("Hardware sensor interface initialized (mock / passive mode)")

    def read(self) -> SensorReading:
        """Poll current sensor state."""
        return SensorReading(
            pir_motion=False,
            tamper_active=False,
            lux=None,
            extra={},
        )
