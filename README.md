# final_project_ece3824

A Raspberry Pi 3 based solar tracking system that measures how long the sun is out each day using a mini solar panel and INA219 current sensor. Readings are taken every 30 seconds, stored in a cloud PostgreSQL database (Supabase), and displayed on a live web dashboard built with Flask and Plotly.

---

## Hardware

| Component | Purpose | Notes |
|-----------|---------|-------|
| Raspberry Pi 3 | Main compute unit | Requires stable power and internet |
| INA219 Current Sensor | Measures voltage, current, power | Shunt: 0.1Ω — I2C address 0x40 |
| SSD1306 OLED Display | Shows last timestamp and daily sun time | 128×64px — I2C address 0x3C |
| Mini Solar Panel (5V 200mA) | Light source / energy input | Sensitive enough for accurate sunlight detection |
| Breadboard + Jumper Cables | Connects components | Standard breadboard wiring |

## Software Stack

| Layer | Technology | Role |
|-------|-----------|------|
| Data Collection | Python + pi-ina219 | Reads sensor every 30 seconds on the Pi |
| Database | Supabase (PostgreSQL) | Cloud-hosted, stores all readings |
| Web Server | Flask + Gunicorn | Serves the dashboard and JSON API |
| Charts | Plotly.js | Interactive voltage timeline and sun-hours bar chart |
| Deployment | Railway / Render | Hosts the Flask app publicly |
| Version Control | Git + GitHub | Syncs code between Pi and cloud |

---

## How It Works

Three independent components communicate only through the shared database:

- **Raspberry Pi** runs `collector.py`, reads the INA219 every 30 seconds, and writes each reading to Supabase over the internet
- **Supabase (PostgreSQL)** is the central data store — both the Pi and the web server connect to it independently
- **Flask web server** (hosted on Railway/Render) reads from Supabase and serves the dashboard — the browser polls `/data` every 30 seconds for live updates

Any voltage reading at or above **1.0V** counts as active sunlight. Each such reading adds 30 seconds to the daily sun counter. Seven days of data are retained at any time — at midnight the oldest day is purged automatically. If the Pi loses power the experiment must be restarted manually.

---

## Wiring

Both the INA219 and OLED share the same I2C bus — wire them in parallel to the same GPIO pins.

### INA219 → Raspberry Pi

| INA219 Pin | Pi GPIO | Pi Physical Pin |
|-----------|---------|----------------|
| VCC | 3.3V | Pin 1 |
| GND | GND | Pin 6 |
| SDA | GPIO 2 (SDA) | Pin 3 |
| SCL | GPIO 3 (SCL) | Pin 5 |

**Solar panel:** Positive lead → INA219 VIN+, INA219 VIN- → load or GND.

### SSD1306 OLED → Raspberry Pi

| OLED Pin | Pi GPIO | Pi Physical Pin |
|---------|---------|----------------|
| VCC | 3.3V | Pin 1 |
| GND | GND | Pin 9 |
| SDA | GPIO 2 (SDA) | Pin 3 |
| SCL | GPIO 3 (SCL) | Pin 5 |

### Enable I2C

```bash
sudo raspi-config
# Interface Options → I2C → Enable → Finish
sudo reboot

# Verify both devices are detected
sudo i2cdetect -y 1
# Should show 0x3C (OLED) and 0x40 (INA219)
```

---

## Setup

### 1. Supabase Database

