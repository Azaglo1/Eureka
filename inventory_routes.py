from flask import Blueprint, render_template, request, redirect, url_for, flash, session, g
from db_utils import get_db
from functools import wraps

# Create inventory blueprint
inventory_bp = Blueprint('inventory', __name__, url_prefix='/inventory')

def query_db(query, args=(), one=False, commit=False):
    """Query the database and return results."""
    db = get_db()
    cur = db.execute(query, args)
    if commit:
        db.commit()
    rv = cur.fetchall()
    cur.close()
    return (rv[0] if rv else None) if one else rv

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('login'))
        if session.get('role') not in ['admin', 'superadmin']:
            flash('You do not have permission to access this page.', 'danger')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

@inventory_bp.route('/')
@login_required
@admin_required
def inventory():
    """Display inventory management dashboard"""
    user_role = session.get('role')
    user_school_id = session.get('school_id')
    
    # Get filter parameters
    search_query = request.args.get('q', '').strip()
    status_filter = request.args.get('status', '').strip()
    
    # Base query
    query = """
        SELECT * FROM inventory_items
        WHERE is_active = 1
    """
    params = []
    
    # Apply school filter for regular admins
    if user_role != 'superadmin':
        query += " AND school_id = ?"
        params.append(user_school_id)
    
    # Apply search filter
    if search_query:
        query += " AND (name LIKE ? OR description LIKE ?)"
        params.extend([f"%{search_query}%", f"%{search_query}%"])
    
    # Apply status filter
    if status_filter:
        query += " AND status = ?"
        params.append(status_filter)
    
    # Order by name
    query += " ORDER BY name ASC"
    
    inventory_items = query_db(query, params)
    
    # Get statistics
    stats_query = """
        SELECT 
            COUNT(*) as total_items,
            SUM(CASE WHEN status = 'low_stock' THEN 1 ELSE 0 END) as low_stock_count,
            SUM(CASE WHEN status = 'out_of_stock' THEN 1 ELSE 0 END) as out_of_stock_count,
            SUM(CASE WHEN status = 'in_stock' THEN 1 ELSE 0 END) as in_stock_count
        FROM inventory_items
        WHERE is_active = 1
    """
    stats_params = []
    
    if user_role != 'superadmin':
        stats_query += " AND school_id = ?"
        stats_params.append(user_school_id)
    
    stats = query_db(stats_query, stats_params, one=True)
    
    return render_template('inventory/index.html', 
                         inventory_items=inventory_items,
                         stats=stats,
                         search_query=search_query,
                         status_filter=status_filter,
                         user_role=user_role)

