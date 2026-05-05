import json
import os
import sys
import requests
import pyodbc


def load_config():
    base = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(base, 'config.json')) as f:
        return json.load(f)


SQL_USERNAME = "dba"
SQL_PASSWORD = "(*$^)"


def get_sql_connection(cfg):
    return pyodbc.connect(f"DSN={cfg['dsn']};UID={SQL_USERNAME};PWD={SQL_PASSWORD}")


BATCH_SIZE = 1000

SQL_QUERY = """
    SELECT code, name, super_code, address, place, city, phone, phone2, remarkcolumntitle, gstin
    FROM DBA.acc_master
    WHERE TRIM(super_code) = 'DEBTO'
"""


def fetch_masters(conn):
    cursor = conn.cursor()
    cursor.execute(SQL_QUERY)
    while True:
        rows = cursor.fetchmany(BATCH_SIZE)
        if not rows:
            break
        yield [{
            "code": r[0],
            "name": r[1],
            "super_code": r[2],
            "address": r[3],
            "place": r[4],
            "city": r[5],
            "phone": r[6],
            "phone2": r[7],
            "remarkcolumntitle": r[8],
            "gstin": r[9]
        } for r in rows]
    cursor.close()


BASE_URL = "https://pkb2bsyncapi.myimc.in/api"


def push_to_api(cfg, records, is_first_batch=False):
    url = BASE_URL + "/master/sync/"
    response = requests.post(url, json={"records": records, "is_first_batch": is_first_batch}, timeout=(10, 120))
    response.raise_for_status()
    return response.json()


def run_sync():
    cfg = load_config()
    print(f"[SYNC] Connecting to DSN: {cfg['dsn']}")
    conn = get_sql_connection(cfg)
    print("[SYNC] Connected successfully")

    try:
        print("[SYNC] Fetching acc_master WHERE super_code = 'DEBTO'")
        for i, batch in enumerate(fetch_masters(conn)):
            result = push_to_api(cfg, batch, is_first_batch=(i == 0))
            print(f"  -> Pushed {len(batch)} records | Response: {result}")
    finally:
        conn.close()

    print("[SYNC] Done.")


if __name__ == "__main__":
    run_sync()
