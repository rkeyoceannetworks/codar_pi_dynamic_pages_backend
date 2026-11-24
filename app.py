import os  # to get files and serve them from usb drive
import json
import subprocess
import sqlite3
from datetime import datetime, timedelta  # This is the best way
from flask import Flask, request, jsonify, send_file, send_from_directory


#import datetime
#from flask import send_file
#from flask import Flask, request, jsonify, send_from_directory # to get files and serve them from usb drive
#from flask import send_from_directory # to get files and serve them from usb drive
#from flask import Flask, jsonify, request
#from datetime import datetime, timedelta

app = Flask(__name__)

# --- HARDWARE SETUP ---
relays = {}
RELAY_PINS = {1: 17, 2: 27}

def get_relay(relay_id):
    from gpiozero import OutputDevice 
    if relay_id not in relays:
        relays[relay_id] = OutputDevice(RELAY_PINS[relay_id], active_high=False, initial_value=False)
    return relays[relay_id]

def get_db_connection():
    conn = sqlite3.connect('/home/codar/python_web_app/sensors.db')
    conn.row_factory = sqlite3.Row
    return conn


def get_log_tail(filepath, lines=50):
    """Safely grabs the last N lines of a text file."""
    try:
        # Runs the standard linux 'tail' command
        result = subprocess.run(['/usr/bin/tail', '-n', str(lines), filepath], 
                                capture_output=True, text=True, timeout=2)
        if result.returncode == 0:
            return result.stdout
        else:
            return f"File not found or empty: {filepath}"
    except Exception as e:
        return f"Error reading logs: {e}"
######
# Routes
#####

######
# Email
#####

@app.route('/email/test', methods=['POST'])
def trigger_test_email():
    try:
        # Run the monitor script with the --daily flag to force an email
        # Pointing to the correct script: pi_monitor.py
        cmd = "/home/codar/gmail_test/env/bin/python /home/codar/gmail_test/pi_monitor.py --daily"

        # We use subprocess.run and wait for it to finish so we know if it succeededresult = subprocess.run(cmd, shell=True, capture_output=True, text=True)result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        
        if result.returncode == 0:
            return jsonify({"status": "success", "message": "Health Report dispatched to mailing list!"})
        else:
            return jsonify({"status": "error", "message": f"Failed to send: {result.stderr.strip()}"})
            
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})



##############
# USB 
###########

@app.route('/usb/status', methods=['GET'])
def usb_status():
    # Physically check if the mount point is active
    mounted = os.path.ismount('/mnt/usb1')
    return jsonify({"mounted": mounted})

@app.route('/usb/verify', methods=['POST'])
def verify_integrity():
    try:
        if not os.path.ismount('/mnt/usb1'):
            return jsonify({"status": "error", "message": "USB not mounted."})

        # Find the latest backup file in the vault
        import glob
        backups = glob.glob('/mnt/usb1/codar_backups/*.db')
        if not backups:
            return jsonify({"status": "error", "message": "No backup files found to verify."})
        
        latest_backup = max(backups, key=os.path.getctime)
        filename = os.path.basename(latest_backup)

        # Run SQLite integrity check on the latest file
        cmd = f"/usr/bin/sqlite3 {latest_backup} 'PRAGMA integrity_check;'"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)

        if "ok" in result.stdout.lower():
            return jsonify({"status": "success", "message": f"Integrity Verified: {filename} is healthy!"})
        else:
            return jsonify({"status": "error", "message": f"CORRUPTION DETECTED in {filename}!"})

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})



@app.route('/usb/backup', methods=['POST'])
def trigger_backup():
    try:
        # Run the bash script and append both output and errors to the log file
        cmd = "/usr/bin/sudo /home/codar/python_web_app/backup_db.sh >> /home/codar/python_web_app/backup_log.txt 2>&1"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        
        if result.returncode == 0:
            return jsonify({"status": "success", "message": "Backup completed successfully!"})
        else:
            return jsonify({"status": "error", "message": "Backup encountered an error. Check the System Logs tab."})

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})


