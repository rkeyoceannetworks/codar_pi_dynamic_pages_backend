import os
import glob
import time
import sqlite3

# Load the 1-Wire kernel modules
os.system('modprobe w1-gpio')
os.system('modprobe w1-therm')

# The directory where the Pi lists all connected 1-Wire devices
BASE_DIR = '/sys/bus/w1/devices/'

def read_temp_raw(device_file):
    """Reads the raw text output from the sensor hardware file."""
    with open(device_file, 'r') as f:
        lines = f.readlines()
    return lines

def read_temp(device_file):
    """Parses the raw text to extract the actual temperature."""
    lines = read_temp_raw(device_file)
    
    # The sensor prints 'YES' at the end of the first line if the read was successful
    while lines[0].strip()[-3:] != 'YES':
        time.sleep(0.2)
        lines = read_temp_raw(device_file)
        
    # The temperature is on the second line, starting with 't='
    equals_pos = lines[1].find('t=')
    if equals_pos != -1:
        temp_string = lines[1][equals_pos+2:]
        # The output is in thousandths of a degree Celsius, so divide by 1000
        temp_c = float(temp_string) / 1000.0
        return round(temp_c, 2)
    return None

def log_temperatures():
    # 1. Dynamically find all folders starting with '28-' (the DS18B20 family code)
    device_folders = glob.glob(BASE_DIR + '28*')
    
    if not device_folders:
        print("No DS18B20 sensors detected. Check wiring and raspi-config.")
        return

    # 2. Connect to the database
    conn = sqlite3.connect('/home/codar/python_web_app/sensors.db')
    cursor = conn.cursor()
    
    # 3. Ensure our dynamic multi-sensor table exists
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ds18b20_readings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            sensor_id TEXT,
            temperature REAL
        )
    ''')

    print(f"Found {len(device_folders)} sensor(s). Reading and logging...")
    
    # 4. Loop through whatever sensors are currently plugged in
    for folder in device_folders:
        # Extract the unique MAC address from the folder name
        sensor_id = os.path.basename(folder)
        device_file = folder + '/w1_slave'
        
        # Get the temperature
        temp_c = read_temp(device_file)
        
        if temp_c is not None:
            print(f"Sensor ID [{sensor_id}]: {temp_c}°C")
            # Insert the reading into the database
            cursor.execute(
                'INSERT INTO ds18b20_readings (sensor_id, temperature) VALUES (?, ?)',
                (sensor_id, temp_c)
            )
            
    # 5. Save the database changes
    conn.commit()
    conn.close()
    print("Logging complete!")

if __name__ == '__main__':
    log_temperatures()
