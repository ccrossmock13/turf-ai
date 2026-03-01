"""
Budget and Purchase Order Tracking module for Greenside AI.

Handles budget management, purchase orders, expense tracking, and financial
analytics for turfgrass operations. Supports both SQLite and PostgreSQL via
the shared db.py layer.
"""

import logging
from datetime import datetime, date

from db import get_db

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_CATEGORIES = [
    'chemical', 'fertilizer', 'seed', 'equipment', 'labor', 'irrigation', 'other'
]
VALID_AREAS = ['greens', 'fairways', 'tees', 'rough', 'all']
VALID_PO_STATUSES = ['draft', 'submitted', 'approved', 'received', 'cancelled']
MONTHS = list(range(1, 13))

# ---------------------------------------------------------------------------
# Table Initialization
# ---------------------------------------------------------------------------

def init_budget_tables():
    """Create all budget-related tables if they do not exist."""
    with get_db() as conn:
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS budgets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                name TEXT NOT NULL,
                fiscal_year INTEGER NOT NULL,
                total_amount REAL NOT NULL DEFAULT 0,
                category TEXT,
                area TEXT DEFAULT 'all',
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS budget_line_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                budget_id INTEGER NOT NULL,
                description TEXT NOT NULL,
                amount REAL NOT NULL DEFAULT 0,
                month INTEGER,
                category TEXT,
                product_name TEXT,
                vendor TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (budget_id) REFERENCES budgets(id) ON DELETE CASCADE
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS purchase_orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                po_number TEXT NOT NULL,
                vendor TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'draft',
                order_date TEXT,
                expected_delivery TEXT,
                actual_delivery TEXT,
                subtotal REAL NOT NULL DEFAULT 0,
                tax REAL NOT NULL DEFAULT 0,
                shipping REAL NOT NULL DEFAULT 0,
                total REAL NOT NULL DEFAULT 0,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS po_line_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                po_id INTEGER NOT NULL,
                product_name TEXT NOT NULL,
                product_id TEXT,
                quantity REAL NOT NULL DEFAULT 0,
                unit TEXT,
                unit_price REAL NOT NULL DEFAULT 0,
                total_price REAL NOT NULL DEFAULT 0,
                budget_id INTEGER,
                notes TEXT,
                FOREIGN KEY (po_id) REFERENCES purchase_orders(id) ON DELETE CASCADE,
                FOREIGN KEY (budget_id) REFERENCES budgets(id)
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                date TEXT NOT NULL,
                amount REAL NOT NULL DEFAULT 0,
                category TEXT,
                description TEXT,
                vendor TEXT,
                po_id INTEGER,
                receipt_url TEXT,
                area TEXT DEFAULT 'all',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (po_id) REFERENCES purchase_orders(id)
            )
        ''')

    logger.info("Budget tables initialized")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _today():
    """Return today's date as YYYY-MM-DD string."""
    return date.today().isoformat()


def _now():
    """Return current timestamp as ISO string."""
    return datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')


def _validate_category(category):
    """Return the category if valid, else None."""
    if category and category.lower() in VALID_CATEGORIES:
        return category.lower()
    return None


def _validate_area(area):
    """Return the area if valid, else 'all'."""
    if area and area.lower() in VALID_AREAS:
        return area.lower()
    return 'all'

def _validate_po_status(status):
    """Return the status if valid, else None."""
    if status and status.lower() in VALID_PO_STATUSES:
        return status.lower()
    return None


def _row_to_dict(row):
    """Convert a database row to a plain dict."""
    if row is None:
        return None
    return dict(row)


def _rows_to_dicts(rows):
    """Convert a list of database rows to a list of dicts."""
    return [dict(r) for r in rows]


def _fiscal_year_bounds(fiscal_year):
    """Return (start_date, end_date) strings for a fiscal year (calendar-based)."""
    return (f'{fiscal_year}-01-01', f'{fiscal_year}-12-31')

# ---------------------------------------------------------------------------
# Budget CRUD
# ---------------------------------------------------------------------------

def create_budget(user_id, data):
    """Create a new budget. Returns the new budget ID.

    Args:
        user_id: Owner user ID.
        data: dict with keys: name, fiscal_year, total_amount, category,
              area, notes, line_items (optional list).

    Returns:
        int: The new budget ID.
    """
    name = data.get('name', 'Untitled Budget')
    fiscal_year = int(data.get('fiscal_year', datetime.utcnow().year))
    total_amount = float(data.get('total_amount', 0))
    category = _validate_category(data.get('category'))
    area = _validate_area(data.get('area'))
    notes = data.get('notes', '')
    now = _now()
    with get_db() as conn:
        cursor = conn.execute('''
            INSERT INTO budgets
                (user_id, name, fiscal_year, total_amount, category, area, notes,
                 created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, name, fiscal_year, total_amount, category, area, notes,
              now, now))
        budget_id = cursor.lastrowid

        # Insert line items if provided
        line_items = data.get('line_items', [])
        for item in line_items:
            conn.execute('''
                INSERT INTO budget_line_items
                    (budget_id, description, amount, month, category,
                     product_name, vendor, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                budget_id,
                item.get('description', ''),
                float(item.get('amount', 0)),
                item.get('month'),
                _validate_category(item.get('category')),
                item.get('product_name'),
                item.get('vendor'),
                now
            ))
    logger.info("Budget created: id=%s user=%s name=%s year=%s",
                budget_id, user_id, name, fiscal_year)
    return budget_id


def update_budget(budget_id, user_id, data):
    """Update an existing budget. Returns True if updated.

    Args:
        budget_id: Budget ID to update.
        user_id: Owner user ID (ownership check).
        data: dict with optional keys: name, fiscal_year, total_amount,
              category, area, notes, line_items.

    Returns:
        bool: True if the budget was found and updated.
    """
    fields = []
    params = []

    if 'name' in data:
        fields.append('name = ?')
        params.append(data['name'])
    if 'fiscal_year' in data:
        fields.append('fiscal_year = ?')
        params.append(int(data['fiscal_year']))
    if 'total_amount' in data:
        fields.append('total_amount = ?')
        params.append(float(data['total_amount']))
    if 'category' in data:
        fields.append('category = ?')
        params.append(_validate_category(data['category']))
    if 'area' in data:
        fields.append('area = ?')
        params.append(_validate_area(data['area']))
    if 'notes' in data:
        fields.append('notes = ?')
        params.append(data['notes'])

    if not fields:
        return False

    fields.append('updated_at = ?')
    params.append(_now())
    params.extend([budget_id, user_id])

    with get_db() as conn:
        cursor = conn.execute(
            f"UPDATE budgets SET {', '.join(fields)} WHERE id = ? AND user_id = ?",
            params
        )
        updated = cursor.rowcount > 0
        # Replace line items if provided
        if 'line_items' in data and updated:
            conn.execute(
                'DELETE FROM budget_line_items WHERE budget_id = ?',
                (budget_id,)
            )
            now = _now()
            for item in data['line_items']:
                conn.execute('''
                    INSERT INTO budget_line_items
                        (budget_id, description, amount, month, category,
                         product_name, vendor, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    budget_id,
                    item.get('description', ''),
                    float(item.get('amount', 0)),
                    item.get('month'),
                    _validate_category(item.get('category')),
                    item.get('product_name'),
                    item.get('vendor'),
                    now
                ))

    if updated:
        logger.info("Budget updated: id=%s user=%s", budget_id, user_id)
    return updated