@app.route('/usb/eject', methods=['POST'])
def eject_usb():
    try:
        mount_point = '/mnt/usb1'
        
        # 1. Run the umount command
        result = subprocess.run(['/usr/bin/sudo', '/usr/bin/umount', mount_point], capture_output=True, text=True)
        
        # 2. BULLETPROOF CHECK: Is it actually unmounted now?
        import os
        if not os.path.ismount(mount_point):
            return jsonify({"status": "success", "message": "USB drive safely ejected. You may now remove it."})
        else:
            # It's STILL mounted. Let's grab whatever error it threw.
            error_msg = result.stderr.strip() or result.stdout.strip()
            if not error_msg:
                error_msg = "Target is busy (a terminal or script is currently using the drive)."
                
            return jsonify({"status": "error", "message": f"Cannot eject: {error_msg}"})

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})


@app.route('/usb/mount', methods=['POST'])
def mount_usb():
    try:
        import os
        import glob

        # Helper function to check if /mnt/usb1 is ACTUALLY a mount point
        def is_mounted():
            return os.path.ismount('/mnt/usb1')

        # --- STEP 1: TRY THE OFFICIAL WAY ---
        subprocess.run(['/usr/bin/sudo', '/usr/bin/mount', '/mnt/usb1'], capture_output=True)
        
        if is_mounted():
            return jsonify({"status": "success", "message": "Mounted via /etc/fstab (Verified)"})

        # --- STEP 2: FALLBACK TO DYNAMIC HUNTING ---
        usb_partitions = glob.glob('/dev/sd*[1-9]')
        if usb_partitions:
            target_dev = usb_partitions[0]
            # Force a manual mount to the partition we found
            subprocess.run(f"/usr/bin/sudo /usr/bin/mount {target_dev} /mnt/usb1", shell=True, capture_output=True)
            
            if is_mounted():
                return jsonify({"status": "success", "message": f"Mounted {target_dev} (Dynamic Fallback)"})

        # --- STEP 3: IF WE GET HERE, IT FAILED ---
        return jsonify({"status": "error", "message": "Mount failed. No valid drive detected or /etc/fstab entry is invalid."})

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})


########
# Data #
########

