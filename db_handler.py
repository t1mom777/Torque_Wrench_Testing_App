import sqlite3
import datetime
import json

DB_FILE = "data.db"

def init_db(db_file: str = DB_FILE) -> None:
    """
    Create the tables TorqueTable, RawData, and Summary if they do not already exist.
    """
    with sqlite3.connect(db_file) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS TorqueTable (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                max_torque REAL,
                type TEXT,
                unit TEXT,
                applied_torq TEXT,
                allowance1 TEXT,
                allowance2 TEXT,
                allowance3 TEXT
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS RawData (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                target_torque REAL,
                torque_table_id INTEGER,
                which_allowance TEXT,
                allowance_range TEXT
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS Summary (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                allowance_range TEXT,
                test_results TEXT
            )
        """)
        conn.commit()

def insert_default_torque_table_data(db_file: str = DB_FILE) -> None:
    """
    Inserts default torque table entries if the TorqueTable is empty.
    """
    default_data = [
        {
            "max_torque": 75,
            "type": "Wrench",
            "unit": "ft/lbs",
            "applied_torq": [70.0, 50.0, 30.0],
            "allowance1": "67.2 - 72.8",
            "allowance2": "48.0 - 52.0",
            "allowance3": "28.8 - 31.2"
        },
        {
            "max_torque": 80,
            "type": "Wrench",
            "unit": "ft/lbs",
            "applied_torq": [80.0, 40.0, 20.0],
            "allowance1": "76.8 - 83.2",
            "allowance2": "38.4 - 41.6",
            "allowance3": "19.2 - 20.8"
        },
        {
            "max_torque": 100,
            "type": "Wrench",
            "unit": "ft/lbs",
            "applied_torq": [100.0, 60.0, 30.0],
            "allowance1": "96.0 - 104.0",
            "allowance2": "57.6 - 62.4",
            "allowance3": "28.8 - 31.2"
        },
        {
            "max_torque": 500,
            "type": "Torque Multiplier",
            "unit": "ft/lbs",
            "applied_torq": [150.0, 100.0, 50.0],
            "allowance1": "144.0 - 156.0",
            "allowance2": "96.0 - 104.0",
            "allowance3": "48.0 - 52.0"
        },
        {
            "max_torque": 320,
            "type": "Wrench",
            "unit": "NM",
            "applied_torq": [300.0, 200.0, 100.0],
            "allowance1": "288.0 - 312.0",
            "allowance2": "192.0 - 208.0",
            "allowance3": "96.0 - 104.0"
        },
        {
            "max_torque": 240,
            "type": "Wrench",
            "unit": "in/lbs",
            "applied_torq": [230.0, 150.0, 80.0],
            "allowance1": "220.8 - 239.2",
            "allowance2": "144.0 - 156.0",
            "allowance3": "76.8 - 83.2"
        }
    ]
    with sqlite3.connect(db_file) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM TorqueTable")
        count = cursor.fetchone()[0]
        if count == 0:
            for row in default_data:
                cursor.execute("""
                    INSERT INTO TorqueTable (max_torque, type, unit, applied_torq, allowance1, allowance2, allowance3)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (row["max_torque"], row["type"], row["unit"], json.dumps(row["applied_torq"]),
                      row["allowance1"], row["allowance2"], row["allowance3"]))
            conn.commit()

def get_torque_table(db_file: str = DB_FILE) -> list:
    """
    Retrieves all entries from the TorqueTable and returns a list of dictionaries.
    """
    with sqlite3.connect(db_file) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, max_torque, type, unit, applied_torq, allowance1, allowance2, allowance3
            FROM TorqueTable
        """)
        rows = cursor.fetchall()
    torque_table = []
    for r in rows:
        torque_table.append({
            "id": r[0],
            "max_torque": r[1],
            "type": r[2],
            "unit": r[3],
            "applied_torq": r[4],
            "allowance1": r[5],
            "allowance2": r[6],
            "allowance3": r[7]
        })
    return torque_table

def insert_torque_table_entry(max_torque: float, type_str: str, unit: str, applied_torq: str,
                              allowance1: str, allowance2: str, allowance3: str, db_file: str = DB_FILE) -> None:
    """
    Adds a new entry to the TorqueTable.
    """
    with sqlite3.connect(db_file) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO TorqueTable (max_torque, type, unit, applied_torq, allowance1, allowance2, allowance3)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (max_torque, type_str, unit, applied_torq, allowance1, allowance2, allowance3))
        conn.commit()

def update_torque_table_entry(entry_id: int, max_torque: float, type_str: str, unit: str, applied_torq: str,
                              allowance1: str, allowance2: str, allowance3: str, db_file: str = DB_FILE) -> None:
    """
    Updates an existing row in the TorqueTable.
    """
    with sqlite3.connect(db_file) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE TorqueTable
            SET max_torque = ?,
                type = ?,
                unit = ?,
                applied_torq = ?,
                allowance1 = ?,
                allowance2 = ?,
                allowance3 = ?
            WHERE id = ?
        """, (max_torque, type_str, unit, applied_torq, allowance1, allowance2, allowance3, entry_id))
        conn.commit()

def insert_raw_data(target: float, torque_table_id: int, which_allowance: str, allowance_range: str, db_file: str = DB_FILE) -> None:
    """
    Inserts a measurement result (raw data) into the RawData table.
    """
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with sqlite3.connect(db_file) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO RawData (timestamp, target_torque, torque_table_id, which_allowance, allowance_range)
            VALUES (?, ?, ?, ?, ?)
        """, (timestamp, target, torque_table_id, which_allowance, allowance_range))
        conn.commit()

def insert_summary(allowance_range: str, test_results: list, db_file: str = DB_FILE) -> None:
    """
    Inserts a summary record. 'test_results' is a list of floats converted to a comma-separated string.
    """
    results_str = ",".join(str(tr) for tr in test_results)
    with sqlite3.connect(db_file) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO Summary (allowance_range, test_results)
            VALUES (?, ?)
        """, (allowance_range, results_str))
        conn.commit()

def get_all_types(db_file: str = DB_FILE) -> list:
    """
    Returns a list of distinct types from the database.
    """
    with sqlite3.connect(db_file) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT type FROM TorqueTable WHERE type IS NOT NULL")
        results = [row[0] for row in cursor.fetchall() if row[0]]
    return results

def get_all_units(db_file: str = DB_FILE) -> list:
    """
    Returns a list of distinct units from the database.
    """
    with sqlite3.connect(db_file) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT unit FROM TorqueTable WHERE unit IS NOT NULL")
        results = [row[0] for row in cursor.fetchall() if row[0]]
    return results
