import sqlite3

SCAN_ID = "d26ff5c5-cced-4c62-ad20-d88ddcdd6f59"

connection = sqlite3.connect("backend/woundsplat.db")
connection.row_factory = sqlite3.Row

for table in ("scans", "measurements"):
    print(f"[{table}]")
    rows = connection.execute(
        f"SELECT * FROM {table} WHERE scan_id = ?" if table == "measurements"
        else f"SELECT * FROM {table} WHERE id = ?",
        (SCAN_ID,),
    ).fetchall()
    for row in rows:
        print(dict(row))