@app.route('/data')
def get_sensor_data():
    try:
        start_date = request.args.get('start')
        end_date = request.args.get('end')
        res = request.args.get('res', 'raw')
        custom_mins = request.args.get('custom_minutes', '15') # Default 15 mins if not provided

        # 1. PREPARE THE DATES
        if not start_date or not end_date:
            end_dt = datetime.now()
            start_dt = end_dt - timedelta(hours=48)
            start_date = start_dt.strftime('%Y-%m-%d %H:%M:%S')
            end_date = end_dt.strftime('%Y-%m-%d %H:%M:%S')
        else:
            start_date = start_date.replace('T', ' ') + ':00'
            end_date = end_date.replace('T', ' ') + ':59'



        # 2. --- THE NEW SAFETY VALVE ---
        # Convert strings to datetime objects to do the math
        start_dt_math = datetime.strptime(start_date, '%Y-%m-%d %H:%M:%S')
        end_dt_math = datetime.strptime(end_date, '%Y-%m-%d %H:%M:%S')
        total_seconds = (end_dt_math - start_dt_math).total_seconds()

        # Map your exact resolution names to seconds
        res_map = {
            'raw': 60,          # 1 min
            '5min': 300,        # 5 mins
            'hourly': 3600,     # 1 hour
            'daily': 86400      # 1 day
        }

        # Determine interval for custom or standard resolutions
        if res in res_map:
            interval_seconds = res_map[res]
        elif res == 'custom':
            try:
                # custom_mins is in minutes, so we multiply by 60 for seconds
                interval_seconds = int(custom_mins) * 60
                if interval_seconds <= 0:
                    interval_seconds = 60
            except ValueError:
                interval_seconds = 60
        else:
            interval_seconds = 60

        # Calculate estimated points
        estimated_points = total_seconds / interval_seconds

        # The 10,000 Point Limiter
        if estimated_points > 10100:
            max_allowed_days = int((10100 * interval_seconds) / 86400)

            error_msg = (
                f"Request too large ({int(estimated_points):,} points). "
                f"Server max is 10,100 points. "
                f"For this resolution, select a range of {max_allowed_days} days or less."
            )
            return jsonify({"status": "error", "message": error_msg}), 400
        # --- END SAFETY VALVE ---

        # 3. PROCEED TO DATABASE
        conn = get_db_connection()
        params = [start_date, end_date]
        where_clause = ' WHERE timestamp >= ? AND timestamp <= ?'

        # --- NEW ADVANCED TIME GROUPING LOGIC ---
        is_grouped = True
        if res == 'hourly':
            time_grp = "strftime('%Y-%m-%d %H:00:00', timestamp)"
        elif res == 'daily':
            time_grp = "strftime('%Y-%m-%d 00:00:00', timestamp)"
        elif res == '5min':
            # 300 seconds = 5 minutes
            time_grp = "datetime((CAST(strftime('%s', timestamp) AS INTEGER) / 300) * 300, 'unixepoch')"
        elif res == 'custom':
            try:
                interval_sec = int(custom_mins) * 60
                if interval_sec <= 0: interval_sec = 60
            except ValueError:
                interval_sec = 60
            time_grp = f"datetime((CAST(strftime('%s', timestamp) AS INTEGER) / {interval_sec}) * {interval_sec}, 'unixepoch')"
        else:
            time_grp = "timestamp"
            is_grouped = False

        # BUILD QUERIES
        if is_grouped:
            query_ds = f'SELECT {time_grp} as timestamp, sensor_id, ROUND(AVG(temperature), 2) as temperature FROM ds18b20_readings {where_clause} GROUP BY sensor_id, {time_grp} ORDER BY timestamp ASC'
            query_sht = f'SELECT {time_grp} as timestamp, ROUND(AVG(temperature), 2) as temperature, ROUND(AVG(humidity), 2) as humidity FROM sht35_readings {where_clause} GROUP BY {time_grp} ORDER BY timestamp ASC'
            
            query_sys = f'''SELECT {time_grp} as timestamp, ROUND(AVG(cpu_temp), 2) as cpu_temp, ROUND(AVG(cpu_usage), 2) as cpu_usage, 
                            ROUND(AVG(ram_usage), 2) as ram_usage, ROUND(AVG(disk_usage), 2) as disk_usage, MAX(uptime_hours) as uptime_hours, 
                            ROUND(AVG(cpu_freq), 2) as cpu_freq, MAX(throttle_code) as throttle_code 
                            FROM system_stats {where_clause} GROUP BY {time_grp} ORDER BY timestamp ASC'''
            
            query_emi = f'''SELECT {time_grp} as timestamp, ROUND(AVG(vm1), 3) as vm1, ROUND(AVG(vm2), 3) as vm2, ROUND(AVG(vm3), 3) as vm3, ROUND(AVG(vm4), 3) as vm4, 
                            ROUND(AVG(vm5), 3) as vm5, ROUND(AVG(vm6), 3) as vm6, ROUND(AVG(vm7), 3) as vm7, ROUND(AVG(vm8), 3) as vm8, ROUND(AVG(temp_c), 2) as temp_c, 
                            MAX(r1) as r1, MAX(r2) as r2, MAX(r3) as r3, MAX(r4) as r4, 
                            MAX(a1) as a1, MAX(a2) as a2, MAX(a3) as a3, MAX(a4) as a4, MAX(a5) as a5, 
                            MAX(io1) as io1, MAX(io2) as io2, MAX(io3) as io3, MAX(io4) as io4, MAX(io5) as io5, MAX(io6) as io6, 
                            MAX(uptime_days) as uptime_days, ROUND(AVG(meminfo), 2) as meminfo, ROUND(AVG(diskinfo), 2) as diskinfo 
                            FROM emi300_readings {where_clause} GROUP BY {time_grp} ORDER BY timestamp ASC'''
        else:
            query_ds = f'SELECT timestamp, sensor_id, temperature FROM ds18b20_readings {where_clause} ORDER BY timestamp ASC'
            query_sht = f'SELECT timestamp, temperature, humidity FROM sht35_readings {where_clause} ORDER BY timestamp ASC'
            query_sys = f'SELECT timestamp, cpu_temp, cpu_usage, ram_usage, disk_usage, uptime_hours, cpu_freq, throttle_code FROM system_stats {where_clause} ORDER BY timestamp ASC'
            query_emi = f'SELECT timestamp, vm1, vm2, vm3, vm4, vm5, vm6, vm7, vm8, temp_c, r1, r2, r3, r4, a1, a2, a3, a4, a5, io1, io2, io3, io4, io5, io6, uptime_days, meminfo, diskinfo FROM emi300_readings {where_clause} ORDER BY timestamp ASC'

        # FETCH DATA
        ds_rows = conn.execute(query_ds, params).fetchall()
        sht_rows = conn.execute(query_sht, params).fetchall()
        try: sys_rows = conn.execute(query_sys, params).fetchall()
        except sqlite3.Error as e: print(f"DB Error Sys: {e}"); sys_rows = []
        try: emi_rows = conn.execute(query_emi, params).fetchall()
        except sqlite3.Error as e: print(f"DB Error EMI: {e}"); emi_rows = []
        conn.close()

        # 1. Package Sensor Data
        sensors_data = {}
        for row in ds_rows:
            sensor_id = f"DS18B20: {row['sensor_id']}"
            if sensor_id not in sensors_data: sensors_data[sensor_id] = []
            sensors_data[sensor_id].append({"x": row["timestamp"], "y": row["temperature"]})

        if sht_rows:
            sensors_data["SHT35: Temperature"] = []
            sensors_data["SHT35: Humidity"] = []
            for row in sht_rows:
                sensors_data["SHT35: Temperature"].append({"x": row["timestamp"], "y": row["temperature"]})
                sensors_data["SHT35: Humidity"].append({"x": row["timestamp"], "y": row["humidity"]})

        if emi_rows:
            sensors_data["EMI-300: Temperature"] = []
            for row in emi_rows: sensors_data["EMI-300: Temperature"].append({"x": row["timestamp"], "y": row["temp_c"]})

        # 2. Package Pi System Data
        system_data = {"CPU Temp (°C)": [], "CPU Usage (%)": [], "RAM Usage (%)": [], "Disk Usage (%)": [], "CPU Freq (MHz)": [], "Uptime (Hrs)": [], "Throttle Code": []}
        for row in sys_rows:
            ts = row["timestamp"]
            system_data["CPU Temp (°C)"].append({"x": ts, "y": row["cpu_temp"]})
            system_data["CPU Usage (%)"].append({"x": ts, "y": row["cpu_usage"]})
            system_data["RAM Usage (%)"].append({"x": ts, "y": row["ram_usage"]})
            system_data["Disk Usage (%)"].append({"x": ts, "y": row["disk_usage"]})
            system_data["CPU Freq (MHz)"].append({"x": ts, "y": row["cpu_freq"]})
            system_data["Uptime (Hrs)"].append({"x": ts, "y": row["uptime_hours"]})
            system_data["Throttle Code"].append({"x": ts, "y": row["throttle_code"]})

        # 3. Package EMI-300 Data
        emi_voltages = { "VM1": [], "VM2": [], "VM3": [], "VM4": [], "VM5": [], "VM6": [], "VM7": [], "VM8": [] }
        emi_sys = { "Mem Usage (%)": [], "Disk Usage (%)": [], "Uptime (Days)": [] }
        emi_digital = { "r1":[], "r2":[], "r3":[], "r4":[], "a1":[], "a2":[], "a3":[], "a4":[], "a5":[], "io1":[], "io2":[], "io3":[], "io4":[], "io5":[], "io6":[] }
        
        for row in emi_rows:
            ts = row["timestamp"]
            for i in range(1, 9): emi_voltages[f"VM{i}"].append({"x": ts, "y": row[f"vm{i}"]})
            emi_sys["Mem Usage (%)"].append({"x": ts, "y": row["meminfo"]})
            emi_sys["Disk Usage (%)"].append({"x": ts, "y": row["diskinfo"]})
            emi_sys["Uptime (Days)"].append({"x": ts, "y": row["uptime_days"]})
            for r in range(1, 5): emi_digital[f"r{r}"].append({"x": ts, "y": row[f"r{r}"]})
            for a in range(1, 6): emi_digital[f"a{a}"].append({"x": ts, "y": row[f"a{a}"]})
            for io in range(1, 7): emi_digital[f"io{io}"].append({"x": ts, "y": row[f"io{io}"]})

        return jsonify({"sensors": sensors_data, "system": system_data, "voltages": emi_voltages, "emi_sys": emi_sys, "emi_digital": emi_digital})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/relay/<int:relay_id>/<action>')