def delete_budget(budget_id, user_id):
    """Delete a budget and its line items. Returns True if deleted.

    Args:
        budget_id: Budget ID to delete.
        user_id: Owner user ID (ownership check).

    Returns:
        bool: True if the budget was found and deleted.
    """
    with get_db() as conn:
        # Delete line items first (for SQLite without ON DELETE CASCADE support)
        conn.execute(
            'DELETE FROM budget_line_items WHERE budget_id = ?',
            (budget_id,)
        )
        cursor = conn.execute(
            'DELETE FROM budgets WHERE id = ? AND user_id = ?',
            (budget_id, user_id)
        )
        deleted = cursor.rowcount > 0

    if deleted:
        logger.info("Budget deleted: id=%s user=%s", budget_id, user_id)
    return deleted

def get_budgets(user_id, fiscal_year=None):
    """Get all budgets for a user, optionally filtered by fiscal year.

    Args:
        user_id: Owner user ID.
        fiscal_year: Optional fiscal year filter.

    Returns:
        list[dict]: List of budget dicts.
    """
    query = 'SELECT * FROM budgets WHERE user_id = ?'
    params = [user_id]

    if fiscal_year:
        query += ' AND fiscal_year = ?'
        params.append(int(fiscal_year))

    query += ' ORDER BY fiscal_year DESC, name ASC'

    with get_db() as conn:
        cursor = conn.execute(query, params)
        rows = cursor.fetchall()

    return _rows_to_dicts(rows)

def get_budget_by_id(budget_id, user_id):
    """Get a single budget with its line items.

    Args:
        budget_id: Budget ID.
        user_id: Owner user ID (ownership check).

    Returns:
        dict or None: Budget dict with 'line_items' key, or None if not found.
    """
    with get_db() as conn:
        cursor = conn.execute(
            'SELECT * FROM budgets WHERE id = ? AND user_id = ?',
            (budget_id, user_id)
        )
        row = cursor.fetchone()
        if not row:
            return None

        budget = _row_to_dict(row)

        li_cursor = conn.execute(
            'SELECT * FROM budget_line_items WHERE budget_id = ? ORDER BY month, id',
            (budget_id,)
        )
        budget['line_items'] = _rows_to_dicts(li_cursor.fetchall())

    return budget

def get_budget_summary(user_id, fiscal_year):
    """Get budget vs actual spending by category for a fiscal year.

    Returns a dict with per-category budgeted amount, actual spend, remaining,
    and percentage used.

    Args:
        user_id: Owner user ID.
        fiscal_year: The fiscal year to summarize.

    Returns:
        dict: { categories: { category: { budgeted, actual, remaining, pct_used } },
                total_budgeted, total_actual, total_remaining, total_pct_used }
    """
    fiscal_year = int(fiscal_year)
    start_date, end_date = _fiscal_year_bounds(fiscal_year)

    with get_db() as conn:
        # Get budgeted amounts by category
        budget_cursor = conn.execute('''
            SELECT category, SUM(total_amount) as budgeted
            FROM budgets
            WHERE user_id = ? AND fiscal_year = ?
            GROUP BY category
        ''', (user_id, fiscal_year))
        budget_rows = budget_cursor.fetchall()

        # Get actual expenses by category
        expense_cursor = conn.execute('''
            SELECT category, SUM(amount) as actual
            FROM expenses
            WHERE user_id = ? AND date >= ? AND date <= ?
            GROUP BY category
        ''', (user_id, start_date, end_date))
        expense_rows = expense_cursor.fetchall()

    budgeted_map = {}
    for r in budget_rows:
        row = _row_to_dict(r)
        cat = row['category'] or 'other'
        budgeted_map[cat] = float(row['budgeted'] or 0)

    actual_map = {}
    for r in expense_rows:
        row = _row_to_dict(r)
        cat = row['category'] or 'other'
        actual_map[cat] = float(row['actual'] or 0)
    # Merge all categories
    all_cats = set(list(budgeted_map.keys()) + list(actual_map.keys()))
    categories = {}
    total_budgeted = 0.0
    total_actual = 0.0

    for cat in sorted(all_cats):
        budgeted = budgeted_map.get(cat, 0)
        actual = actual_map.get(cat, 0)
        remaining = budgeted - actual
        pct_used = round((actual / budgeted) * 100, 1) if budgeted > 0 else 0
        categories[cat] = {
            'budgeted': round(budgeted, 2),
            'actual': round(actual, 2),
            'remaining': round(remaining, 2),
            'pct_used': pct_used
        }
        total_budgeted += budgeted
        total_actual += actual

    total_remaining = total_budgeted - total_actual
    total_pct = round((total_actual / total_budgeted) * 100, 1) if total_budgeted > 0 else 0

    return {
        'fiscal_year': fiscal_year,
        'categories': categories,
        'total_budgeted': round(total_budgeted, 2),
        'total_actual': round(total_actual, 2),
        'total_remaining': round(total_remaining, 2),
        'total_pct_used': total_pct
    }

