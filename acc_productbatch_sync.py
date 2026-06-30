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
    SELECT b.productcode, b.salesprice, b.secondprice, b.thirdprice, b.fourthprice,
           b.nlc1, b.quantity, b.barcode, b.bmrp, b.settings
    FROM DBA.acc_productbatch b
    INNER JOIN DBA.acc_product p ON b.productcode = p.code
    WHERE TRIM(p.settings) LIKE '#EC%'
    AND TRIM(b.settings) LIKE '#EC%'
    AND b.barcode IS NOT NULL
"""


def get_total_count(conn):
    cursor = conn.cursor()
    cursor.execute("""
        SELECT COUNT(*) FROM DBA.acc_productbatch b
        INNER JOIN DBA.acc_product p ON b.productcode = p.code
        WHERE TRIM(p.settings) LIKE '#EC%' AND TRIM(b.settings) LIKE '#EC%'
        AND b.barcode IS NOT NULL
    """)
    return cursor.fetchone()[0]


def fetch_batches(conn):
    cursor = conn.cursor()
    cursor.execute(SQL_QUERY)
    while True:
        rows = cursor.fetchmany(BATCH_SIZE)
        if not rows:
            break
        yield [{
            "productcode": r[0],
            "salesprice": float(r[1]) if r[1] is not None else None,
            "secondprice": float(r[2]) if r[2] is not None else None,
            "thirdprice": float(r[3]) if r[3] is not None else None,
            "fourthprice": float(r[4]) if r[4] is not None else None,
            "nlc1": float(r[5]) if r[5] is not None else None,
            "quantity": float(r[6]) if r[6] is not None else None,
            "barcode": r[7],
            "bmrp": float(r[8]) if r[8] is not None else None,
            "settings": r[9]
        } for r in rows]
    cursor.close()


BASE_URL = "https://pkb2bsyncapi.myimc.in/api"


def push_to_api(cfg, records, is_first_batch=False):
    url = BASE_URL + "/productbatch/sync/"
    response = requests.post(url, json={"records": records, "is_first_batch": is_first_batch}, timeout=(10, 300))
    response.raise_for_status()
    return response.json()


def run_sync():
    cfg = load_config()
    print(f"[SYNC] Connecting to DSN: {cfg['dsn']}")
    conn = get_sql_connection(cfg)
    print("[SYNC] Connected successfully")

    try:
        print("[SYNC] Fetching acc_productbatch joined with acc_product WHERE #EC%")
        for i, batch in enumerate(fetch_batches(conn)):
            result = push_to_api(cfg, batch, is_first_batch=(i == 0))
            print(f"  -> Pushed {len(batch)} records | Response: {result}")
    finally:
        conn.close()

    print("[SYNC] Done.")


if __name__ == "__main__":
    run_sync()