@inventory_bp.route('/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_inventory_item():
    """Add a new inventory item"""
    if request.method == 'POST':
        user_school_id = session.get('school_id')
        
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
        quantity = request.form.get('quantity', '0').strip()
        
        # Validate required fields
        if not name:
            flash('Item name is required.', 'warning')
            return redirect(url_for('inventory.add_inventory_item'))
        
        try:
            quantity = int(quantity)
            if quantity < 0:
                raise ValueError()
        except ValueError:
            flash('Quantity must be a valid number.', 'warning')
            return redirect(url_for('inventory.add_inventory_item'))
        
        # Determine status based on quantity
        if quantity == 0:
            status = 'out_of_stock'
        else:
            status = 'in_stock'
        
        # Insert inventory item
        query_db("""
            INSERT INTO inventory_items 
            (name, description, quantity, status, school_id, is_active)
            VALUES (?, ?, ?, ?, ?, 1)
        """, (
            name, description, quantity, status, user_school_id
        ), commit=True)
        
        flash(f'"{name}" has been added to inventory successfully.', 'success')
        return redirect(url_for('inventory.inventory'))
    
    return render_template('inventory/add.html', user_role=session.get('role'))

@inventory_bp.route('/edit/<int:item_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_inventory_item(item_id):
    """Edit an existing inventory item"""
    user_school_id = session.get('school_id')
    user_role = session.get('role')
    
    # Get the item
    query = "SELECT * FROM inventory_items WHERE id = ? AND is_active = 1"
    params = [item_id]
    
    if user_role != 'superadmin':
        query += " AND school_id = ?"
        params.append(user_school_id)
    
    item = query_db(query, params, one=True)
    
    if not item:
        flash('Inventory item not found.', 'danger')
        return redirect(url_for('inventory.inventory'))
    
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
        category = request.form.get('category', '').strip()
        quantity = request.form.get('quantity', '0').strip()
        unit = request.form.get('unit', 'pieces').strip()
        location = request.form.get('location', '').strip()
        supplier = request.form.get('supplier', '').strip()
        reorder_level = request.form.get('reorder_level', '5').strip()
        
        # Validate required fields
        if not name:
            flash('Item name is required.', 'warning')
            return redirect(url_for('inventory.edit_inventory_item', item_id=item_id))
        
        try:
            quantity = int(quantity)
            reorder_level = int(reorder_level)
            if quantity < 0:
                raise ValueError()
        except ValueError:
            flash('Quantity and reorder level must be valid numbers.', 'warning')
            return redirect(url_for('inventory.edit_inventory_item', item_id=item_id))
        
        # Determine status based on quantity and reorder level
        if quantity == 0:
            status = 'out_of_stock'
        elif quantity <= reorder_level:
            status = 'low_stock'
        else:
            status = 'in_stock'
        
        # Update inventory item
        query_db("""
            UPDATE inventory_items 
            SET name = ?, description = ?, category = ?, quantity = ?, unit = ?, 
                location = ?, supplier = ?, reorder_level = ?, status = ?, 
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND school_id = ? AND is_active = 1
        """, (
            name, description, category, quantity, unit, location, supplier, 
            reorder_level, status, item_id, user_school_id
        ), commit=True)
        
        flash(f'"{name}" has been updated successfully.', 'success')
        return redirect(url_for('inventory.inventory'))
    
    # GET request - show form with current data
    # Get existing categories for dropdown
    categories_query = """
        SELECT DISTINCT category FROM inventory_items
        WHERE is_active = 1
    """
    categories_params = []
    
    if user_role != 'superadmin':
        categories_query += " AND school_id = ?"
        categories_params.append(user_school_id)
    
    categories_query += " ORDER BY category ASC"
    categories = query_db(categories_query, categories_params)
    
    return render_template('inventory/edit.html', 
                         item=item,
                         categories=categories,
                         user_role=user_role)

@inventory_bp.route('/delete/<int:item_id>', methods=['POST'])
@login_required
@admin_required
def delete_inventory_item(item_id):
    """Delete an inventory item (soft delete)"""
    user_school_id = session.get('school_id')
    user_role = session.get('role')
    
    # Check if item exists and belongs to user's school
    query = "SELECT name FROM inventory_items WHERE id = ? AND is_active = 1"
    params = [item_id]
    
    if user_role != 'superadmin':
        query += " AND school_id = ?"
        params.append(user_school_id)
    
    item = query_db(query, params, one=True)
    
    if not item:
        flash('Inventory item not found.', 'danger')
        return redirect(url_for('inventory.inventory'))
    
    # Soft delete
    query_db("""
        UPDATE inventory_items 
        SET is_active = 0, updated_at = CURRENT_TIMESTAMP
        WHERE id = ? AND school_id = ? AND is_active = 1
    """, (item_id, user_school_id), commit=True)
    
    flash(f'"{item["name"]}" has been removed from inventory.', 'success')
    return redirect(url_for('inventory.inventory'))

@inventory_bp.route('/update_status/<int:item_id>', methods=['POST'])
@login_required
@admin_required
def update_inventory_status(item_id):
    """Update inventory item status and quantity"""
    user_school_id = session.get('school_id')
    user_role = session.get('role')
    
    quantity = request.form.get('quantity', '').strip()
    status = request.form.get('status', '').strip()
    
    # Validate quantity
    try:
        quantity = int(quantity)
        if quantity < 0:
            raise ValueError()
    except ValueError:
        flash('Quantity must be a valid non-negative number.', 'warning')
        return redirect(url_for('inventory.inventory'))
    
    # Validate status
    valid_statuses = ['in_stock', 'low_stock', 'out_of_stock']
    if status not in valid_statuses:
        flash('Invalid status.', 'warning')
        return redirect(url_for('inventory.inventory'))
    
    # Update item
    query_db("""
        UPDATE inventory_items 
        SET quantity = ?, status = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ? AND school_id = ? AND is_active = 1
    """, (quantity, status, item_id, user_school_id), commit=True)
    
    flash('Inventory item updated successfully.', 'success')
    return redirect(url_for('inventory.inventory'))