# ---------------------------------------------------------------------------
# Purchase Order CRUD
# ---------------------------------------------------------------------------

def _generate_po_number(conn, user_id, year=None):
    """Generate the next PO number for a user in the format PO-YYYY-NNN.

    Args:
        conn: Active database connection.
        user_id: Owner user ID.
        year: Optional year override (defaults to current year).

    Returns:
        str: The generated PO number.
    """
    if year is None:
        year = datetime.utcnow().year

    prefix = f'PO-{year}-'
    cursor = conn.execute(
        "SELECT po_number FROM purchase_orders WHERE user_id = ? AND po_number LIKE ? ORDER BY po_number DESC",
        (user_id, f'{prefix}%')
    )
    row = cursor.fetchone()

    if row:
        last_num = _row_to_dict(row)['po_number']
        try:
            seq = int(last_num.split('-')[-1]) + 1
        except (ValueError, IndexError):
            seq = 1
    else:
        seq = 1

    return f'{prefix}{seq:03d}'

def create_purchase_order(user_id, data):
    """Create a new purchase order with auto-generated PO number.

    Args:
        user_id: Owner user ID.
        data: dict with keys: vendor, status, order_date, expected_delivery,
              notes, tax, shipping, line_items (list of dicts with product_name,
              product_id, quantity, unit, unit_price, budget_id, notes).

    Returns:
        dict: { id, po_number } of the created PO.
    """
    vendor = data.get('vendor', '')
    status = _validate_po_status(data.get('status')) or 'draft'
    order_date = data.get('order_date', _today())
    expected_delivery = data.get('expected_delivery')
    notes = data.get('notes', '')
    now = _now()

    line_items = data.get('line_items', [])

    # Calculate totals from line items
    subtotal = 0.0
    for item in line_items:
        qty = float(item.get('quantity', 0))
        price = float(item.get('unit_price', 0))
        item['_total_price'] = round(qty * price, 2)
        subtotal += item['_total_price']
    tax = float(data.get('tax', 0))
    shipping = float(data.get('shipping', 0))
    total = round(subtotal + tax + shipping, 2)

    with get_db() as conn:
        po_number = _generate_po_number(conn, user_id)

        cursor = conn.execute('''
            INSERT INTO purchase_orders
                (user_id, po_number, vendor, status, order_date, expected_delivery,
                 subtotal, tax, shipping, total, notes, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, po_number, vendor, status, order_date, expected_delivery,
              round(subtotal, 2), round(tax, 2), round(shipping, 2), total,
              notes, now, now))
        po_id = cursor.lastrowid

        for item in line_items:
            conn.execute('''
                INSERT INTO po_line_items
                    (po_id, product_name, product_id, quantity, unit,
                     unit_price, total_price, budget_id, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                po_id,
                item.get('product_name', ''),
                item.get('product_id'),
                float(item.get('quantity', 0)),
                item.get('unit', 'each'),
                float(item.get('unit_price', 0)),
                item['_total_price'],
                item.get('budget_id'),
                item.get('notes')
            ))
    logger.info("Purchase order created: id=%s po=%s user=%s vendor=%s",
                po_id, po_number, user_id, vendor)
    return {'id': po_id, 'po_number': po_number}