def control_relay(relay_id, action):
    if relay_id not in RELAY_PINS: return jsonify({"status": "error", "message": "Relay not found"}), 404
    relay = get_relay(relay_id)
    if action == "on": relay.on()
    elif action == "off": relay.off()
    else: return jsonify({"status": "error", "message": "Invalid action"}), 400
    state = "ON" if relay.is_active else "OFF"
    return jsonify({"status": "success", "relay": relay_id, "state": state})

@app.route('/backups', methods=['GET'])
def list_backups():
    backup_dir = '/mnt/usb1/codar_backups/'
    try:
        # Scan the folder for files
        files = [f for f in os.listdir(backup_dir) if os.path.isfile(os.path.join(backup_dir, f))]
        # Sort them so the newest backups are always at the top
        files.sort(key=lambda x: os.path.getmtime(os.path.join(backup_dir, x)), reverse=True)
        
        # Format a nice list with file sizes
        file_data = []
        for f in files:
            size_mb = os.path.getsize(os.path.join(backup_dir, f)) / (1024 * 1024)
            file_data.append({"name": f, "size": f"{size_mb:.2f} MB"})
            
        return jsonify({"status": "success", "files": file_data})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route('/backups/download/<filename>', methods=['GET'])
def download_backup(filename):
    backup_dir = '/mnt/usb1/codar_backups/'
    # as_attachment=True forces the browser to download it instead of trying to read it
    return send_from_directory(backup_dir, filename, as_attachment=True)

