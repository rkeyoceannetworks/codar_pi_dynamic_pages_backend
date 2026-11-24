# 💾 Codar Hub: Automated Backup System

This project includes a robust, enterprise-grade backup system designed to protect both your live sensor data (`sensors.db`) and the complete system configuration. It utilizes a hybrid daily/weekly schedule and automatically offloads files to an external USB drive.

## ✨ Features

* **Dual-Location Backups:** Saves simultaneously to the local Pi SD card and an external USB drive (`/mnt/usb1/`).
* **Smart Scheduling:** Backs up the SQLite database **every day**, but only takes a full system snapshot once a week (Sundays) to save USB write-cycles.
* **Auto-Archiving:** Automatically moves older backups into an `archive/` subfolder before generating new ones, keeping the top directory and Web Dashboard perfectly clean.
* **Auto-Cleanup:** Automatically deletes expired backups to prevent storage bloat.
* **Optimized Exclusions:** Strictly excludes wasteful junk directories like `__pycache__`, `.rustup`, `.cargo`, and Google API `discovery_cache`.
* **Web Dashboard Integration:** The latest backups can be downloaded directly from the browser via the **USB Backups** tab.

---

## 📂 Directory Structure

**Backup Script Location:** `/home/codar/python_web_app/backup_db.sh`

**Local SD Card Storage:**
* `/home/codar/python_web_app/backups/` (Latest DB)
* `/home/codar/python_web_app/backups/archive/` (Older DBs)

**External USB Storage:**
* `/mnt/usb1/codar_backups/` (Latest DB & Master System `.tar.gz`)
* `/mnt/usb1/codar_backups/archive/` (Older DBs & Master System files)

---

## 🚀 Usage & Commands

### 1. Manual Run (Daily DB Only)
To run the standard daily backup manually (skips the Master System Backup unless today is Sunday):
```bash
sudo bash /home/codar/python_web_app/backup_db.sh
```

### 2. Forced Master Backup
If you are about to make major changes to the system and want a full snapshot **right now**, pass the `force` flag. This will bypass the Sunday rule and instantly compress the entire `/home/codar`, `/var/www/html`, and `/etc` configurations:
```bash
sudo bash /home/codar/python_web_app/backup_db.sh force
```
*(Acceptable flags: `force`, `-f`, or `--force`)*

---

## ⚙️ Automation (Cron)

The backup script is scheduled to run automatically every night at **2:00 AM**. 

Because it backs up protected system directories (like `/etc/nginx/`), it must be run via the **Root Crontab**. To view or edit the schedule, run:
```bash
sudo crontab -e
```

**Current Cron Entry:**
```bash
0 2 * * * bash /home/codar/python_web_app/backup_db.sh >> /home/codar/python_web_app/backup_log.txt 2>&1
```
*Note: All output and errors are logged to `backup_log.txt` for easy debugging.*

---

## 🧹 Retention Policy

The script includes an automated `find` and `rm` cleanup process at the end of every run. The current retention policy is:

* **Local DB Backups:** 7 Days
* **USB DB Backups:** 30 Days
* **USB Master System Backups:** 30 Days (~4 weekly snapshots)

---

## 🛠️ Restoration Guide

**To restore the database:**
1. Download the latest `.db` file from the Web Dashboard or USB drive.
2. Stop the Flask service: `sudo systemctl stop flask_api.service`
3. Replace the existing `/home/codar/python_web_app/sensors.db` with the backup.
4. Restart the service: `sudo systemctl start flask_api.service`

**To restore the Master System:**
1. Extract the `.tar.gz` file.
2. The archive contains the exact file paths. Copy the contents of the extracted `/home/codar`, `/var/www/html`, and `/etc` folders to their respective locations on the new Raspberry Pi.
