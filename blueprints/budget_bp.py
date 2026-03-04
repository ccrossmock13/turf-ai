"""Budget API blueprint."""

import logging

from flask import Blueprint, jsonify, render_template, request

from blueprints.helpers import _user_id

logger = logging.getLogger(__name__)

budget_bp = Blueprint("budget_bp", __name__)


# ====================================================================
# Page Route
# ====================================================================


@budget_bp.route("/budget")
def budget_page():
    return render_template("budget.html")


# ====================================================================
# Budget API
# ====================================================================


@budget_bp.route("/api/budget/budgets", methods=["GET"])
def get_budgets():
    user_id = _user_id()
    year = request.args.get("year", type=int)
    try:
        from budget_tracker import get_budgets as _get_budgets

        budgets = _get_budgets(user_id, fiscal_year=year)
        return jsonify(budgets)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error getting budgets: {e}")
        return jsonify({"error": str(e)}), 500


@budget_bp.route("/api/budget/budgets", methods=["POST"])
def create_budget():
    user_id = _user_id()
    data = request.get_json(force=True)
    try:
        from budget_tracker import create_budget as _create_budget

        budget_id = _create_budget(user_id, data)
        # create_budget returns just an int ID - fetch the full record
        from budget_tracker import get_budget_by_id as _get_budget

        budget = _get_budget(budget_id, user_id)
        return jsonify(budget), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error creating budget: {e}")
        return jsonify({"error": str(e)}), 500


@budget_bp.route("/api/budget/budgets/<int:budget_id>", methods=["PUT"])
def update_budget(budget_id):
    user_id = _user_id()
    data = request.get_json(force=True)
    try:
        from budget_tracker import update_budget as _update_budget

        _update_budget(budget_id, user_id, data)
        # update_budget returns True/False - fetch the updated record
        from budget_tracker import get_budget_by_id as _get_budget

        budget = _get_budget(budget_id, user_id)
        return jsonify(budget)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error updating budget {budget_id}: {e}")
        return jsonify({"error": str(e)}), 500


@budget_bp.route("/api/budget/budgets/<int:budget_id>", methods=["DELETE"])
def delete_budget(budget_id):
    user_id = _user_id()
    try:
        from budget_tracker import delete_budget as _delete_budget

        result = _delete_budget(budget_id, user_id)
        return jsonify(result)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error deleting budget {budget_id}: {e}")
        return jsonify({"error": str(e)}), 500


@budget_bp.route("/api/budget/summary", methods=["GET"])
def get_budget_summary():
    user_id = _user_id()
    year = request.args.get("year", type=int)
    try:
        from budget_tracker import get_budget_summary as _get_summary

        summary = _get_summary(user_id, year)
        return jsonify(summary)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error getting budget summary: {e}")
        return jsonify({"error": str(e)}), 500


@budget_bp.route("/api/budget/purchase-orders", methods=["GET"])
def get_purchase_orders():
    user_id = _user_id()
    status = request.args.get("status")
    vendor = request.args.get("vendor")
    try:
        from budget_tracker import get_purchase_orders as _get_pos

        pos = _get_pos(user_id, status=status, vendor=vendor)
        return jsonify(pos)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error getting purchase orders: {e}")
        return jsonify({"error": str(e)}), 500


@budget_bp.route("/api/budget/purchase-orders", methods=["POST"])
def create_purchase_order():
    user_id = _user_id()
    data = request.get_json(force=True)
    try:
        from budget_tracker import create_purchase_order as _create_po

        po = _create_po(user_id, data)
        return jsonify(po), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error creating purchase order: {e}")
        return jsonify({"error": str(e)}), 500


@budget_bp.route("/api/budget/purchase-orders/<int:po_id>", methods=["GET"])
def get_purchase_order(po_id):
    user_id = _user_id()
    try:
        from budget_tracker import get_purchase_order_by_id as _get_po

        po = _get_po(po_id, user_id)
        return jsonify(po)
    except Exception as e:
        logger.error(f"Error getting purchase order {po_id}: {e}")
        return jsonify({"error": str(e)}), 500


@budget_bp.route("/api/budget/purchase-orders/<int:po_id>", methods=["PUT"])
def update_purchase_order(po_id):
    user_id = _user_id()
    data = request.get_json(force=True)
    try:
        from budget_tracker import update_purchase_order as _update_po

        po = _update_po(po_id, user_id, data)
        return jsonify(po)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error updating purchase order {po_id}: {e}")
        return jsonify({"error": str(e)}), 500


@budget_bp.route("/api/budget/purchase-orders/<int:po_id>", methods=["DELETE"])
def delete_purchase_order(po_id):
    user_id = _user_id()
    try:
        from budget_tracker import delete_purchase_order as _delete_po

        result = _delete_po(user_id, po_id)
        return jsonify(result)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error deleting purchase order {po_id}: {e}")
        return jsonify({"error": str(e)}), 500


