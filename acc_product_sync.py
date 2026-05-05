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


BATCH_SIZE = 200

SQL_QUERY = """
    SELECT code, name, text3, text5, unit, taxcode, company, product, brand, text6, nameinsl, settings, properties
    FROM DBA.acc_product
    WHERE TRIM(settings) LIKE '#EC%'
"""


def fetch_products(conn):
    cursor = conn.cursor()
    cursor.execute(SQL_QUERY)
    while True:
        rows = cursor.fetchmany(BATCH_SIZE)
        if not rows:
            break
        yield [{
            "code": r[0],
            "name": r[1],
            "text3": r[2],
            "text5": r[3],
            "unit": r[4],
            "taxcode": r[5],
            "company": r[6],
            "product": r[7],
            "brand": r[8],
            "text6": r[9],
            "nameinsl": r[10],
            "settings": r[11],
            "properties": r[12]
        } for r in rows]
    cursor.close()


BASE_URL = "https://pkb2bsyncapi.myimc.in/api"


def push_to_api(cfg, records, is_first_batch=False):
    url = BASE_URL + "/product/sync/"
    response = requests.post(url, json={"records": records, "is_first_batch": is_first_batch}, timeout=(10, 300))
    response.raise_for_status()
    return response.json()


def run_sync():
    cfg = load_config()
    print(f"[SYNC] Connecting to DSN: {cfg['dsn']}")
    conn = get_sql_connection(cfg)
    print("[SYNC] Connected successfully")

    try:
        print("[SYNC] Fetching acc_product WHERE TRIM(settings) LIKE '#EC%'")
        for i, batch in enumerate(fetch_products(conn)):
            result = push_to_api(cfg, batch, is_first_batch=(i == 0))
            print(f"  -> Pushed {len(batch)} records | Response: {result}")
    finally:
        conn.close()

    print("[SYNC] Done.")


if __name__ == "__main__":
    run_sync()