def update_purchase_order(po_id, user_id, data):
    """Update an existing purchase order. Returns True if updated.

    Args:
        po_id: Purchase order ID.
        user_id: Owner user ID (ownership check).
        data: dict with optional keys: vendor, order_date, expected_delivery,
              actual_delivery, tax, shipping, notes, status, line_items.

    Returns:
        bool: True if the PO was found and updated.
    """
    fields = []
    params = []

    for key in ['vendor', 'order_date', 'expected_delivery', 'actual_delivery', 'notes']:
        if key in data:
            fields.append(f'{key} = ?')
            params.append(data[key])

    if 'status' in data:
        valid = _validate_po_status(data['status'])
        if valid:
            fields.append('status = ?')
            params.append(valid)

    if 'tax' in data:
        fields.append('tax = ?')
        params.append(float(data['tax']))
    if 'shipping' in data:
        fields.append('shipping = ?')
        params.append(float(data['shipping']))
    with get_db() as conn:
        # Replace line items if provided and recalculate totals
        if 'line_items' in data:
            conn.execute('DELETE FROM po_line_items WHERE po_id = ?', (po_id,))
            subtotal = 0.0
            for item in data['line_items']:
                qty = float(item.get('quantity', 0))
                price = float(item.get('unit_price', 0))
                item_total = round(qty * price, 2)
                subtotal += item_total
                conn.execute('''
                    INSERT INTO po_line_items
                        (po_id, product_name, product_id, quantity, unit,
                         unit_price, total_price, budget_id, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    po_id,
                    item.get('product_name', ''),
                    item.get('product_id'),
                    qty,
                    item.get('unit', 'each'),
                    price,
                    item_total,
                    item.get('budget_id'),
                    item.get('notes')
                ))
            fields.append('subtotal = ?')
            params.append(round(subtotal, 2))
            # Recalculate total
            tax = float(data.get('tax', 0))
            shipping = float(data.get('shipping', 0))

            # If tax/shipping not in data, fetch current values
            if 'tax' not in data or 'shipping' not in data:
                cur = conn.execute(
                    'SELECT tax, shipping FROM purchase_orders WHERE id = ? AND user_id = ?',
                    (po_id, user_id)
                )
                existing = cur.fetchone()
                if existing:
                    ex = _row_to_dict(existing)
                    if 'tax' not in data:
                        tax = float(ex.get('tax', 0))
                    if 'shipping' not in data:
                        shipping = float(ex.get('shipping', 0))

            total = round(subtotal + tax + shipping, 2)
            fields.append('total = ?')
            params.append(total)

        if not fields:
            return False

        fields.append('updated_at = ?')
        params.append(_now())
        params.extend([po_id, user_id])

        cursor = conn.execute(
            f"UPDATE purchase_orders SET {', '.join(fields)} WHERE id = ? AND user_id = ?",
            params
        )
        updated = cursor.rowcount > 0

    if updated:
        logger.info("Purchase order updated: id=%s user=%s", po_id, user_id)
    return updated

def update_po_status(po_id, user_id, status):
    """Update the status of a purchase order. Returns True if updated.

    If status is 'received', also sets actual_delivery to today.

    Args:
        po_id: Purchase order ID.
        user_id: Owner user ID (ownership check).
        status: New status string.

    Returns:
        bool: True if the PO was found and status updated.
    """
    valid_status = _validate_po_status(status)
    if not valid_status:
        logger.warning("Invalid PO status: %s", status)
        return False

    now = _now()
    with get_db() as conn:
        if valid_status == 'received':
            cursor = conn.execute(
                '''UPDATE purchase_orders
                   SET status = ?, actual_delivery = ?, updated_at = ?
                   WHERE id = ? AND user_id = ?''',
                (valid_status, _today(), now, po_id, user_id)
            )
        else:
            cursor = conn.execute(
                '''UPDATE purchase_orders
                   SET status = ?, updated_at = ?
                   WHERE id = ? AND user_id = ?''',
                (valid_status, now, po_id, user_id)
            )
        updated = cursor.rowcount > 0

    if updated:
        logger.info("PO status updated: id=%s status=%s user=%s",
                    po_id, valid_status, user_id)
    return updated

def get_purchase_orders(user_id, status=None, vendor=None):
    """Get purchase orders for a user with optional filters.

    Args:
        user_id: Owner user ID.
        status: Optional status filter.
        vendor: Optional vendor filter (partial match).

    Returns:
        list[dict]: List of purchase order dicts.
    """
    query = 'SELECT * FROM purchase_orders WHERE user_id = ?'
    params = [user_id]

    if status:
        valid = _validate_po_status(status)
        if valid:
            query += ' AND status = ?'
            params.append(valid)

    if vendor:
        query += ' AND vendor LIKE ?'
        params.append(f'%{vendor}%')

    query += ' ORDER BY created_at DESC'

    with get_db() as conn:
        cursor = conn.execute(query, params)
        rows = cursor.fetchall()

    return _rows_to_dicts(rows)

def get_po_by_id(po_id, user_id):
    """Get a single purchase order with its line items.

    Args:
        po_id: Purchase order ID.
        user_id: Owner user ID (ownership check).

    Returns:
        dict or None: PO dict with 'line_items' key, or None if not found.
    """
    with get_db() as conn:
        cursor = conn.execute(
            'SELECT * FROM purchase_orders WHERE id = ? AND user_id = ?',
            (po_id, user_id)
        )
        row = cursor.fetchone()
        if not row:
            return None

        po = _row_to_dict(row)

        li_cursor = conn.execute(
            'SELECT * FROM po_line_items WHERE po_id = ? ORDER BY id',
            (po_id,)
        )
        po['line_items'] = _rows_to_dicts(li_cursor.fetchall())

    return po

# ---------------------------------------------------------------------------
# Expense Tracking
# ---------------------------------------------------------------------------

def log_expense(user_id, data):
    """Log a new expense record. Returns the new expense ID.

    Args:
        user_id: Owner user ID.
        data: dict with keys: date, amount, category, description, vendor,
              po_id, receipt_url, area.

    Returns:
        int: The new expense ID.
    """
    expense_date = data.get('date', _today())
    amount = float(data.get('amount', 0))
    category = _validate_category(data.get('category'))
    description = data.get('description', '')
    vendor = data.get('vendor', '')
    po_id = data.get('po_id')
    receipt_url = data.get('receipt_url')
    area = _validate_area(data.get('area'))
    now = _now()

    with get_db() as conn:
        cursor = conn.execute('''
            INSERT INTO expenses
                (user_id, date, amount, category, description, vendor,
                 po_id, receipt_url, area, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, expense_date, amount, category, description, vendor,
              po_id, receipt_url, area, now))
        expense_id = cursor.lastrowid

    logger.info("Expense logged: id=%s user=%s amount=%.2f category=%s",
                expense_id, user_id, amount, category)
    return expense_id

