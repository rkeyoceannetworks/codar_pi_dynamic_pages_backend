import os
import glob
import time
import sqlite3
import smbus2
import psutil
import subprocess
import requests
import urllib3
import json

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

CONFIG_FILE = '/home/codar/python_web_app/config.json'

def load_config():
    default_config = {
        "logging_enabled": {"ds18b20": True, "sht35": True, "system_stats": True, "emi300": True},
        "emi300_settings": {"ip_address": "192.168.1.174", "username": "admin", "password": "CHANGE_ME"},
        "system_settings": {"db_filename": "sensors.db", "polling_interval_sec": 60, "cpu_measure_window_sec": 1.0}
    }
    try:
        if not os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'w') as f:
                json.dump(default_config, f, indent=4)
            return default_config
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading config: {e}")
        return default_config

# --- Hardware Setup ---
os.system('modprobe w1-gpio')
os.system('modprobe w1-therm')
BASE_DIR = '/sys/bus/w1/devices/'
I2C_BUS = 1
SHT35_ADDRESS = 0x45

def read_ds18b20(device_file):
    try:
        with open(device_file, 'r') as f: lines = f.readlines()
        while lines[0].strip()[-3:] != 'YES':
            time.sleep(0.2)
            with open(device_file, 'r') as f: lines = f.readlines()
        equals_pos = lines[1].find('t=')
        if equals_pos != -1: return round(float(lines[1][equals_pos+2:]) / 1000.0, 2)
    except Exception: pass
    return None

def read_sht35():
    try:
        # Wrapping this in a 'with' block ensures the bus closes instantly!
        with smbus2.SMBus(I2C_BUS) as bus:
            bus.write_i2c_block_data(SHT35_ADDRESS, 0x2C, [0x06])
            time.sleep(0.5) 
            data = bus.read_i2c_block_data(SHT35_ADDRESS, 0x00, 6)
            
            temp_c = ((((data[0] * 256.0) + data[1]) * 175) / 65535.0) - 45
            humidity = 100 * (data[3] * 256 + data[4]) / 65535.0
            return round(temp_c, 2), round(humidity, 2)
    except Exception: 
        return None, None

def get_system_stats(cpu_window):
    stats = {}
    try:
        # Measure the CPU using the dynamic window from config.json
        with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f: stats['cpu_temp'] = round(float(f.read())/1000.0, 2)
        stats['cpu_usage'] = psutil.cpu_percent(interval=cpu_window)

        stats['ram_usage'] = psutil.virtual_memory().percent
        stats['disk_usage'] = psutil.disk_usage('/').percent
        with open('/proc/uptime', 'r') as f: stats['uptime_hours'] = round(float(f.readline().split()[0])/3600.0, 2)
#        stats['cpu_freq'] = round(psutil.cpu_freq().current, 2)
        freq = psutil.cpu_freq()
        stats['cpu_freq'] = round(freq.current, 2) if freq else None
        throttle_raw = subprocess.check_output(['vcgencmd', 'get_throttled']).decode('utf-8').strip()
        stats['throttle_code'] = int(throttle_raw.split('=')[1], 16) 
        return stats
    except Exception: return None

def read_network_device(ip, user, password):
    url = f"https://{ip}/api/sdserver.php?element=homeall"
    response = None
    try:
        # Using 'with' guarantees the connection is closed when the block finishes
        with requests.get(url, auth=(user, password), verify=False, timeout=10) as response:

    #    if response.status_code == 200:
            response.raise_for_status() # Check for HTTP errors like 404 or 500
            data = response.json() # Or response.text depending on what you do with it
            vms = data.get("vms", {})
            
            # Voltages
            vm1 = float(vms.get("vm1", 0))
            vm2 = float(vms.get("vm2", 0))
            vm3 = float(vms.get("vm3", 0))
            vm4 = float(vms.get("vm4", 0))
            vm5 = float(vms.get("vm5", 0))
            vm6 = float(vms.get("vm6", 0))
            vm7 = float(vms.get("vm7", 0))
            vm8 = float(vms.get("vm8", 0))
            
            # Temp
            temp_c = float(vms.get("tempc", "0").split(" ")[0])
            
            # Relays
            r1 = int(vms.get("r1", 0))
            r2 = int(vms.get("r2", 0))
            r3 = int(vms.get("r3", 0))
            r4 = int(vms.get("r4", 0))
            
            # Alarms
            a1 = int(vms.get("a1", 0))
            a2 = int(vms.get("a2", 0))
            a3 = int(vms.get("a3", 0))
            a4 = int(vms.get("a4", 0))
            a5 = int(vms.get("a5", 0))
            
            # GPIO
            io1 = int(vms.get("io1", 0))
            io2 = int(vms.get("io2", 0))
            io3 = int(vms.get("io3", 0))
            io4 = int(vms.get("io4", 0))
            io5 = int(vms.get("io5", 0))
            io6 = int(vms.get("io6", 0))
            
            # Uptime (Strips spaces and "Days")
            uptime_days = float(vms.get("uptime", "0").strip().split(" ")[0])
            
            # NEW: Mem and Disk (Strips spaces)
            meminfo = float(vms.get("meminfo", "0").strip())
            diskinfo = float(vms.get("diskinfo", "0").strip())
            
            return (vm1, vm2, vm3, vm4, vm5, vm6, vm7, vm8, temp_c, 
                    r1, r2, r3, r4, a1, a2, a3, a4, a5, 
                    io1, io2, io3, io4, io5, io6, uptime_days, meminfo, diskinfo)
