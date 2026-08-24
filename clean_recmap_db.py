import sqlite3
import os

db_path = "D:/claude/Hesh rec/recmap.db"
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    tables = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    print(f"Tables in recmap.db: {tables}")
    for t in tables:
        try:
            cur.execute(f"DELETE FROM {t}")
            print(f"Purged table: {t}")
        except Exception as e:
            print(f"Error purging {t}: {e}")
    conn.commit()
    conn.close()
    print("Purged recmap.db successfully.")