def get_expenses(user_id, start_date=None, end_date=None, category=None):
    """Get expenses for a user with optional filters.

    Args:
        user_id: Owner user ID.
        start_date: Optional start date (YYYY-MM-DD) inclusive.
        end_date: Optional end date (YYYY-MM-DD) inclusive.
        category: Optional category filter.

    Returns:
        list[dict]: List of expense dicts.
    """
    query = 'SELECT * FROM expenses WHERE user_id = ?'
    params = [user_id]

    if start_date:
        query += ' AND date >= ?'
        params.append(start_date)
    if end_date:
        query += ' AND date <= ?'
        params.append(end_date)
    if category:
        valid = _validate_category(category)
        if valid:
            query += ' AND category = ?'
            params.append(valid)

    query += ' ORDER BY date DESC'

    with get_db() as conn:
        cursor = conn.execute(query, params)
        rows = cursor.fetchall()

    return _rows_to_dicts(rows)

def get_expense_summary(user_id, fiscal_year):
    """Get monthly expense breakdown by category for a fiscal year.

    Args:
        user_id: Owner user ID.
        fiscal_year: The fiscal year to summarize.

    Returns:
        dict: { fiscal_year, months: { 1..12: { category: amount } },
                category_totals: { category: amount }, grand_total }
    """
    fiscal_year = int(fiscal_year)
    start_date, end_date = _fiscal_year_bounds(fiscal_year)

    with get_db() as conn:
        cursor = conn.execute('''
            SELECT date, amount, category
            FROM expenses
            WHERE user_id = ? AND date >= ? AND date <= ?
            ORDER BY date
        ''', (user_id, start_date, end_date))
        rows = cursor.fetchall()

    months = {m: {} for m in MONTHS}
    category_totals = {}
    grand_total = 0.0

    for r in rows:
        row = _row_to_dict(r)
        try:
            month = int(row['date'].split('-')[1])
        except (IndexError, ValueError, AttributeError):
            continue
        cat = row['category'] or 'other'
        amt = float(row['amount'] or 0)

        if month in months:
            months[month][cat] = round(months[month].get(cat, 0) + amt, 2)
        category_totals[cat] = round(category_totals.get(cat, 0) + amt, 2)
        grand_total += amt

    return {
        'fiscal_year': fiscal_year,
        'months': months,
        'category_totals': category_totals,
        'grand_total': round(grand_total, 2)
    }

def get_cost_per_acre(user_id, fiscal_year, area=None):
    """Get cost per acre by area for a fiscal year.

    Uses the profile module to look up acreage per area. Falls back to
    summing expenses without per-acre calculation if profile is unavailable.

    Args:
        user_id: Owner user ID.
        fiscal_year: The fiscal year.
        area: Optional specific area filter.

    Returns:
        dict: { fiscal_year, areas: { area: { total_spent, acreage,
                cost_per_acre } }, overall_total, overall_acreage,
                overall_cost_per_acre }
    """
    fiscal_year = int(fiscal_year)
    start_date, end_date = _fiscal_year_bounds(fiscal_year)

    # Try to get acreage from profile
    acreage_map = {}
    try:
        from profile import get_profile
        profile = get_profile(user_id)
        if profile:
            for area_name in ['greens', 'fairways', 'tees', 'rough']:
                key = f'{area_name}_acreage'
                val = profile.get(key)
                if val:
                    acreage_map[area_name] = float(val)
    except ImportError:
        logger.debug("Profile module not available for acreage lookup")
    query = '''
        SELECT area, SUM(amount) as total_spent
        FROM expenses
        WHERE user_id = ? AND date >= ? AND date <= ?
    '''
    params = [user_id, start_date, end_date]

    if area:
        valid = _validate_area(area)
        if valid and valid != 'all':
            query += ' AND area = ?'
            params.append(valid)

    query += ' GROUP BY area'

    with get_db() as conn:
        cursor = conn.execute(query, params)
        rows = cursor.fetchall()

    areas = {}
    overall_total = 0.0
    overall_acreage = 0.0

    for r in rows:
        row = _row_to_dict(r)
        area_name = row['area'] or 'all'
        total_spent = float(row['total_spent'] or 0)
        acreage = acreage_map.get(area_name, 0)
        cost_per = round(total_spent / acreage, 2) if acreage > 0 else 0
        areas[area_name] = {
            'total_spent': round(total_spent, 2),
            'acreage': acreage,
            'cost_per_acre': cost_per
        }
        overall_total += total_spent
        if area_name != 'all':
            overall_acreage += acreage

    overall_cost = round(overall_total / overall_acreage, 2) if overall_acreage > 0 else 0

    return {
        'fiscal_year': fiscal_year,
        'areas': areas,
        'overall_total': round(overall_total, 2),
        'overall_acreage': round(overall_acreage, 2),
        'overall_cost_per_acre': overall_cost
    }

# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------