@budget_bp.route("/api/budget/purchase-orders/<int:po_id>/status", methods=["POST", "PUT"])
def update_po_status(po_id):
    user_id = _user_id()
    data = request.get_json(force=True)
    try:
        from budget_tracker import update_po_status as _update_po_status

        status = data.get("status", "")
        result = _update_po_status(po_id, user_id, status)
        return jsonify(result)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error updating PO status {po_id}: {e}")
        return jsonify({"error": str(e)}), 500


@budget_bp.route("/api/budget/expenses", methods=["GET"])
def get_expenses():
    user_id = _user_id()
    category = request.args.get("category")
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")
    try:
        from budget_tracker import get_expenses as _get_expenses

        expenses = _get_expenses(user_id, start_date=start_date, end_date=end_date, category=category)
        return jsonify(expenses)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error getting expenses: {e}")
        return jsonify({"error": str(e)}), 500


@budget_bp.route("/api/budget/expenses", methods=["POST"])
def create_expense():
    user_id = _user_id()
    data = request.get_json(force=True)
    try:
        from budget_tracker import log_expense as _create_expense

        expense = _create_expense(user_id, data)
        return jsonify(expense), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error creating expense: {e}")
        return jsonify({"error": str(e)}), 500


@budget_bp.route("/api/budget/expenses/<int:expense_id>", methods=["PUT"])
def update_expense(expense_id):
    user_id = _user_id()
    data = request.get_json(force=True)
    try:
        from budget_tracker import update_expense as _update_expense

        expense = _update_expense(user_id, expense_id, data)
        return jsonify(expense)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error updating expense {expense_id}: {e}")
        return jsonify({"error": str(e)}), 500


@budget_bp.route("/api/budget/expenses/<int:expense_id>", methods=["DELETE"])
def delete_expense(expense_id):
    user_id = _user_id()
    try:
        from budget_tracker import delete_expense as _delete_expense

        result = _delete_expense(user_id, expense_id)
        return jsonify(result)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error deleting expense {expense_id}: {e}")
        return jsonify({"error": str(e)}), 500


@budget_bp.route("/api/budget/cost-per-acre", methods=["GET"])
def get_cost_per_acre():
    user_id = _user_id()
    year = request.args.get("year", type=int)
    area = request.args.get("area")
    try:
        from budget_tracker import get_cost_per_acre as _get_cpa

        result = _get_cpa(user_id, year, area=area)
        return jsonify(result)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error getting cost per acre: {e}")
        return jsonify({"error": str(e)}), 500


@budget_bp.route("/api/budget/vendor-summary", methods=["GET"])
def get_vendor_summary():
    user_id = _user_id()
    year = request.args.get("year", type=int)
    try:
        from budget_tracker import get_vendor_summary as _get_vendor

        result = _get_vendor(user_id, year)
        return jsonify(result)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error getting vendor summary: {e}")
        return jsonify({"error": str(e)}), 500


# --- Budget: Line Items CRUD (Additional routes) ---


@budget_bp.route("/api/budget/budgets/<int:budget_id>/line-items", methods=["GET"])
def get_line_items(budget_id):
    user_id = _user_id()
    try:
        from budget_tracker import get_line_items as _get_items

        items = _get_items(budget_id, user_id)
        return jsonify(items)
    except Exception as e:
        logger.error(f"Error getting line items: {e}")
        return jsonify({"error": str(e)}), 500


@budget_bp.route("/api/budget/budgets/<int:budget_id>/line-items", methods=["POST"])
def create_line_item(budget_id):
    user_id = _user_id()
    data = request.get_json(force=True)
    try:
        from budget_tracker import create_line_item as _create_item

        item = _create_item(budget_id, user_id, data)
        return jsonify(item), 201
    except Exception as e:
        logger.error(f"Error creating line item: {e}")
        return jsonify({"error": str(e)}), 500


@budget_bp.route("/api/budget/budgets/<int:budget_id>/line-items/<int:item_id>", methods=["DELETE"])
def delete_line_item(budget_id, item_id):
    user_id = _user_id()
    try:
        from budget_tracker import delete_line_item as _del_item

        result = _del_item(budget_id, item_id, user_id)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error deleting line item: {e}")
        return jsonify({"error": str(e)}), 500


@budget_bp.route("/api/budget/export", methods=["GET"])
def export_budget():
    """Export budget data as CSV or PDF."""
    user_id = _user_id()
    fmt = request.args.get("format", "csv").lower()
    year = request.args.get("year", type=int)
    try:
        from budget_tracker import get_budgets as _get_budgets

        budgets = _get_budgets(user_id, fiscal_year=year)
        columns = [
            ("name", "Category"),
            ("fiscal_year", "Year"),
            ("total_budget", "Total Budget"),
            ("total_spent", "Total Spent"),
            ("remaining", "Remaining"),
        ]
        from datetime import datetime

        date_str = datetime.now().strftime("%Y-%m-%d")
        if fmt == "pdf":
            from export_service import export_pdf

            return export_pdf(budgets, "Budget Report", columns, f"budget_{date_str}.pdf")
        from export_service import export_csv

        return export_csv(budgets, columns, f"budget_{date_str}.csv")
    except Exception as e:
        logger.error(f"Error exporting budget: {e}")
        return jsonify({"error": str(e)}), 500
