# Codar Hub: Pi Zero Sensor & Control Dashboard

*Last Updated: March 22, 2026 by Codar*

A high-performance, Flask-based web dashboard and background logging system designed for the Raspberry Pi Zero. This project monitors local hardware sensors, the Pi's internal system health, and scrapes massive datasets from a remote EMI-300 Pro industrial controller, serving it all up on a dark-mode frontend with dynamic down-sampling.

---

## 🚀 Features

* **Continuous Data Logging:** A highly optimized `systemd` background service (`sensor_logger.service`) sleeps in RAM and records 27 distinct data points based on a configurable polling interval.
* **Automated Daily Backups:** A scheduled Cron job safely duplicates the SQLite database every night at 2:00 AM, automatically purging backups older than 7 days to conserve SD card space.
* **Dynamic Resolution Filtering:** Uses on-the-fly SQLite math to downsample millions of raw data points into smooth 5-Minute, 1-Hour, or 1-Day averages instantly.
* **Advanced Charting:** Features a Dual-Axis Comparison Chart to plot any two arbitrary metrics against each other, plus dynamic Min/Max/Avg/Cur stat badges that automatically recalculate as you zoom.
* **Live Digital IO Grid:** Real-time visual status badges for all EMI-300 Relays, Alarms, and GPIOs.
* **Instant CSV Export:** Context-aware data exporting based on the currently selected time window and resolution.
* **Local Relay Control:** Direct trigger control of local Pi GPIO pins (Pins 17 & 27) via the web interface.

---

## 🛠 Hardware Supported

1. **Raspberry Pi Zero W** (Host & Controller)
2. **DS18B20** (1-Wire Temperature Probes)
3. **SHT35** (I2C Temperature & Humidity Sensor)
4. **EMI-300 Pro** (Remote Network Controller)

---

## 📂 System Architecture

The project is split into three main backend services, a static frontend, and an automated backup loop:

### Core Files
* `/home/codar/python_web_app/log_sensors.py`
  * **Role:** The data collector. Runs continuously as a background service (`sensor_logger.service`).
* `/home/codar/python_web_app/app.py`
  * **Role:** The Flask API. Runs continuously via `systemd` (`flask_api.service`).
* `/home/codar/python_web_app/backup_db.sh`
  * **Role:** The data vault. Runs daily via Cron to safely clone `sensors.db` to the `/backups` folder.
* `/var/www/html/index.html`
  * **Role:** The UI. Served via Nginx.
* `/var/www/html/docs/`
  * **Role:** The Documentation Hub (Docsify).

---

## ⚙️ Installation & Setup

### 1. Python Dependencies
Ensure your virtual environment (`venv`) is active, then install the required packages:

```bash
pip install flask psutil smbus2 requests gpiozero
```

### 2. Configuration (`config.json`)
The logger script uses a master configuration file. You can toggle hardware polling, set API credentials, and control the timing/database settings globally.

```json
{
    "logging_enabled": {
        "ds18b20": true, 
        "sht35": true, 
        "system_stats": true, 
        "emi300": true
    },
    "emi300_settings": {
        "ip_address": "192.168.1.174", 
        "username": "admin", 
        "password": "your_password"
    },
    "system_settings": {
        "db_filename": "sensors.db",
        "polling_interval_sec": 60,
        "cpu_measure_window_sec": 1.0
    }
}
```

### 3. Background Services
This project relies on two `systemd` services to ensure it survives reboots and runs efficiently without pegging the single-core CPU.
* **`sensor_logger.service`**: Executes the infinite loop in `log_sensors.py`.
* **`flask_api.service`**: Runs the Gunicorn/Waitress WSGI server for `app.py`.

**Quick Reload Script:**
If you make changes to `config.json`, run the included bash script to apply them instantly:
```bash
./restart_logger.sh
```

### 4. Automated Database Backups
To prevent data loss from SD card corruption, a Cron job runs daily at 2:00 AM to safely back up the SQLite database using the built-in `.backup` command.
To edit the backup schedule, run `crontab -e` and modify this line:
```text
0 2 * * * /home/codar/python_web_app/backup_db.sh >> /home/codar/python_web_app/backups/backup_log.txt 2>&1
```

---

## 📡 API Endpoints

### `/data`
Fetches historical sensor data.
* **Params:** * `start` (YYYY-MM-DD HH:MM:SS)
  * `end` (YYYY-MM-DD HH:MM:SS)
  * `res` (raw, 5min, hourly, daily, custom)
  * `custom_minutes` (integer, used if res=custom)

### `/relay/<id>/<action>`
Triggers local Pi relays.
* **id:** `1` or `2`
* **action:** `on` or `off`

---

## 📚 Documentation
Extended documentation is hosted via **Docsify** locally on the Pi. 
Navigate to `http://<PI_IP>/docs/` to view the full wiki, API examples, and wiring diagrams.