def get_budget_vs_actual(user_id, fiscal_year):
    """Detailed budget vs actual comparison by category and month.

    Args:
        user_id: Owner user ID.
        fiscal_year: The fiscal year.

    Returns:
        dict: { fiscal_year, by_category: { category: { budgeted, actual,
                variance, pct_used, monthly: { 1..12: { budgeted, actual } } } },
                totals: { budgeted, actual, variance, pct_used } }
    """
    fiscal_year = int(fiscal_year)
    start_date, end_date = _fiscal_year_bounds(fiscal_year)

    with get_db() as conn:
        # Get budget line items broken down by month and category
        bli_cursor = conn.execute('''
            SELECT bli.month, bli.category AS li_category, bli.amount,
                   b.category AS budget_category
            FROM budget_line_items bli
            JOIN budgets b ON b.id = bli.budget_id
            WHERE b.user_id = ? AND b.fiscal_year = ?
        ''', (user_id, fiscal_year))
        bli_rows = bli_cursor.fetchall()
        # Also get top-level budget amounts by category (for budgets without line items)
        budget_cursor = conn.execute('''
            SELECT b.id, b.category, b.total_amount,
                   (SELECT COUNT(*) FROM budget_line_items WHERE budget_id = b.id) as li_count
            FROM budgets b
            WHERE b.user_id = ? AND b.fiscal_year = ?
        ''', (user_id, fiscal_year))
        budget_rows = budget_cursor.fetchall()

        # Get expenses by month and category
        expense_cursor = conn.execute('''
            SELECT date, amount, category
            FROM expenses
            WHERE user_id = ? AND date >= ? AND date <= ?
        ''', (user_id, start_date, end_date))
        expense_rows = expense_cursor.fetchall()
    # Build budgeted amounts by category and month
    budgeted = {}  # { category: { 'total': X, 'monthly': { 1: Y, ... } } }

    for r in bli_rows:
        row = _row_to_dict(r)
        cat = row.get('li_category') or row.get('budget_category') or 'other'
        month = row.get('month')
        amt = float(row.get('amount', 0))

        if cat not in budgeted:
            budgeted[cat] = {'total': 0.0, 'monthly': {m: 0.0 for m in MONTHS}}
        budgeted[cat]['total'] += amt
        if month and month in MONTHS:
            budgeted[cat]['monthly'][month] += amt

    # For budgets without line items, spread evenly across 12 months
    for r in budget_rows:
        row = _row_to_dict(r)
        if int(row.get('li_count', 0)) > 0:
            continue  # Already handled via line items
        cat = row.get('category') or 'other'
        total = float(row.get('total_amount', 0))
        if cat not in budgeted:
            budgeted[cat] = {'total': 0.0, 'monthly': {m: 0.0 for m in MONTHS}}
        budgeted[cat]['total'] += total
        monthly_amt = round(total / 12, 2)
        for m in MONTHS:
            budgeted[cat]['monthly'][m] += monthly_amt
    # Build actual amounts by category and month
    actual = {}  # { category: { 'total': X, 'monthly': { 1: Y, ... } } }
    for r in expense_rows:
        row = _row_to_dict(r)
        cat = row.get('category') or 'other'
        amt = float(row.get('amount', 0))
        try:
            month = int(row['date'].split('-')[1])
        except (IndexError, ValueError, AttributeError):
            continue

        if cat not in actual:
            actual[cat] = {'total': 0.0, 'monthly': {m: 0.0 for m in MONTHS}}
        actual[cat]['total'] += amt
        if month in MONTHS:
            actual[cat]['monthly'][month] += amt

    # Merge categories
    all_cats = set(list(budgeted.keys()) + list(actual.keys()))
    by_category = {}
    total_budgeted = 0.0
    total_actual = 0.0
    for cat in sorted(all_cats):
        b = budgeted.get(cat, {'total': 0.0, 'monthly': {m: 0.0 for m in MONTHS}})
        a = actual.get(cat, {'total': 0.0, 'monthly': {m: 0.0 for m in MONTHS}})

        cat_budgeted = round(b['total'], 2)
        cat_actual = round(a['total'], 2)
        variance = round(cat_budgeted - cat_actual, 2)
        pct_used = round((cat_actual / cat_budgeted) * 100, 1) if cat_budgeted > 0 else 0

        monthly = {}
        for m in MONTHS:
            monthly[m] = {
                'budgeted': round(b['monthly'].get(m, 0), 2),
                'actual': round(a['monthly'].get(m, 0), 2)
            }

        by_category[cat] = {
            'budgeted': cat_budgeted,
            'actual': cat_actual,
            'variance': variance,
            'pct_used': pct_used,
            'monthly': monthly
        }
        total_budgeted += cat_budgeted
        total_actual += cat_actual

    total_variance = round(total_budgeted - total_actual, 2)
    total_pct = round((total_actual / total_budgeted) * 100, 1) if total_budgeted > 0 else 0
    return {
        'fiscal_year': fiscal_year,
        'by_category': by_category,
        'totals': {
            'budgeted': round(total_budgeted, 2),
            'actual': round(total_actual, 2),
            'variance': total_variance,
            'pct_used': total_pct
        }
    }

