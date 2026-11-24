import sqlite3
from datetime import datetime

DB_PATH = '/home/codar/python_web_app/sensors.db'
DAYS_TO_KEEP = 800

def cleanup_database():
    try:
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Starting database cleanup...")
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # The SQL command to delete records older than 30 days
        delete_query = f"DELETE FROM {{}} WHERE timestamp <= datetime('now', '-{DAYS_TO_KEEP} days')"

        tables = ['ds18b20_readings', 'sht35_readings', 'system_stats', 'emi300_readings']
        
        total_deleted = 0
        for table in tables:
            cursor.execute(delete_query.format(table))
            deleted_rows = cursor.rowcount
            total_deleted += deleted_rows
            print(f" - Cleaned {deleted_rows} old records from {table}")

        conn.commit()

        # VACUUM defragments the database and releases the empty space back to the OS
        print(" - Vacuuming database to reclaim disk space...")
        cursor.execute("VACUUM")
        
        conn.close()
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Cleanup complete. Total records removed: {total_deleted}\n")

    except Exception as e:
        print(f"Error during database cleanup: {e}")

if __name__ == '__main__':
    cleanup_database()
