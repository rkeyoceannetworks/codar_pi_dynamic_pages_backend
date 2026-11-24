#!/bin/bash

# --- 0. PARSE ARGUMENTS ---
FORCE_MASTER=0
if [[ "$1" == "force" || "$1" == "-f" || "$1" == "--force" ]]; then
    FORCE_MASTER=1
fi

echo "--- Backup Started: $(date) ---"
if [ "$FORCE_MASTER" -eq 1 ]; then
    echo "--- MANUAL FORCE FLAG DETECTED ---"
fi

# --- 1. SETUP PATHS ---
DB_PATH="/home/codar/python_web_app/sensors.db"
LOCAL_DIR="/home/codar/python_web_app/backups"
USB_DIR="/mnt/usb1/codar_backups"

LOCAL_ARCHIVE="$LOCAL_DIR/archive"
USB_ARCHIVE="$USB_DIR/archive"

TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
DAY_OF_WEEK=$(date +%u)  # 1 = Monday, ..., 7 = Sunday

# Ensure all directory structures exist
mkdir -p "$LOCAL_ARCHIVE" "$USB_ARCHIVE"


# --- 1.1 MOUNT & DISK SPACE HEALTH CHECK ---
# Prevent writing to the internal SD card if the USB is unplugged
if ! mountpoint -q /mnt/usb1; then
    echo "🚨 CRITICAL ERROR: USB is not mounted at /mnt/usb1! Aborting backup."
    exit 1
fi

# Check disk space early to prevent corrupting archives mid-write
USB_FREE=$(df /mnt/usb1 --output=pcent | tail -1 | tr -dc '0-9')
if [ -n "$USB_FREE" ] && [ "$USB_FREE" -gt 95 ]; then
    echo "🚨 CRITICAL ERROR: USB Drive is dangerously full ($USB_FREE%)! Aborting."
    exit 1
elif [ -n "$USB_FREE" ] && [ "$USB_FREE" -gt 85 ]; then
    echo "⚠️ WARNING: USB Drive is getting full ($USB_FREE%)."
fi


# --- 1.5 AUTO-UPDATE REQUIREMENTS (Safe Version) ---
# Writes to a temp file first. If pip crashes, it won't blank out your real file.
/home/codar/python_web_app/venv/bin/pip freeze > /tmp/req_app.txt 2>/dev/null
if [ -s /tmp/req_app.txt ]; then 
    mv /tmp/req_app.txt /home/codar/python_web_app/requirements.txt
fi

/home/codar/gmail_test/env/bin/pip freeze > /tmp/req_gmail.txt 2>/dev/null
if [ -s /tmp/req_gmail.txt ]; then 
    mv /tmp/req_gmail.txt /home/codar/gmail_test/requirements_gmail.txt
fi


# --- 2. DATABASE BACKUP (DAILY) ---
# Move yesterday's files to archive to keep the top-level clean
mv "$LOCAL_DIR"/*.db "$LOCAL_ARCHIVE/" 2>/dev/null
mv "$USB_DIR"/*.db "$USB_ARCHIVE/" 2>/dev/null

if [ -f "$DB_PATH" ]; then
    DB_FILENAME="sensors_backup_${TIMESTAMP}.db"
    
    # Use SQLite's safe .backup command
    sqlite3 "$DB_PATH" ".backup '$LOCAL_DIR/$DB_FILENAME'"
    
    if [ $? -eq 0 ]; then
        cp "$LOCAL_DIR/$DB_FILENAME" "$USB_DIR/$DB_FILENAME"
        
        echo "Backup copied. Cooling down I/O for 3 seconds..."
        sleep 3

        # 2c. AUTO-VERIFY
        echo "Verifying backup integrity on USB..."
        CHECK_RESULT=$(sqlite3 "$USB_DIR/$DB_FILENAME" "PRAGMA integrity_check;")

        if [ "$CHECK_RESULT" == "ok" ]; then
            echo "SUCCESS: Database safely backed up and VERIFIED (Integrity OK)."
        else
            echo "🚨 CRITICAL ERROR: Backup created but INTEGRITY CHECK FAILED!"
            echo "Result: $CHECK_RESULT"
            mv "$USB_DIR/$DB_FILENAME" "$USB_DIR/${DB_FILENAME}.CORRUPT"
        fi

    else
        echo "ERROR: SQLite failed to generate a safe backup snapshot!"
    fi
else
    echo "ERROR: Database not found at $DB_PATH!"
fi


# --- 3. MASTER SYSTEM BACKUP (WEEKLY OR FORCED) ---
if [ "$DAY_OF_WEEK" -eq 7 ] || [ "$FORCE_MASTER" -eq 1 ]; then
    
    if [ "$FORCE_MASTER" -eq 1 ]; then
        echo "Forced run: Triggering Master System Backup..."
    else
        echo "Sunday detected: Running weekly Master System Backup..."
    fi
    
    mv "$USB_DIR"/*.tar.gz "$USB_ARCHIVE/" 2>/dev/null
    SYS_FILENAME="codar_master_backup_${TIMESTAMP}.tar.gz"

    # Expanded tar command to capture all system-wide cron and service configs
    tar -czf "$USB_DIR/$SYS_FILENAME" \
      --exclude="$LOCAL_DIR" \
      --exclude="*.db" \
      --exclude="*.db-wal" \
      --exclude="*.db-shm" \
      --exclude="backup_log.txt" \
      --exclude="*/.cache" \
      --exclude="*/discovery_cache" \
      --exclude="/home/codar/.rustup" \
      --exclude="/home/codar/.cargo/registry" \
      --exclude="*/__pycache__" \
      --exclude="*.pyc" \
      /home/codar \
      /var/www/html \
      /etc/systemd/system \
      /etc/default \
      /etc/nginx \
      /etc/fstab \
      /var/spool/cron/crontabs \
      /etc/cron.d \
      /etc/cron.daily \
      /etc/cron.hourly \
      /etc/cron.monthly \
      /etc/cron.weekly \
      /etc/crontab \
      /etc/ssh

    if [ $? -eq 0 ] || [ $? -eq 1 ]; then
        echo "SUCCESS: Master system backed up."
    else
        echo "ERROR: Master system backup failed!"
    fi
else
    echo "INFO: Skipping Master System Backup (only runs on Sundays or with 'force' flag)."
fi


# --- 4. AUTO-CLEANUP ---
# Local SD: Keep 7 days
find "$LOCAL_DIR" -type f -name "*.db" -mtime +7 -exec rm {} \;

# USB: Keep 30 days (This recursively cleans the /archive folder too, which is intentional to save space)
find "$USB_DIR" -type f -name "*.db" -mtime +30 -exec rm {} \;
find "$USB_DIR" -type f -name "codar_master_backup_*.tar.gz" -mtime +30 -exec rm {} \;

echo "SUCCESS: Cleanup complete."
echo "-----------------------------------"
