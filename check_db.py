from app import app
from db_utils import get_db

def check_database():
    try:
        with app.app_context():
            db = get_db()
            cursor = db.cursor()
            
            # Check schools table
            cursor.execute("SELECT COUNT(*) FROM schools")
            school_count = cursor.fetchone()
            # Handle both tuple and dict-like row
            if isinstance(school_count, dict):
                school_count = list(school_count.values())[0]
            else:
                school_count = school_count[0]
            print(f"Schools count: {school_count}")
            if school_count > 0:
                cursor.execute("SELECT id, name, school_code FROM schools")
                schools = cursor.fetchall()
                print("Schools:")
                for school in schools:
                    if isinstance(school, dict):
                        print(f"  ID: {school['id']}, Name: {school['name']}, Code: {school['school_code']}")
                    else:
                        print(f"  ID: {school[0]}, Name: {school[1]}, Code: {school[2]}")
            else:
                print("No schools found")
            
            print("\n" + "="*50)
            
            # Check library_books table
            cursor.execute("SELECT COUNT(*) FROM library_books")
            book_count = cursor.fetchone()
            # Handle both tuple and dict-like row
            if isinstance(book_count, dict):
                book_count = list(book_count.values())[0]
            else:
                book_count = book_count[0]
            print(f"Inventory items count: {book_count}")
            if book_count > 0:
                cursor.execute("SELECT id, title, author, quantity, stock_status, category FROM library_books ORDER BY id LIMIT 10")
                books = cursor.fetchall()
                print("Sample inventory items:")
                for book in books:
                    if isinstance(book, dict):
                        print(f"  ID: {book['id']}, Title: {book['title']}, Author: {book['author']}, Qty: {book['quantity']}, Status: {book['stock_status']}, Category: {book['category']}")
                    else:
                        print(f"  ID: {book[0]}, Title: {book[1]}, Author: {book[2]}, Qty: {book[3]}, Status: {book[4]}, Category: {book[5]}")
            else:
                print("No inventory items found")
                
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_database()