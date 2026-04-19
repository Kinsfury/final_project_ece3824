"""
Solar Tracker - Data Collector (Cloud Edition)
Reads INA219 sensor every 30 seconds, writes to Supabase PostgreSQL, updates OLED.
 
Environment variables required (.env file or systemd EnvironmentFile):
DATABASE_URL — PostgreSQL connection string from Supabase
e.g. postgresql://postgres:<password>@db.<ref>.supabase.co:5432/postgres
"""
 
import os
import time
import logging
from datetime import datetime, timedelta
from pathlib import Path
 
import psycopg2
from dotenv import load_dotenv
 
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
 
# ── Load .env ──────────────────────────────────────────────────────────────────
load_dotenv(Path(__file__).parent / ".env")
 
# ── Configuration ──────────────────────────────────────────────────────────────
DATABASE_URL = os.environ["DATABASE_URL"] # crashes loudly if missing
SHUNT_OHMS = 0.1
MAX_EXPECTED_A = 0.4
SUNLIGHT_THRESHOLD_V = 1.0
POLL_INTERVAL = 30
OLED_ADDRESS = 0x3C
INA_ADDRESS = 0x40
MAX_DAYS = 7
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
 
def get_conn():
    return psycopg2.connect(DATABASE_URL, connect_timeout=10)
 
 
def init_db():
    with get_conn() as con:
        with con.cursor() as cur:
            cur.execute("""
            CREATE TABLE IF NOT EXISTS readings (
            id SERIAL PRIMARY KEY,
            timestamp TIMESTAMPTZ NOT NULL,
            voltage_v REAL NOT NULL,
            current_ma REAL NOT NULL,
            power_mw REAL NOT NULL
            )
            """)
            cur.execute("""
            CREATE INDEX IF NOT EXISTS readings_timestamp_idx
            ON readings (timestamp DESC)
            """)
        con.commit()
    log.info("Database initialised (PostgreSQL/Supabase)")
 
 
def insert_reading(timestamp, voltage_v, current_ma, power_mw):
    sql = "INSERT INTO readings (timestamp, voltage_v, current_ma, power_mw) VALUES (%s,%s,%s,%s)"
    for attempt in range(2):
        try:
            with get_conn() as con:
                with con.cursor() as cur:
                    cur.execute(sql, (timestamp, voltage_v, current_ma, power_mw))
                con.commit()
            return
        except psycopg2.OperationalError as e:
            log.warning("DB insert attempt %d failed: %s", attempt + 1, e)
            time.sleep(5)
    log.error("Could not insert reading after retries — dropping data point.")
 
 
def purge_old_days():
    cutoff = (datetime.now() - timedelta(days=MAX_DAYS)).strftime("%Y-%m-%d")
    try:
        with get_conn() as con:
            with con.cursor() as cur:
                cur.execute("DELETE FROM readings WHERE timestamp::date < %s", (cutoff,))
                deleted = cur.rowcount
            con.commit()
        log.info("Midnight purge: removed %d rows older than %s", deleted, cutoff)
    except psycopg2.OperationalError as e:
        log.error("Purge failed: %s", e)
 
 
# ── Hardware helpers ───────────────────────────────────────────────────────────
 
def setup_ina219():
    if not INA_AVAILABLE:
        return None
    sensor = INA219(SHUNT_OHMS, MAX_EXPECTED_A, address=INA_ADDRESS, busnum=1)
    sensor.configure(sensor.RANGE_16V)
    log.info("INA219 configured (shunt=%.2f ohms)", SHUNT_OHMS)
    return sensor
 
 
def read_sensor(sensor):
    if sensor is None:
        import math
        t = time.time()
        v = max(0.0, 3.5 * abs(math.sin(t / 600)) + 0.2)
        c = v / SHUNT_OHMS * 10
        p = v * c
        return round(v, 4), round(c, 4), round(p, 4)
    try:
        return round(sensor.voltage(), 4), round(sensor.current(), 4), round(sensor.power(), 4)
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
 
 
def update_oled(device, timestamp, sun_seconds):
    if device is None:
        return
    hours, rem = divmod(sun_seconds, 3600)
    minutes, seconds = divmod(rem, 60)
    sun_str = f"{hours:02d}h {minutes:02d}m {seconds:02d}s"
    ts_short = timestamp[11:19] if len(timestamp) >= 19 else timestamp
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 14)
        small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 11)
    except Exception:
        font = small = ImageFont.load_default()
    with canvas(device) as draw:
        draw.text((0, 0), "Solar Tracker", font=font, fill="white")
        draw.text((0, 18), f"Last: {ts_short}", font=small, fill="white")
        draw.text((0, 32), "Sun time:", font=small, fill="white")
        draw.text((0, 46), sun_str, font=font, fill="white")
 
 
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
    log.info("=== Solar Tracker (cloud) starting ===")
    init_db()
    sensor = setup_ina219()
    oled = setup_oled()
    purge = MidnightPurge()
    sun_seconds = 0
    current_day = datetime.now().date()
    log.info("Polling every %d s. Sunlight threshold: %.1f V", POLL_INTERVAL, SUNLIGHT_THRESHOLD_V)
 
    while True:
        now = datetime.now()
        if now.date() != current_day:
            log.info("New day — resetting sun counter")
            sun_seconds = 0
            current_day = now.date()
        purge.check()
 
        voltage_v, current_ma, power_mw = read_sensor(sensor)
        ts = now.strftime("%Y-%m-%d %H:%M:%S")
 
        if voltage_v >= SUNLIGHT_THRESHOLD_V:
            sun_seconds += POLL_INTERVAL
            log.info("SUN %s | %.3f V | %.2f mA | %.2f mW | sun=%ds",
                     ts, voltage_v, current_ma, power_mw, sun_seconds)
        else:
            log.info("DARK %s | %.3f V | %.2f mA | %.2f mW",
                     ts, voltage_v, current_ma, power_mw)
 
        insert_reading(ts, voltage_v, current_ma, power_mw)
        update_oled(oled, ts, sun_seconds)
        time.sleep(POLL_INTERVAL)
 
 
if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log.info("Collector stopped by user.")