##########
## LOGs ##
##########


@app.route('/logs', methods=['GET'])
def get_logs():
    try:
        import os
        import subprocess
        
        # Helper function to run shell commands safely with a proper environment
        def run_cmd(cmd):
            try:
                # 1. Grab the current environment variables
                safe_env = os.environ.copy()
                # 2. Give it the standard Linux map to find 'sudo', 'tail', 'grep', etc.
                safe_env["PATH"] = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
                
                return subprocess.check_output(cmd, shell=True, text=True, stderr=subprocess.STDOUT, env=safe_env).strip()
            except subprocess.CalledProcessError as e:
                return f"Error executing log command: {e.output}"

        # Fetch all logs
        logs_data = {
            "status": "success",
            # Your Existing Logs
            "sensor_logs": run_cmd("sudo journalctl -u sensor_logger.service -n 20 --no-pager"),
            "flask_logs": run_cmd("sudo journalctl -u flask_api.service -n 20 --no-pager"),
            "nginx_logs": run_cmd("sudo journalctl -u nginx.service -n 20 --no-pager"),
           # "backup_logs": run_cmd("sudo journalctl -u backup.service -n 20 --no-pager"), # this is not a service right now so look for cron logs instead
            "backup_logs": run_cmd("sudo tail -n 20 /home/codar/python_web_app/backup_log.txt"),
            
            "email_logs": run_cmd("sudo tail -n 20 /home/codar/gmail_test/pi_monitor.log"),
            # The 4 New System Logs
#            "dmesg_logs": run_cmd("sudo dmesg -T | tail -n 20"),
#            "auth_logs": run_cmd("sudo tail -n 20 /var/log/auth.log"),
#            "cron_logs": run_cmd("sudo grep CRON /var/log/syslog | tail -n 20"),
#            "nginx_err_logs": run_cmd("sudo tail -n 20 /var/log/nginx/error.log")
# The 4 New System Logs
            "dmesg_logs": run_cmd("sudo dmesg -T | tail -n 20"),
            
            # Use journalctl instead of the missing auth.log
            "auth_logs": run_cmd("sudo journalctl -u ssh.service -n 20 --no-pager"),
            
            # Use journalctl instead of the missing syslog
            "cron_logs": run_cmd("sudo journalctl -u cron.service -n 20 --no-pager"),
            
            # Nginx still writes to its own physical file, so this one stays the same!
            "nginx_err_logs": run_cmd("sudo tail -n 20 /var/log/nginx/error.log")

        }
        
        return jsonify(logs_data)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})


