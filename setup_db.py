import sqlite3
import random
from datetime import datetime, timedelta

# 1. Connect to the database (this creates the 'sensors.db' file automatically)
conn = sqlite3.connect('sensors.db')
cursor = conn.cursor()

# 2. Create the table schema
cursor.execute('''
    CREATE TABLE IF NOT EXISTS sensor_data (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        temperature REAL,
        humidity REAL,
        voltage REAL,
        current REAL
    )
''')

# 3. Clear any old data if you run this script multiple times
cursor.execute('DELETE FROM sensor_data')

# 4. Generate 24 hours of fake historical data (one reading per hour)
print("Generating 24 hours of mock sensor data...")
now = datetime.now()

for i in range(24):
    # Calculate a timestamp for the past 24 hours
    record_time = now - timedelta(hours=24-i)
    time_str = record_time.strftime("%Y-%m-%d %H:%M:%S")
    
    # Generate random realistic values
    temp = round(random.uniform(20.0, 30.0), 2)    # 20°C to 30°C
    hum = round(random.uniform(40.0, 60.0), 2)     # 40% to 60% humidity
    volt = round(random.uniform(11.5, 12.5), 2)    # 11.5V to 12.5V
    curr = round(random.uniform(1.0, 5.0), 2)      # 1A to 5A
    
    # Insert the row into the database
    cursor.execute('''
        INSERT INTO sensor_data (timestamp, temperature, humidity, voltage, current)
        VALUES (?, ?, ?, ?, ?)
    ''', (time_str, temp, hum, volt, curr))

# 5. Save (commit) the changes and close the connection
conn.commit()
conn.close()

print("Database 'sensors.db' created and populated successfully!")