#        else:
#            print(f"EMI-300 Network Error: Received Status Code {response.status_code}")
    except Exception as e:
        print(f"Error reading network device: {e}")
        if response is not None:
            print(f"EMI-300 Network Error: Received Status Code {response.status_code}")
    return None

def log_all_sensors():
    config = load_config()
###
# read sensors
###
    flags = config.get("logging_enabled", {})
    emi_cfg = config.get("emi300_settings", {})
    sys_cfg = config.get("system_settings", {})

###
#Write to database
##  
    db_filename = sys_cfg.get("db_filename", "sensors.db")
    cpu_window = sys_cfg.get("cpu_measure_window_sec", 1.0)

    db_path = f'/home/codar/python_web_app/{db_filename}'

# 1. Add timeout=30.0 to your connection
# This makes Python wait in line for up to 30 seconds before giving up.
    try:

        conn = sqlite3.connect(db_path, timeout=30) #make the timeout longer if need be as the backup of the database sometimes causes a hang
        cursor = conn.cursor()
        
        cursor.execute('''CREATE TABLE IF NOT EXISTS ds18b20_readings (id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP, sensor_id TEXT, temperature REAL)''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS sht35_readings (id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP, temperature REAL, humidity REAL)''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS system_stats (id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP, cpu_temp REAL, cpu_usage REAL, ram_usage REAL, disk_usage REAL, uptime_hours REAL, cpu_freq REAL, throttle_code INTEGER)''')
        
        # NEW EXPANDED TABLE WITH MEMINFO AND DISKINFO
        cursor.execute('''CREATE TABLE IF NOT EXISTS emi300_readings (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                            vm1 REAL, vm2 REAL, vm3 REAL, vm4 REAL, vm5 REAL, vm6 REAL, vm7 REAL, vm8 REAL, temp_c REAL,
                            r1 INTEGER, r2 INTEGER, r3 INTEGER, r4 INTEGER,
                            a1 INTEGER, a2 INTEGER, a3 INTEGER, a4 INTEGER, a5 INTEGER,
                            io1 INTEGER, io2 INTEGER, io3 INTEGER, io4 INTEGER, io5 INTEGER, io6 INTEGER,
                            uptime_days REAL, meminfo REAL, diskinfo REAL)''')

        print(f"--- Reading Sensors & System (DB: {db_filename}) ---")

        if flags.get("ds18b20", True):
            for folder in glob.glob(BASE_DIR + '28*'):
                sensor_id = os.path.basename(folder)
                temp_c = read_ds18b20(folder + '/w1_slave')
                if temp_c is not None: cursor.execute('INSERT INTO ds18b20_readings (sensor_id, temperature) VALUES (?, ?)', (sensor_id, temp_c))

        if flags.get("sht35", True):
            sht_temp, sht_hum = read_sht35()
            if sht_temp is not None: cursor.execute('INSERT INTO sht35_readings (temperature, humidity) VALUES (?, ?)', (sht_temp, sht_hum))

        if flags.get("system_stats", True):
            sys_stats = get_system_stats(cpu_window)
            if sys_stats is not None: cursor.execute('''INSERT INTO system_stats (cpu_temp, cpu_usage, ram_usage, disk_usage, uptime_hours, cpu_freq, throttle_code) VALUES (?, ?, ?, ?, ?, ?, ?)''', (sys_stats['cpu_temp'], sys_stats['cpu_usage'], sys_stats['ram_usage'], sys_stats['disk_usage'], sys_stats['uptime_hours'], sys_stats['cpu_freq'], sys_stats['throttle_code']))

        if flags.get("emi300", True):
            net_data = read_network_device(emi_cfg.get("ip_address"), emi_cfg.get("username"), emi_cfg.get("password"))
            if net_data is not None:
                print(f"EMI-300: Temp {net_data[8]}°C | Mem: {net_data[25]}% | Disk: {net_data[26]}%")
                # 27 Question marks to match the 27 items returned by read_network_device!
                cursor.execute('''INSERT INTO emi300_readings 
                                  (vm1, vm2, vm3, vm4, vm5, vm6, vm7, vm8, temp_c, 
                                   r1, r2, r3, r4, a1, a2, a3, a4, a5, 
                                   io1, io2, io3, io4, io5, io6, uptime_days, meminfo, diskinfo) 
                                  VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', net_data)

        conn.commit()
        conn.close()
        print("--- Logging Complete ---")

    # 2. Catch the specific SQLite error so it doesn't crash the script
    except sqlite3.OperationalError as e:
        if "locked" in str(e):
            print(f"WARNING: Database locked for over 30s. Skipping this data point. Error: {e}")
        else:
            print(f"SQLite Error: {e}")
            
    # 3. Catch any other random errors just to be safe
    except Exception as e:
        print(f"Unexpected error: {e}")
# NEW: 4. Guarantee the connection closes even if it crashes
    finally:
        try:
            if 'conn' in locals():
                conn.close()
        except Exception:
            pass

########
# Main #
########


if __name__ == '__main__':
    print("Starting continuous sensor logging service...")
    while True:
        try:
            log_all_sensors()
        except Exception as e:
            print(f"Error in main loop: {e}")
        
        # Pull the latest interval dynamically from config.json before sleeping
        current_config = load_config()
        poll_interval = current_config.get("system_settings", {}).get("polling_interval_sec", 60)
        
        time.sleep(poll_interval)