########
# Manual Log
########


@app.route('/tags', methods=['GET'])
def get_tags():
    try:
        tags_file = '/home/codar/python_web_app/tags.json'
        
        # If the file doesn't exist yet, create it with some default tags
        if not os.path.exists(tags_file):
            default_tags = ["Maintenance", "Calibration", "Hardware Swap", "Error", "Observation"]
            with open(tags_file, 'w') as f:
                json.dump(default_tags, f)
            return jsonify({"status": "success", "tags": default_tags})
            
        # Read and return the tags
        with open(tags_file, 'r') as f:
            tags = json.load(f)
        return jsonify({"status": "success", "tags": tags})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route('/tags', methods=['POST'])
def create_tag():
    try:
        data = request.get_json()
        new_tag = data.get('tag', '').strip()
        
        if not new_tag:
            return jsonify({"status": "error", "message": "Tag cannot be empty"})

        tags_file = '/home/codar/python_web_app/tags.json'
        
        # Load existing tags
        with open(tags_file, 'r') as f:
            tags = json.load(f)
            
        # Add the new tag if it doesn't already exist
        if new_tag not in tags:
            tags.append(new_tag)
            # Save the updated list back to the file
            with open(tags_file, 'w') as f:
                json.dump(tags, f)
                
        return jsonify({"status": "success", "tags": tags})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})


@app.route('/manual_logs', methods=['GET'])
def get_manual_logs():
    try:
        with open('/home/codar/python_web_app/manual_log.txt', 'r') as f:
            content = f.read()
        return jsonify({"status": "success", "logs": content})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})


@app.route('/manual_logs', methods=['POST'])
def add_manual_log():
    try:
        data = request.get_json()
        new_entry = data.get('entry', '').strip()
        tags = data.get('tags', [])  # Get the array of tags from the frontend
        
        if not new_entry:
            return jsonify({"status": "error", "message": "Entry cannot be empty"})

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Format tags into brackets, e.g., "[Maintenance] [Error] "
        tag_string = ""
        if tags:
            tag_string = " ".join([f"[{t}]" for t in tags]) + " "

        # Assemble the final log line
        formatted_entry = f"[{timestamp}] {tag_string}{new_entry}\n"

        with open('/home/codar/python_web_app/manual_log.txt', 'a') as f:
            f.write(formatted_entry)

        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})






@app.route('/manual_logs/download', methods=['GET'])
def download_manual_log():
    try:
        log_path = '/home/codar/python_web_app/manual_log.txt'
        
        # FIX: Grab today's date using the exact same logic as your POST route
        today_str = datetime.now().strftime("%Y-%m-%d")
        
        # This sends the file and suggests a filename with today's date
        return send_file(log_path,
                         as_attachment=True,
                         download_name=f"pi_manual_log_{today_str}.txt")
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

import subprocess
from flask import jsonify

@app.route('/system_health', methods=['GET'])
def get_system_health():
    health_status = {
        "hardware_watchdog": "Unknown",
        "software_daemon": "Inactive",
        "load_average": "0.00"
    }

    try:
        # 1. Check if Software Watchdog is running
        sw_check = subprocess.run(['/usr/bin/systemctl', 'is-active', 'watchdog'], capture_output=True, text=True)
        health_status["software_daemon"] = "Active" if sw_check.stdout.strip() == "active" else "Inactive"

        # 2. Check if Hardware Watchdog device exists
        hw_check = subprocess.run(['/usr/bin/ls', '/dev/watchdog'], capture_output=True)
        health_status["hardware_watchdog"] = "Ready" if hw_check.returncode == 0 else "Error/Not Found"

        # 3. Get current 1-minute load average
        with open("/proc/loadavg", "r") as f:
            health_status["load_average"] = f.read().split()[0]

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

    return jsonify(health_status)





####
# Main
####

if __name__ == '__main__':
    app.run()