def forecast_spending(user_id, fiscal_year):
    """Project end-of-year spending based on year-to-date trends.

    Uses the average monthly spend from months elapsed to project the
    remaining months in the fiscal year.

    Args:
        user_id: Owner user ID.
        fiscal_year: The fiscal year.

    Returns:
        dict: { fiscal_year, ytd_total, months_elapsed, months_remaining,
                avg_monthly, projected_total, by_category: { category:
                { ytd, avg_monthly, projected } }, budget_comparison:
                { total_budgeted, projected_total, projected_variance } }
    """
    fiscal_year = int(fiscal_year)
    start_date, end_date = _fiscal_year_bounds(fiscal_year)
    today = date.today()

    # Determine how many months have elapsed
    if today.year == fiscal_year:
        months_elapsed = today.month
    elif today.year > fiscal_year:
        months_elapsed = 12
    else:
        months_elapsed = 0

    months_remaining = max(0, 12 - months_elapsed)
    with get_db() as conn:
        cursor = conn.execute('''
            SELECT category, SUM(amount) as total
            FROM expenses
            WHERE user_id = ? AND date >= ? AND date <= ?
            GROUP BY category
        ''', (user_id, start_date, end_date))
        rows = cursor.fetchall()

        # Get total budgeted for comparison
        budget_cursor = conn.execute('''
            SELECT SUM(total_amount) as total_budgeted
            FROM budgets
            WHERE user_id = ? AND fiscal_year = ?
        ''', (user_id, fiscal_year))
        budget_row = budget_cursor.fetchone()

    total_budgeted = 0.0
    if budget_row:
        br = _row_to_dict(budget_row)
        total_budgeted = float(br.get('total_budgeted', 0) or 0)

    by_category = {}
    ytd_total = 0.0

    for r in rows:
        row = _row_to_dict(r)
        cat = row['category'] or 'other'
        ytd = float(row['total'] or 0)
        avg_m = round(ytd / months_elapsed, 2) if months_elapsed > 0 else 0
        projected = round(ytd + (avg_m * months_remaining), 2)
        by_category[cat] = {
            'ytd': round(ytd, 2),
            'avg_monthly': avg_m,
            'projected': projected
        }
        ytd_total += ytd

    avg_monthly = round(ytd_total / months_elapsed, 2) if months_elapsed > 0 else 0
    projected_total = round(ytd_total + (avg_monthly * months_remaining), 2)
    projected_variance = round(total_budgeted - projected_total, 2)

    return {
        'fiscal_year': fiscal_year,
        'ytd_total': round(ytd_total, 2),
        'months_elapsed': months_elapsed,
        'months_remaining': months_remaining,
        'avg_monthly': avg_monthly,
        'projected_total': projected_total,
        'by_category': by_category,
        'budget_comparison': {
            'total_budgeted': round(total_budgeted, 2),
            'projected_total': projected_total,
            'projected_variance': projected_variance
        }
    }

def get_product_spend(user_id, fiscal_year):
    """Get total spend grouped by product name for a fiscal year.

    Aggregates from PO line items on received or approved POs.

    Args:
        user_id: Owner user ID.
        fiscal_year: The fiscal year.

    Returns:
        dict: { fiscal_year, products: [ { product_name, total_spent,
                order_count, avg_unit_price } ] }
    """
    fiscal_year = int(fiscal_year)
    start_date, end_date = _fiscal_year_bounds(fiscal_year)

    with get_db() as conn:
        po_cursor = conn.execute('''
            SELECT pli.product_name,
                   SUM(pli.total_price) as total_spent,
                   COUNT(DISTINCT pli.po_id) as order_count,
                   AVG(pli.unit_price) as avg_unit_price
            FROM po_line_items pli
            JOIN purchase_orders po ON po.id = pli.po_id
            WHERE po.user_id = ?
              AND po.order_date >= ? AND po.order_date <= ?
              AND po.status IN ('approved', 'received')
            GROUP BY pli.product_name
            ORDER BY total_spent DESC
        ''', (user_id, start_date, end_date))
        po_rows = po_cursor.fetchall()
    products = []
    for r in po_rows:
        row = _row_to_dict(r)
        products.append({
            'product_name': row['product_name'],
            'total_spent': round(float(row['total_spent'] or 0), 2),
            'order_count': int(row['order_count'] or 0),
            'avg_unit_price': round(float(row['avg_unit_price'] or 0), 2)
        })

    return {
        'fiscal_year': fiscal_year,
        'products': products
    }

def get_vendor_summary(user_id, fiscal_year):
    """Get total spend grouped by vendor for a fiscal year.

    Aggregates from both purchase orders and direct expense records.

    Args:
        user_id: Owner user ID.
        fiscal_year: The fiscal year.

    Returns:
        dict: { fiscal_year, vendors: [ { vendor, total_spent, po_count,
                expense_count, avg_order_value } ] }
    """
    fiscal_year = int(fiscal_year)
    start_date, end_date = _fiscal_year_bounds(fiscal_year)

    with get_db() as conn:
        # PO spend by vendor
        po_cursor = conn.execute('''
            SELECT vendor,
                   SUM(total) as po_total,
                   COUNT(*) as po_count
            FROM purchase_orders
            WHERE user_id = ?
              AND order_date >= ? AND order_date <= ?
              AND status IN ('approved', 'received')
            GROUP BY vendor
        ''', (user_id, start_date, end_date))
        po_rows = po_cursor.fetchall()
        # Expense spend by vendor
        exp_cursor = conn.execute('''
            SELECT vendor,
                   SUM(amount) as exp_total,
                   COUNT(*) as exp_count
            FROM expenses
            WHERE user_id = ?
              AND date >= ? AND date <= ?
              AND vendor IS NOT NULL AND vendor != ''
            GROUP BY vendor
        ''', (user_id, start_date, end_date))
        exp_rows = exp_cursor.fetchall()

    vendor_map = {}

    for r in po_rows:
        row = _row_to_dict(r)
        v = row['vendor']
        if v not in vendor_map:
            vendor_map[v] = {'po_total': 0, 'po_count': 0,
                             'exp_total': 0, 'exp_count': 0}
        vendor_map[v]['po_total'] = float(row['po_total'] or 0)
        vendor_map[v]['po_count'] = int(row['po_count'] or 0)

    for r in exp_rows:
        row = _row_to_dict(r)
        v = row['vendor']
        if v not in vendor_map:
            vendor_map[v] = {'po_total': 0, 'po_count': 0,
                             'exp_total': 0, 'exp_count': 0}
        vendor_map[v]['exp_total'] = float(row['exp_total'] or 0)
        vendor_map[v]['exp_count'] = int(row['exp_count'] or 0)
    vendors = []
    for v, data in vendor_map.items():
        total = data['po_total'] + data['exp_total']
        count = data['po_count'] + data['exp_count']
        avg_order = round(total / count, 2) if count > 0 else 0
        vendors.append({
            'vendor': v,
            'total_spent': round(total, 2),
            'po_count': data['po_count'],
            'expense_count': data['exp_count'],
            'avg_order_value': avg_order
        })

    # Sort by total spent descending
    vendors.sort(key=lambda x: x['total_spent'], reverse=True)

    return {
        'fiscal_year': fiscal_year,
        'vendors': vendors
    }


