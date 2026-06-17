#!/usr/bin/env python
# Script to add bulk upload route to app.py

with open('app.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Check if already added
if 'def bulk_upload_books' in content:
    print('Bulk upload route already exists')
    exit(0)

# The code to insert
bulk_upload_code = '''

# Bulk Upload Books Route
@app.route("/library/bulk_upload", methods=["GET", "POST"])
@login_required
@admin_required
def bulk_upload_books():
    """Bulk upload books from a CSV file."""
    school_id = session.get("school_id")
    
    if request.method == "POST":
        if "csv_file" not in request.files:
            flash("No file selected.", "danger")
            return redirect(url_for("bulk_upload_books"))
        
        csv_file = request.files["csv_file"]
        if csv_file.filename == "":
            flash("No file selected.", "danger")
            return redirect(url_for("bulk_upload_books"))
        
        # Check file extension
        if not csv_file.filename.lower().endswith(".csv"):
            flash("Please upload a CSV file.", "danger")
            return redirect(url_for("bulk_upload_books"))
        
        import csv
        import io
        
        try:
            # Read CSV content
            stream = io.StringIO(csv_file.stream.read().decode("utf-8"))
            reader = csv.DictReader(stream)
            
            added_count = 0
            skipped_count = 0
            errors = []
            
            for row_num, row in enumerate(reader, start=2):
                title = (row.get("title") or row.get("Title") or "").strip()
                author = (row.get("author") or row.get("Author") or "").strip()
                isbn = (row.get("isbn") or row.get("ISBN") or "").strip() or None
                category = (row.get("category") or row.get("Category") or "").strip() or None
                description = (row.get("description") or row.get("Description") or "").strip() or None
                quantity = (row.get("quantity") or row.get("Quantity") or "1").strip()
                
                if not title or not author:
                    errors.append(f"Row {row_num}: Missing title or author")
                    skipped_count += 1
                    continue
                
                try:
                    quantity = int(quantity)
                    if quantity < 1:
                        quantity = 1
                except ValueError:
                    quantity = 1
                
                existing = query_db(
                    "SELECT id FROM library_books WHERE school_id = ? AND title = ? AND author = ? AND is_active = 1",
                    (school_id, title, author),
                    one=True
                )
                
                if existing:
                    errors.append(f"Row {row_num}: Book '{title}' already exists")
                    skipped_count += 1
                    continue
                
                query_db(
                    "INSERT INTO library_books (school_id, title, author, isbn, category, description, quantity, stock_status) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (school_id, title, author, isbn, category, description, quantity, "available"),
                    commit=True
                )
                added_count += 1
            
            if added_count > 0:
                flash(f"Successfully added {added_count} book(s) to the library.", "success")
            if skipped_count > 0:
                flash(f"Skipped {skipped_count} row(s).", "warning")
            if errors:
                for error in errors[:10]:
                    flash(error, "warning")
            
            return redirect(url_for("library"))
            
        except Exception as e:
            flash(f"Error processing file: {str(e)}", "danger")
            return redirect(url_for("bulk_upload_books"))
    
    return render_template("bulk_upload_books.html")

'''

# Find the insertion point
target = '# Teaching Plan Routes'
if target in content:
    new_content = content.replace(target, bulk_upload_code + target)
    with open('app.py', 'w', encoding='utf-8') as f:
        f.write(new_content)
    print('Successfully added bulk upload route to app.py')
else:
    print('ERROR: Could not find insertion point')
    exit(1)