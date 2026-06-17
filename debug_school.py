from app import app
from db_utils import get_db

with app.app_context():
    db = get_db()
    cursor = db.cursor()
    
    # Test the query
    cursor.execute("SELECT id FROM schools LIMIT 1")
    school_result = cursor.fetchone()
    print(f"school_result: {school_result}")
    print(f"type: {type(school_result)}")
    
    if school_result:
        print(f"school_result[0]: {school_result[0]}")
        print(f"type of school_result[0]: {type(school_result[0])}")
    
    # Also test what we're actually getting
    cursor.execute("SELECT id FROM schools")
    all_results = cursor.fetchall()
    print(f"all_results: {all_results}")
    print(f"type: {type(all_results)}")