import sqlite3
con = sqlite3.connect('D:/Local/Dev/sysava-nicegui/data/escola_ativa_legado.db')
cur = con.cursor()
tables = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'")]
print('LEGACY tables:', tables)
if 'user_history' in tables:
    print('user_history count:', cur.execute('SELECT COUNT(*) FROM user_history').fetchone()[0])
else:
    print('user_history: N/A')
con.close()
con2 = sqlite3.connect('D:/Local/Dev/sysava-nicegui/data/escola_ativa.db')
cur2 = con2.cursor()
tables2 = [r[0] for r in cur2.execute("SELECT name FROM sqlite_master WHERE type='table'")]
print('CLEAN tables:', tables2)
if 'user_history' in tables2:
    print('user_history count:', cur2.execute('SELECT COUNT(*) FROM user_history').fetchone()[0])
else:
    print('user_history: N/A')
con2.close()
