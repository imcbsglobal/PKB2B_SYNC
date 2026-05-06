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
    SELECT ph.code, ph.url2
    FROM DBA.acc_productphoto ph
    INNER JOIN DBA.acc_product p ON ph.code = p.code
    WHERE ph.slno = (
        SELECT MIN(ph2.slno)
        FROM DBA.acc_productphoto ph2
        WHERE ph2.code = ph.code
        AND ph2.favourite = '1'
    )
    OR (
        ph.favourite != '1'
        AND NOT EXISTS (
            SELECT 1 FROM DBA.acc_productphoto ph3
            WHERE ph3.code = ph.code AND ph3.favourite = '1'
        )
        AND ph.slno = (
            SELECT MIN(ph4.slno) FROM DBA.acc_productphoto ph4
            WHERE ph4.code = ph.code
        )
    )
"""


def get_total_count(conn):
    cursor = conn.cursor()
    cursor.execute("""
        SELECT COUNT(DISTINCT ph.code)
        FROM DBA.acc_productphoto ph
        INNER JOIN DBA.acc_product p ON ph.code = p.code
    """)
    return cursor.fetchone()[0]


def fetch_photos(conn):
    cursor = conn.cursor()
    cursor.execute(SQL_QUERY)
    while True:
        rows = cursor.fetchmany(BATCH_SIZE)
        if not rows:
            break
        yield [{"code": r[0], "url2": r[1] or ""} for r in rows]
    cursor.close()


BASE_URL = "https://pkb2bsyncapi.myimc.in/api"


def push_to_api(cfg, records, is_first_batch=False):
    url = BASE_URL + "/productphoto/sync/"
    response = requests.post(url, json={"records": records, "is_first_batch": is_first_batch}, timeout=(10, 300))
    response.raise_for_status()
    return response.json()


def run_sync():
    cfg = load_config()
    print(f"[SYNC] Connecting to DSN: {cfg['dsn']}")
    conn = get_sql_connection(cfg)
    print("[SYNC] Connected successfully")

    try:
        print("[SYNC] Fetching acc_productphoto joined with acc_product")
        for i, batch in enumerate(fetch_photos(conn)):
            result = push_to_api(cfg, batch, is_first_batch=(i == 0))
            print(f"  -> Pushed {len(batch)} records | Response: {result}")
    finally:
        conn.close()

    print("[SYNC] Done.")


if __name__ == "__main__":
    run_sync()
