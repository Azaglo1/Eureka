# Bulk Upload Books Route - to be added to app.py
# This code should be inserted after the serve_cover function

BULK_UPLOAD_CODE = '''

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
            
            for row_num, row in enumerate(reader, start=2):  # Start at 2 to account for header
                title = (row.get("title") or row.get("Title") or "").strip()
                author = (row.get("author") or row.get("Author") or "").strip()
                isbn = (row.get("isbn") or row.get("ISBN") or "").strip() or None
                category = (row.get("category") or row.get("Category") or "").strip() or None
                description = (row.get("description") or row.get("Description") or "").strip() or None
                quantity = (row.get("quantity") or row.get("Quantity") or "1").strip()
                
                # Validate required fields
                if not title or not author:
                    errors.append(f"Row {row_num}: Missing title or author")
                    skipped_count += 1
                    continue
                
                # Validate quantity
                try:
                    quantity = int(quantity)
                    if quantity < 1:
                        quantity = 1
                except ValueError:
                    quantity = 1
                
                # Check if book already exists
                existing = query_db(
                    "SELECT id FROM library_books WHERE school_id = ? AND title = ? AND author = ? AND is_active = 1",
                    (school_id, title, author),
                    one=True
                )
                
                if existing:
                    errors.append(f"Row {row_num}: Book '{title}' already exists")
                    skipped_count += 1
                    continue
                
                # Insert the book
                query_db(
                    "INSERT INTO library_books (school_id, title, author, isbn, category, description, quantity, stock_status) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (school_id, title, author, isbn, category, description, quantity, "available"),
                    commit=True
                )
                added_count += 1
            
            if added_count > 0:
                flash(f"Successfully added {added_count} book(s) to the library.", "success")
            if skipped_count > 0:
                flash(f"Skipped {skipped_count} row(s). Check the error log.", "warning")
            if errors:
                for error in errors[:10]:  # Show first 10 errors
                    flash(error, "warning")
            
            return redirect(url_for("library"))
            
        except Exception as e:
            flash(f"Error processing file: {str(e)}", "danger")
            return redirect(url_for("bulk_upload_books"))
    
    return render_template("bulk_upload_books.html")
'''