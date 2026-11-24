# 🆘 Codar Hub: Professional Disaster Recovery Guide

This guide provides step-by-step instructions to restore your system from the automated backups located on your USB drive (`/mnt/usb1/codar_backups/`).

---

## 📂 Scenario A: Restoring Only the Database
Use this if the Raspberry Pi is running correctly, but your sensor data is corrupted or accidentally deleted.

1. **Stop the live service** to prevent data conflicts:
   ```bash
   sudo systemctl stop flask_api.service
   ```

2. **Copy the backup** over the live database:
   ```bash
   # Replace YYYYMMDD_HHMMSS with your chosen backup timestamp
   sudo cp /mnt/usb1/codar_backups/sensors_backup_YYYYMMDD_HHMMSS.db /home/codar/python_web_app/sensors.db
   ```

3. **Fix Ownership:** Ensure the `codar` user can read/write to the restored file:
   ```bash
   sudo chown codar:codar /home/codar/python_web_app/sensors.db
   ```

4. **Restart the service:**
   ```bash
   sudo systemctl start flask_api.service
   ```

---

## 🖥️ Scenario B: Full System Recovery (New Hardware/SD Card)
Use this if you have a fresh OS installation and need to restore your entire Codar Hub environment, including Nginx, Systemd, and both Python projects.

### 1. Extract the Master Backup
Plug in your USB drive (ensure it is mounted at `/mnt/usb1/`) and run:
```bash
# This restores /home/codar, /var/www/html, and all system /etc/ configs
sudo tar -xzvf /mnt/usb1/codar_backups/codar_master_backup_YYYYMMDD_HHMMSS.tar.gz -C / --overwrite
```

### 2. Reload System Services
Tell the OS to recognize the restored Nginx and Systemd configurations:
```bash
sudo systemctl daemon-reload
sudo systemctl restart nginx
sudo systemctl enable flask_api.service
sudo systemctl start flask_api.service
```

### 3. Rebuild Python Virtual Environments
Because virtual environments contain hardcoded paths, it is best practice to refresh them using your "shopping list" files:

**Web App Environment:**
```bash
cd /home/codar/python_web_app
rm -rf venv/  # Remove the old one if it exists
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
deactivate
```

**Gmail API Environment:**
```bash
cd /home/codar/gmail_test
rm -rf env/  # Remove the old one if it exists
python3 -m venv env
source env/bin/activate
pip install -r requirements_gmail.txt
deactivate
```

---

## 🔍 Verification & Health Check
After restoration, verify that the system is healthy:

* **Check the Web App Log:** `sudo journalctl -u flask_api.service -f`
* **Check Disk Space:** `df -h`
* **Check the Backup Log:** `cat /home/codar/python_web_app/backup_log.txt`
