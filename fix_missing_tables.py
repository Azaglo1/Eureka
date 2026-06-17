import os, sys
sys.path.insert(0, r"C:\Users\LENOVO\OneDrive\Desktop\school")
os.chdir(r"C:\Users\LENOVO\OneDrive\Desktop\school")
from db_utils import connect_db
from dotenv import load_dotenv
load_dotenv()
db = connect_db()
cur = db.cursor()
cur.execute('SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = %s)', ('school_subjects',))
print('school_subjects exists:', cur.fetchone()[0])
cur.close()
db.close()