# ---------------------------------------------------------------------------
# Expense update / delete  (added for feature_routes compatibility)
# ---------------------------------------------------------------------------

def update_expense(user_id, expense_id, data):
    """Update an existing expense record.

    Args:
        user_id: Owner user ID.
        expense_id: Expense ID to update.
        data: dict with optional keys: date, amount, category, description,
              vendor, po_id, receipt_url, area.

    Returns:
        dict: Updated expense record, or None if not found.
    """
    with get_db() as conn:
        cursor = conn.execute(
            'SELECT * FROM expenses WHERE id = ? AND user_id = ?',
            (expense_id, user_id))
        existing = cursor.fetchone()
        if not existing:
            return None

        fields = []
        params = []
        for key in ('date', 'amount', 'category', 'description',
                    'vendor', 'po_id', 'receipt_url', 'area'):
            if key in data:
                val = data[key]
                if key == 'amount':
                    val = float(val)
                elif key == 'category':
                    val = _validate_category(val)
                elif key == 'area':
                    val = _validate_area(val)
                fields.append(f'{key} = ?')
                params.append(val)

        if not fields:
            return _row_to_dict(existing)

        params.extend([expense_id, user_id])
        conn.execute(
            f'UPDATE expenses SET {", ".join(fields)} WHERE id = ? AND user_id = ?',
            params)

    with get_db() as conn:
        cursor = conn.execute(
            'SELECT * FROM expenses WHERE id = ?', (expense_id,))
        row = cursor.fetchone()
    return _row_to_dict(row) if row else None


def delete_expense(user_id, expense_id):
    """Delete an expense record.

    Args:
        user_id: Owner user ID.
        expense_id: Expense ID to delete.

    Returns:
        bool: True if deleted, False if not found.
    """
    with get_db() as conn:
        cursor = conn.execute(
            'DELETE FROM expenses WHERE id = ? AND user_id = ?',
            (expense_id, user_id))
    deleted = cursor.rowcount > 0
    if deleted:
        logger.info("Expense deleted: id=%s user=%s", expense_id, user_id)
    return deleted


def delete_purchase_order(user_id, po_id):
    """Delete a purchase order.

    Args:
        user_id: Owner user ID.
        po_id: Purchase order ID to delete.

    Returns:
        bool: True if deleted, False if not found.
    """
    with get_db() as conn:
        cursor = conn.execute(
            'DELETE FROM purchase_orders WHERE id = ? AND user_id = ?',
            (po_id, user_id))
    deleted = cursor.rowcount > 0
    if deleted:
        logger.info("PO deleted: id=%s user=%s", po_id, user_id)
    return deleted


# Alias so both names work
create_expense = log_expense


def get_line_items(budget_id, user_id):
    """Get line items for a budget."""
    with get_db() as conn:
        # Verify ownership
        budget = conn.execute(
            'SELECT id FROM budgets WHERE id = ? AND user_id = ?',
            (budget_id, user_id)
        ).fetchone()
        if not budget:
            raise ValueError(f"Budget {budget_id} not found")
        rows = conn.execute(
            'SELECT * FROM budget_line_items WHERE budget_id = ? ORDER BY category, description',
            (budget_id,)
        ).fetchall()
    return [dict(r) for r in rows]


def create_line_item(budget_id, user_id, data):
    """Create a line item in a budget."""
    with get_db() as conn:
        budget = conn.execute(
            'SELECT id FROM budgets WHERE id = ? AND user_id = ?',
            (budget_id, user_id)
        ).fetchone()
        if not budget:
            raise ValueError(f"Budget {budget_id} not found")
        cursor = conn.execute(
            '''INSERT INTO budget_line_items (budget_id, category, description, estimated_amount, actual_amount, notes)
               VALUES (?, ?, ?, ?, ?, ?)''',
            (budget_id, data.get('category', ''), data.get('description', ''),
             data.get('estimated_amount', 0), data.get('actual_amount', 0), data.get('notes', ''))
        )
    return {'id': cursor.lastrowid, 'budget_id': budget_id, **data}


def delete_line_item(budget_id, item_id, user_id):
    """Delete a line item from a budget."""
    with get_db() as conn:
        budget = conn.execute(
            'SELECT id FROM budgets WHERE id = ? AND user_id = ?',
            (budget_id, user_id)
        ).fetchone()
        if not budget:
            raise ValueError(f"Budget {budget_id} not found")
        conn.execute(
            'DELETE FROM budget_line_items WHERE id = ? AND budget_id = ?',
            (item_id, budget_id)
        )
    return {'deleted': True}


def get_purchase_order_by_id(po_id, user_id):
    """Get a single purchase order by ID. Alias for get_po_by_id."""
    return get_po_by_id(po_id, user_id)