1. Go to [supabase.com](https://supabase.com) and create a free account
2. Create a new project and set a database password
3. Go to **Project Settings → Database → Connection String → URI**
4. Copy the connection string — replace `[YOUR-PASSWORD]` with your actual password:
   ```
   postgresql://postgres:yourpassword@db.xxxx.supabase.co:5432/postgres
   ```

The `readings` table is created automatically the first time `collector.py` runs.

### 2. Raspberry Pi

```bash
# Enable I2C first (see Wiring section above)

# Install dependencies
sudo apt update && sudo apt install -y python3-pip i2c-tools git
pip install -r requirements.txt --break-system-packages

# Set up SSH key for GitHub
ssh-keygen -t ed25519 -C "your@email.com"
cat ~/.ssh/id_ed25519.pub   # copy this to GitHub → Settings → SSH Keys
ssh -T git@github.com       # test connection

# Clone the repo
git clone git@github.com:yourname/your-repo-name.git
cd your-repo-name

# Create the environment file
nano .env
# Add this line:
# DATABASE_URL=postgresql://postgres:yourpassword@db.xxxx.supabase.co:5432/postgres

# Test the database connection
python3 -c "import psycopg2; psycopg2.connect('your-database-url'); print('Connected!')"
```

### 3. Run the Collector

```bash
python collector.py
```

**Auto-start on boot** — save as `/etc/systemd/system/solar-collector.service`:

```ini
[Unit]
Description=Solar Tracker Collector
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/your-repo-name
EnvironmentFile=/home/pi/your-repo-name/.env
ExecStart=/usr/bin/python3 /home/pi/your-repo-name/collector.py
Restart=on-failure
RestartSec=30

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now solar-collector
sudo systemctl status solar-collector
```

### 4. Deploy to Railway

1. Push code to GitHub (see Git section below first)
2. Go to [railway.app](https://railway.app) → sign in with GitHub
3. New Project → Deploy from GitHub repo → select your repo
4. Railway detects the `Procfile` and runs `gunicorn app:app` automatically
5. Go to your service → **Variables** tab → add `DATABASE_URL`
6. Railway gives you a public HTTPS URL — that's your live dashboard

---

## Environment Variables

Create a `.env` file in the project root (never commit this):

```
DATABASE_URL=postgresql://postgres:yourpassword@db.xxxx.supabase.co:5432/postgres
```

On Railway/Render, set this as an environment variable in the dashboard instead.

---

## Database Schema

Single table — created automatically on first run:

| Column | Type | Description |
|--------|------|-------------|
| id | SERIAL PRIMARY KEY | Auto-incrementing ID |
| timestamp | TIMESTAMPTZ | When the reading was taken (UTC) |
| voltage_v | REAL | Voltage in volts |
| current_ma | REAL | Current in milliamps |
| power_mw | REAL | Power in milliwatts |

---

## Configuration

All tunable constants are at the top of `collector.py`:

| Constant | Default | Description |
|---------|---------|-------------|
| `SUNLIGHT_THRESHOLD_V` | `1.0` | Minimum voltage counted as sunlight |
| `POLL_INTERVAL` | `30` | Seconds between readings |
| `MAX_DAYS` | `7` | Days of data retained |
| `SHUNT_OHMS` | `0.1` | INA219 shunt resistor value |
| `OLED_ADDRESS` | `0x3C` | I2C address of OLED |
| `INA_ADDRESS` | `0x40` | I2C address of INA219 |

---

## Git Workflow

```bash
# Before your first push — make sure .gitignore is correct
cat .gitignore
# Should contain: .env, .env~, *.log, __pycache__/, solar.db

# Remove .env if it was accidentally tracked
git rm --cached .env
git rm --cached .env~

# Verify .env does not appear, then push
git status
git add .
git commit -m "initial commit"
git push
```

**Ongoing changes:**

```bash
git add .
git commit -m "describe what changed"
git push   # Railway redeploys automatically
```

---

## Network Notes

Campus Wi-Fi often blocks the Pi due to MAC address registration or captive portals. The most reliable option is a **phone hotspot**. If the hotspot has internet but Supabase still fails, your carrier may be blocking port 5432. Test with:

```bash
nc -zv db.yourref.supabase.co 5432   # primary port
nc -zv db.yourref.supabase.co 6543   # pooler port (try this if 5432 fails)
```

If both are blocked, use the connection pooler URL from Supabase (port 6543) or switch to a home Wi-Fi router which has no port restrictions.

---

## Troubleshooting

| Error | Cause | Fix |
|-------|-------|-----|
| `Could not determine default I2C bus` | I2C library can't auto-detect platform | Pass `busnum=1` explicitly: `INA219(..., busnum=1)` |
| `Network is unreachable` (psql/nc) | Carrier blocking port 5432/6543 | Try port 6543 pooler URL, or switch to home Wi-Fi |
| Default keyring prompt on Wi-Fi | OS keychain asking for master password | Leave blank and press Enter, or edit `wpa_supplicant.conf` directly |
| `.env` appearing in `git status` | File already tracked before `.gitignore` was added | Run `git rm --cached .env` |
| `Connection refused` on dashboard | Gunicorn bound to `127.0.0.1` not `0.0.0.0` | Restart with `gunicorn -b 0.0.0.0:8000 app:app` |
| Campus Wi-Fi refuses Pi connection | MAC not registered on university network | Use phone hotspot or contact IT to whitelist Pi MAC address |

---

## Design Notes

- **Power loss** resets the experiment. The Pi has no RTC battery so timestamps depend on NTP sync after reboot. An optional DS3231 RTC module can fix this.
- **Sun time accuracy** is bounded by the 30-second poll interval — maximum error is ±30 seconds per reading.
- **INA219 shunt** of 0.1Ω is handled internally by the `pi-ina219` library, which returns current in mA directly.
- **Supabase free tier** allows 500MB storage — sufficient for ~2,880 readings per week at 30-second intervals.
- The `.env` file must be created manually on each new device since it is excluded from Git.