"""clean_db.py — Verwijder onrealistische signalen uit de database"""
import insider_database as idb
import sqlite3

con = sqlite3.connect(idb.DB_PATH)
cursor = con.cursor()

# Verwijder signalen met onrealistische waarden
cursor.execute("DELETE FROM signals WHERE value > 5000000000")
print(f"Verwijderd (waarde > $5B): {cursor.rowcount}")

cursor.execute("DELETE FROM signals WHERE price > 10000")
print(f"Verwijderd (prijs > $10.000): {cursor.rowcount}")

con.commit()

total = cursor.execute("SELECT COUNT(*) FROM signals").fetchone()[0]
print(f"\nResterende signalen: {total}")

con.close()