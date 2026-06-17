#!/usr/bin/env python3
"""
Script to add sample inventory items to the school inventory system.
This adds common school supplies like markers, dusters, etc.
"""

import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app
from db_utils import get_db

def add_sample_inventory():
    """Add sample inventory items to the database."""
    with app.app_context():
        db = get_db()
        cursor = db.cursor()
        
        # Sample inventory items - common school supplies
        sample_items = [
            {
                'title': 'Whiteboard Marker - Black',
                'author': 'Expo',
                'isbn': 'WM-BLK-001',
                'category': 'School Supplies',
                'quantity': 15,
                'stock_status': 'available',
                'description': 'Low odor whiteboard marker, black color'
            },
            {
                'title': 'Whiteboard Marker - Red',
                'author': 'Expo',
                'isbn': 'WM-RED-002',
                'category': 'School Supplies',
                'quantity': 8,
                'stock_status': 'low',
                'description': 'Low odor whiteboard marker, red color'
            },
            {
                'title': 'Whiteboard Marker - Blue',
                'author': 'Expo',
                'isbn': 'WM-BLU-003',
                'category': 'School Supplies',
                'quantity': 3,
                'stock_status': 'low',
                'description': 'Low odor whiteboard marker, blue color'
            },
            {
                'title': 'Whiteboard Duster',
                'author': 'Prymat',
                'isbn': 'WD-001',
                'category': 'School Supplies',
                'quantity': 5,
                'stock_status': 'available',
                'description': 'Eraser for whiteboards'
            },
            {
                'title': 'Chalk - White (Box of 12)',
                'author': 'Kores',
                'isbn': 'CH-WHT-001',
                'category': 'School Supplies',
                'quantity': 20,
                'stock_status': 'available',
                'description': 'Dustless white chalk, box of 12 pieces'
            },
            {
                'title': 'Chalk - Colored (Box of 12)',
                'author': 'Kores',
                'isbn': 'CH-COL-002',
                'category': 'School Supplies',
                'quantity': 12,
                'stock_status': 'available',
                'description': 'Assorted colored chalk, box of 12 pieces'
            },
            {
                'title': 'Pencil - HB (Pack of 10)',
                'author': 'Faber-Castell',
                'isbn': 'PB-HB-001',
                'category': 'School Supplies',
                'quantity': 25,
                'stock_status': 'available',
                'description': 'Standard HB pencils, pack of 10'
            },
            {
                'title': 'Ballpoint Pen - Blue (Pack of 10)',
                'author': 'Pilot',
                'isbn': 'PN-BLU-001',
                'category': 'School Supplies',
                'quantity': 18,
                'stock_status': 'available',
                'description': 'Blue ballpoint pens, pack of 10'
            },
            {
                'title': 'A4 Paper - Ream (500 sheets)',
                'author': 'Double A',
                'isbn': 'PA-A4-001',
                'category': 'School Supplies',
                'quantity': 10,
                'stock_status': 'available',
                'description': 'Premium A4 copier paper, 500 sheets per ream'
            },
            {
                'title': 'Stapler',
                'author': 'Kangaroo',
                'isbn': 'ST-001',
                'category': 'Office Supplies',
                'quantity': 7,
                'stock_status': 'available',
                'description': 'Standard desktop stapler'
            },
            {
                'title': 'Staple Pins (Box of 1000)',
                'author': 'Kangaroo',
                'isbn': 'SP-001',
                'category': 'Office Supplies',
                'quantity': 30,
                'stock_status': 'available',
                'description': 'Standard staple pins, box of 1000 pieces'
            },
            {
                'title': 'Scissors - 8 inch',
                'author': 'Camel',
                'isbn': 'SC-001',
                'category': 'Office Supplies',
                'quantity': 12,
                'stock_status': 'available',
                'description': '8 inch stainless steel scissors'
            },
            {
                'title': 'Glue Stick - Large',
                'author': 'Fevicol',
                'isbn': 'GL-001',
                'category': 'Office Supplies',
                'quantity': 6,
                'stock_status': 'low',
                'description': 'Large glue stick for paper and cardboard'
            },
            {
                'title': 'Whiteboard Cleaner Spray - 500ml',
                'author': 'Expo',
                'isbn': 'WC-001',
                'category': 'Cleaning Supplies',
                'quantity': 4,
                'stock_status': 'low',
                'description': 'Cleaning solution for whiteboards, 500ml spray bottle'
            },
            {
                'title': 'Permanent Marker - Black',
                'author': 'Sharpie',
                'isbn': 'PM-BLK-001',
                'category': 'Office Supplies',
                'quantity': 2,
                'stock_status': 'out',
                'description': 'Permanent marker for labeling, black color'
            }
        ]
        
        # Get the first school ID to associate items with
        # In a real system, you might want to let user choose or add to all schools
        cursor.execute("SELECT id FROM schools LIMIT 1")
        school_result = cursor.fetchone()
        
        if not school_result:
            print("No schools found in database. Please create a school first.")
            return
        
        # Handle both tuple and dict-like row (e.g., RealDictRow from psycopg2)
        if isinstance(school_result, dict):
            school_id = school_result['id']
        else:
            school_id = school_result[0]
        
        print(f"Adding inventory items to school ID: {school_id}")
        
        added_count = 0
        for item in sample_items:
            # Check if item with this ISBN already exists for this school
            cursor.execute(
                "SELECT id FROM library_books WHERE isbn = ? AND school_id = ? AND is_active = 1",
                (item['isbn'], school_id)
            )
            existing = cursor.fetchone()
            
            if existing:
                print(f"Item with ISBN {item['isbn']} already exists, skipping...")
                continue
            
            # Insert the inventory item
            cursor.execute("""
                INSERT INTO library_books 
                (title, author, isbn, category, school_id, quantity, stock_status, is_active, description)
                VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?)
            """, (
                item['title'],
                item['author'],
                item['isbn'],
                item['category'],
                school_id,
                item['quantity'],
                item['stock_status'],
                item['description']
            ))
            
            print(f"Added: {item['title']} (ISBN: {item['isbn']}) - Quantity: {item['quantity']}, Status: {item['stock_status']}")
            added_count += 1
        
        db.commit()
        print(f"\nSuccessfully added {added_count} sample inventory items to school ID {school_id}")
        print("You can now view these items in the Inventory section of the admin dashboard.")

if __name__ == "__main__":
    add_sample_inventory()