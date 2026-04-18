"""
Solar Tracker - Data Collector
Reads INA219 sensor every 30 seconds, writes to SQLite, updates OLED display.
Runs continuously on Raspberry Pi 3.
"""

import time
import sqlite3
import logging
from datetime import datetime, timedelta
from pathlib import Path

# INA219 and OLED libraries (install via pip on the Pi)
try:
    from ina219 import INA219, DeviceRangeError
    from luma.core.interface.serial import i2c
    from luma.oled.device import ssd1306
    from luma.core.render import canvas
    from PIL import ImageFont
    INA_AVAILABLE = True
except ImportError:
    INA_AVAILABLE = False
    logging.warning("Hardware libraries not found — running in simulation mode.")

# ── Configuration ──────────────────────────────────────────────────────────────
DB_PATH        = Path(__file__).parent / "solar.db"
SHUNT_OHMS     = 0.1          # INA219 shunt resistor value
MAX_EXPECTED_A = 0.4          # INA219 max expected amps (adjust if needed)
SUNLIGHT_THRESHOLD_V = 1.0    # Voltage above this counts as sunlight
POLL_INTERVAL  = 30           # Seconds between readings
OLED_ADDRESS   = 0x3C         # Common SSD1306 I2C address
INA_ADDRESS    = 0x40         # Default INA219 I2C address
MAX_DAYS       = 7            # Days of data to retain
# ───────────────────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(Path(__file__).parent / "collector.log"),
    ],
)
log = logging.getLogger(__name__)


# ── Database ───────────────────────────────────────────────────────────────────

def init_db():
    """Create the readings table if it doesn't exist."""
    with sqlite3.connect(DB_PATH) as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS readings (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp   TEXT    NOT NULL,
                voltage_v   REAL    NOT NULL,
                current_ma  REAL    NOT NULL,
                power_mw    REAL    NOT NULL
            )
        """)
        con.commit()
    log.info("Database initialised at %s", DB_PATH)


def insert_reading(timestamp: str, voltage_v: float, current_ma: float, power_mw: float):
    with sqlite3.connect(DB_PATH) as con:
        con.execute(
            "INSERT INTO readings (timestamp, voltage_v, current_ma, power_mw) VALUES (?,?,?,?)",
            (timestamp, voltage_v, current_ma, power_mw),
        )
        con.commit()


def purge_old_days():
    """
    Remove all readings that belong to a date older than MAX_DAYS.
    Called once at midnight — removes the oldest day completely.
    """
    cutoff = (datetime.now() - timedelta(days=MAX_DAYS)).strftime("%Y-%m-%d")
    with sqlite3.connect(DB_PATH) as con:
        deleted = con.execute(
            "DELETE FROM readings WHERE date(timestamp) < ?", (cutoff,)
        ).rowcount
        con.commit()
    log.info("Midnight purge: removed %d rows older than %s", deleted, cutoff)


# ── Hardware helpers ───────────────────────────────────────────────────────────

def setup_ina219():
    if not INA_AVAILABLE:
        return None
    sensor = INA219(SHUNT_OHMS, MAX_EXPECTED_A, address=INA_ADDRESS, busnum=1)
    sensor.configure(sensor.RANGE_16V)
    log.info("INA219 configured (shunt=%.2f Ω)", SHUNT_OHMS)
    return sensor


def read_sensor(sensor) -> tuple[float, float, float]:
    """Return (voltage_v, current_ma, power_mw). Simulates if no hardware."""
    if sensor is None:
        # Simulation: sine-wave-ish values so you can test the dashboard
        import math
        t = time.time()
        v = max(0.0, 3.5 * abs(math.sin(t / 600)) + 0.2)
        c = v / SHUNT_OHMS * 10          # rough simulation
        p = v * c
        return round(v, 4), round(c, 4), round(p, 4)
    try:
        v = sensor.voltage()
        c = sensor.current()          # already in mA with this library
        p = sensor.power()            # already in mW
        return round(v, 4), round(c, 4), round(p, 4)
    except DeviceRangeError:
        log.warning("INA219 DeviceRangeError — returning zeros")
        return 0.0, 0.0, 0.0


def setup_oled():
    if not INA_AVAILABLE:
        return None
    serial = i2c(port=1, address=OLED_ADDRESS)
    device = ssd1306(serial)
    log.info("OLED display ready")
    return device


def update_oled(device, timestamp: str, sun_seconds: int):
    """Render two lines on the 128×64 OLED."""
    if device is None:
        return
    hours, rem = divmod(sun_seconds, 3600)
    minutes, seconds = divmod(rem, 60)
    sun_str = f"{hours:02d}h {minutes:02d}m {seconds:02d}s"
    # Trim timestamp to HH:MM:SS for display width
    ts_short = timestamp[11:19] if len(timestamp) >= 19 else timestamp

    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 14)
        small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 11)
    except Exception:
        font = ImageFont.load_default()
        small = font

    with canvas(device) as draw:
        draw.text((0,  0), "Solar Tracker",    font=font,  fill="white")
        draw.text((0, 18), f"Last: {ts_short}", font=small, fill="white")
        draw.text((0, 32), "Sun time:",         font=small, fill="white")
        draw.text((0, 46), sun_str,             font=font,  fill="white")


# ── Midnight purge scheduler ───────────────────────────────────────────────────

class MidnightPurge:
    def __init__(self):
        self._last_date = datetime.now().date()

    def check(self):
        today = datetime.now().date()
        if today != self._last_date:
            purge_old_days()
            self._last_date = today


# ── Main loop ─────────────────────────────────────────────────────────────────

def main():
    log.info("=== Solar Tracker starting ===")
    init_db()

    sensor = setup_ina219()
    oled   = setup_oled()
    purge  = MidnightPurge()

    # sun_seconds accumulates within the current calendar day
    sun_seconds = 0
    current_day = datetime.now().date()

    log.info("Polling every %d seconds. Sunlight threshold: %.1f V", POLL_INTERVAL, SUNLIGHT_THRESHOLD_V)

    while True:
        now = datetime.now()

        # Reset daily sun counter at midnight
        if now.date() != current_day:
            log.info("New day — resetting sun counter")
            sun_seconds = 0
            current_day = now.date()

        purge.check()

        voltage_v, current_ma, power_mw = read_sensor(sensor)
        ts = now.strftime("%Y-%m-%d %H:%M:%S")

        if voltage_v >= SUNLIGHT_THRESHOLD_V:
            sun_seconds += POLL_INTERVAL
            log.info("☀  %s | %.3f V | %.2f mA | %.2f mW | sun=%ds",
                     ts, voltage_v, current_ma, power_mw, sun_seconds)
        else:
            log.info("🌑 %s | %.3f V | %.2f mA | %.2f mW (below threshold)",
                     ts, voltage_v, current_ma, power_mw)

        insert_reading(ts, voltage_v, current_ma, power_mw)
        update_oled(oled, ts, sun_seconds)

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log.info("Collector stopped by user.")
