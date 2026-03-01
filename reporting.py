"""
Reporting and Compliance Engine for Greenside AI.

Generates comprehensive superintendent reports, green committee summaries,
annual reviews, pesticide compliance reports, and state-format exports.
Tracks compliance records for pesticide applications, worker protection,
storage inspections, disposal, and calibration.

Database: Uses get_db() context manager from db.py (SQLite/PostgreSQL).
"""

import csv
import io
import json
import logging
from calendar import monthrange
from datetime import datetime, date

from db import get_db

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_REPORT_TYPES = (
    'monthly_super', 'quarterly', 'annual',
    'green_committee', 'pesticide_compliance',
    'water_usage', 'custom',
)

VALID_REPORT_FORMATS = ('json', 'html')
VALID_REPORT_STATUSES = ('draft', 'final')

VALID_COMPLIANCE_RECORD_TYPES = (
    'pesticide_application', 'worker_protection',
    'storage_inspection', 'disposal', 'calibration',
)

MONTH_NAMES = [
    '', 'January', 'February', 'March', 'April', 'May', 'June',
    'July', 'August', 'September', 'October', 'November', 'December',
]


# ---------------------------------------------------------------------------
# Table Initialization
# ---------------------------------------------------------------------------

def init_reporting_tables():
    """Create reports and compliance_records tables if they do not exist."""
    with get_db() as conn:
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                report_type TEXT NOT NULL,
                title TEXT NOT NULL,
                date_range_start TEXT,
                date_range_end TEXT,
                content_json TEXT,
                format TEXT NOT NULL DEFAULT 'json',
                status TEXT NOT NULL DEFAULT 'draft',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_reports_user ON reports(user_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_reports_type ON reports(user_id, report_type)')

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS compliance_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                record_type TEXT NOT NULL,
                date TEXT NOT NULL,
                description TEXT,
                applicator_name TEXT,
                applicator_license TEXT,
                product_name TEXT,
                epa_reg_number TEXT,
                target_pest TEXT,
                area_treated TEXT,
                area_sqft REAL,
                rate_applied TEXT,
                rate_unit TEXT,
                wind_speed REAL,
                temperature REAL,
                rei_hours REAL,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_compliance_user ON compliance_records(user_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_compliance_type ON compliance_records(user_id, record_type)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_compliance_date ON compliance_records(user_id, date)')

    logger.info("Reporting tables initialized successfully")


# ---------------------------------------------------------------------------
# Internal data-aggregation helpers
# ---------------------------------------------------------------------------

def _date_range_for_month(year, month):
    """Return (start, end) date strings for a given year/month."""
    _, last_day = monthrange(year, month)
    return f"{year}-{month:02d}-01", f"{year}-{month:02d}-{last_day:02d}"


def _date_range_for_year(year):
    """Return (start, end) date strings for a full calendar year."""
    return f"{year}-01-01", f"{year}-12-31"


def _fetch_spray_applications(conn, user_id, start_date, end_date):
    """Fetch spray_applications rows within a date range."""
    cursor = conn.execute(
        'SELECT * FROM spray_applications WHERE user_id = ? AND date >= ? AND date <= ? ORDER BY date ASC',
        (user_id, start_date, end_date))
    rows = cursor.fetchall()
    results = []
    for row in rows:
        r = dict(row)
        for json_field in ('nutrients_applied', 'products_json'):
            if r.get(json_field):
                try:
                    r[json_field] = json.loads(r[json_field])
                except (json.JSONDecodeError, TypeError):
                    r[json_field] = None
        results.append(r)
    return results


def _fetch_scouting_reports(conn, user_id, start_date, end_date):
    """Fetch scouting_reports rows within a date range."""
    cursor = conn.execute(
        'SELECT * FROM scouting_reports WHERE user_id = ? AND scout_date >= ? AND scout_date <= ? ORDER BY scout_date ASC',
        (user_id, start_date, end_date))
    return [dict(r) for r in cursor.fetchall()]


def _fetch_expenses(conn, user_id, start_date, end_date):
    """Fetch expense rows within a date range."""
    try:
        cursor = conn.execute(
            'SELECT * FROM expenses WHERE user_id = ? AND date >= ? AND date <= ? ORDER BY date ASC',
            (user_id, start_date, end_date))
        return [dict(r) for r in cursor.fetchall()]
    except Exception:
        return []


def _fetch_budgets(conn, user_id, year):
    """Fetch budget rows for a fiscal year."""
    try:
        cursor = conn.execute('SELECT * FROM budgets WHERE user_id = ? AND fiscal_year = ?', (user_id, year))
        return [dict(r) for r in cursor.fetchall()]
    except Exception:
        return []


def _fetch_budget_line_items(conn, budget_id):
    """Fetch line items for a budget."""
    try:
        cursor = conn.execute('SELECT * FROM budget_line_items WHERE budget_id = ? ORDER BY month ASC', (budget_id,))
        return [dict(r) for r in cursor.fetchall()]
    except Exception:
        return []


def _aggregate_nutrients(applications):
    """Aggregate N/P2O5/K2O totals from a list of spray application dicts.
    Returns dict keyed by area with per-nutrient totals.
    """
    nutrient_keys = ['N', 'P2O5', 'K2O']
    by_area = {}
    for app in applications:
        area = app.get('area', 'unknown')
        if area not in by_area:
            by_area[area] = {k: 0.0 for k in nutrient_keys}
        if app.get('products_json') and isinstance(app['products_json'], list):
            for mix_product in app['products_json']:
                nutrients = mix_product.get('nutrients_applied')
                if nutrients:
                    for key in nutrient_keys:
                        n_data = nutrients.get(key)
                        if isinstance(n_data, dict):
                            by_area[area][key] += n_data.get('total', 0)
                        elif isinstance(n_data, (int, float)):
                            by_area[area][key] += n_data
        else:
            nutrients = app.get('nutrients_applied')
            if nutrients:
                for key in nutrient_keys:
                    n_data = nutrients.get(key)
                    if isinstance(n_data, dict):
                        by_area[area][key] += n_data.get('total', 0)
                    elif isinstance(n_data, (int, float)):
                        by_area[area][key] += n_data
    for area in by_area:
        for key in nutrient_keys:
            by_area[area][key] = round(by_area[area][key], 2)
    return by_area


def _summarize_scouting(reports):
    """Produce scouting summary from a list of scouting report dicts."""
    new_issues, resolved, ongoing = [], [], []
    for r in reports:
        status = (r.get('status') or 'open').lower()
        entry = {
            'id': r.get('id'), 'date': r.get('scout_date'), 'area': r.get('area'),
            'issue_type': r.get('issue_type'), 'severity': r.get('severity'),
            'diagnosis': r.get('diagnosis'), 'status': status,
        }
        if status == 'resolved':
            resolved.append(entry)
        elif status == 'open':
            new_issues.append(entry)
        else:
            ongoing.append(entry)
    return {
        'new_count': len(new_issues), 'resolved_count': len(resolved),
        'ongoing_count': len(ongoing), 'new_issues': new_issues,
        'resolved': resolved, 'ongoing': ongoing,
    }


def _summarize_budget(budgets, expenses, line_items_by_budget):
    """Build budget summary comparing budgeted vs actual spend."""
    budgeted_by_category = {}
    for b in budgets:
        cat = b.get('category') or 'general'
        budgeted_by_category.setdefault(cat, 0.0)
        budgeted_by_category[cat] += b.get('total_amount', 0)
    spent_by_category = {}
    for e in expenses:
        cat = e.get('category') or 'general'
        spent_by_category.setdefault(cat, 0.0)
        spent_by_category[cat] += e.get('amount', 0)
    all_categories = sorted(set(list(budgeted_by_category.keys()) + list(spent_by_category.keys())))
    breakdown = []
    total_budgeted = 0.0
    total_spent = 0.0
    for cat in all_categories:
        budgeted = budgeted_by_category.get(cat, 0)
        spent = spent_by_category.get(cat, 0)
        total_budgeted += budgeted
        total_spent += spent
        breakdown.append({
            'category': cat, 'budgeted': round(budgeted, 2), 'spent': round(spent, 2),
            'remaining': round(budgeted - spent, 2),
            'pct_used': round((spent / budgeted * 100), 1) if budgeted > 0 else 0,
        })
    return {
        'total_budgeted': round(total_budgeted, 2), 'total_spent': round(total_spent, 2),
        'total_remaining': round(total_budgeted - total_spent, 2),
        'pct_used': round((total_spent / total_budgeted * 100), 1) if total_budgeted > 0 else 0,
        'by_category': breakdown,
    }


def _parse_wind_speed(wind_str):
    """Extract numeric wind speed from a string like '10 mph'."""
    if not wind_str:
        return 0
    try:
        return float(str(wind_str).split()[0].rstrip('mph'))
    except (ValueError, IndexError):
        return 0


# ---------------------------------------------------------------------------
# Report Generators
# ---------------------------------------------------------------------------

def generate_monthly_report(user_id, year, month):
    """Generate a comprehensive monthly superintendent report."""
    if month < 1 or month > 12:
        raise ValueError(f"Invalid month: {month}")
    start_date, end_date = _date_range_for_month(year, month)
    month_name = MONTH_NAMES[month]
    title = f"Monthly Superintendent Report - {month_name} {year}"

    with get_db() as conn:
        applications = _fetch_spray_applications(conn, user_id, start_date, end_date)
        scouting = _fetch_scouting_reports(conn, user_id, start_date, end_date)
        expenses = _fetch_expenses(conn, user_id, start_date, end_date)
        budgets = _fetch_budgets(conn, user_id, year)
        line_items_by_budget = {}
        for b in budgets:
            line_items_by_budget[b['id']] = _fetch_budget_line_items(conn, b['id'])

    # Weather summary from spray application weather fields
    temps = [a['weather_temp'] for a in applications if a.get('weather_temp') is not None]
    weather_summary = {
        'avg_temp': round(sum(temps) / len(temps), 1) if temps else None,
        'min_temp': min(temps) if temps else None,
        'max_temp': max(temps) if temps else None,
        'application_days': len(set(a['date'] for a in applications)),
    }

    # Spray application summary
    spray_summary = []
    for app in applications:
        entry = {
            'date': app['date'], 'area': app['area'], 'product_name': app['product_name'],
            'product_category': app.get('product_category'), 'rate': app['rate'],
            'rate_unit': app['rate_unit'], 'area_acreage': app.get('area_acreage'),
            'total_product': app.get('total_product'), 'total_product_unit': app.get('total_product_unit'),
            'weather_temp': app.get('weather_temp'), 'weather_wind': app.get('weather_wind'),
            'notes': app.get('notes'),
        }
        if app.get('products_json') and isinstance(app['products_json'], list):
            entry['tank_mix_products'] = [p.get('product_name', '') for p in app['products_json']]
        spray_summary.append(entry)

    nutrient_summary = _aggregate_nutrients(applications)
    scouting_summary = _summarize_scouting(scouting)
    month_expenses = [e for e in expenses if e.get('date', '').startswith(f"{year}-{month:02d}")]
    budget_summary = _summarize_budget(budgets, month_expenses, line_items_by_budget)

    products_by_category = {}
    for app in applications:
        cat = app.get('product_category', 'other')
        products_by_category.setdefault(cat, [])
        products_by_category[cat].append(app['product_name'])
    for cat in products_by_category:
        products_by_category[cat] = sorted(set(products_by_category[cat]))

    content = {
        'report_type': 'monthly_super', 'year': year, 'month': month, 'month_name': month_name,
        'date_range': {'start': start_date, 'end': end_date},
        'weather_summary': weather_summary, 'spray_applications': spray_summary,
        'spray_count': len(spray_summary), 'products_by_category': products_by_category,
        'nutrient_summary': nutrient_summary, 'scouting': scouting_summary, 'budget': budget_summary,
    }
    report_id = _save_report_record(user_id, 'monthly_super', title, start_date, end_date, content)
    content['report_id'] = report_id
    logger.info(f"Monthly report generated: {title} (user={user_id}, sprays={len(spray_summary)}, scouting={len(scouting)})")
    return content


def generate_green_committee_report(user_id, year, month):
    """Generate an executive summary for the green committee / board."""
    if month < 1 or month > 12:
        raise ValueError(f"Invalid month: {month}")
    start_date, end_date = _date_range_for_month(year, month)
    month_name = MONTH_NAMES[month]
    title = f"Green Committee Report - {month_name} {year}"

    with get_db() as conn:
        applications = _fetch_spray_applications(conn, user_id, start_date, end_date)
        scouting = _fetch_scouting_reports(conn, user_id, start_date, end_date)
        expenses = _fetch_expenses(conn, user_id, start_date, end_date)
        budgets = _fetch_budgets(conn, user_id, year)
        line_items_by_budget = {}
        for b in budgets:
            line_items_by_budget[b['id']] = _fetch_budget_line_items(conn, b['id'])

    open_issues = [r for r in scouting if (r.get('status') or '').lower() in ('open', 'monitoring')]
    resolved_issues = [r for r in scouting if (r.get('status') or '').lower() == 'resolved']

    conditions_overview = {
        'total_applications': len(applications), 'open_issues': len(open_issues),
        'resolved_issues': len(resolved_issues),
        'areas_treated': sorted(set(a['area'] for a in applications)) if applications else [],
    }

    accomplishments = []
    for r in resolved_issues:
        accomplishments.append(f"Resolved {r.get('issue_type', 'issue')} on {r.get('area', 'course')} ({r.get('scout_date', 'N/A')})")
    categories_used = {}
    for app in applications:
        cat = app.get('product_category', 'other')
        categories_used[cat] = categories_used.get(cat, 0) + 1
    for cat, count in sorted(categories_used.items()):
        accomplishments.append(f"{count} {cat} application(s) completed")

    upcoming_plans = []
    for r in open_issues:
        follow_up = r.get('follow_up_date')
        plan = f"Monitor {r.get('issue_type', 'issue')} on {r.get('area', 'course')}"
        if follow_up:
            plan += f" (follow-up: {follow_up})"
        upcoming_plans.append(plan)

    month_expenses = [e for e in expenses if e.get('date', '').startswith(f"{year}-{month:02d}")]
    budget_summary = _summarize_budget(budgets, month_expenses, line_items_by_budget)

    temps = [a['weather_temp'] for a in applications if a.get('weather_temp') is not None]
    weather_impact = {
        'spray_days': len(set(a['date'] for a in applications)),
        'avg_temp': round(sum(temps) / len(temps), 1) if temps else None,
        'high_wind_days': len([a for a in applications if a.get('weather_wind') and _parse_wind_speed(a['weather_wind']) > 10]),
    }

    issues_and_resolutions = []
    for r in scouting:
        issues_and_resolutions.append({
            'date': r.get('scout_date'), 'area': r.get('area'), 'issue_type': r.get('issue_type'),
            'severity': r.get('severity'), 'status': r.get('status'), 'treatment': r.get('treatment_applied'),
        })

    content = {
        'report_type': 'green_committee', 'year': year, 'month': month, 'month_name': month_name,
        'date_range': {'start': start_date, 'end': end_date},
        'conditions_overview': conditions_overview, 'accomplishments': accomplishments,
        'upcoming_plans': upcoming_plans,
        'budget_summary': {'total_budgeted': budget_summary['total_budgeted'], 'total_spent': budget_summary['total_spent'], 'pct_used': budget_summary['pct_used']},
        'weather_impact': weather_impact, 'issues_and_resolutions': issues_and_resolutions,
    }
    report_id = _save_report_record(user_id, 'green_committee', title, start_date, end_date, content)
    content['report_id'] = report_id
    logger.info(f"Green committee report generated: {title} (user={user_id})")
    return content


def generate_annual_report(user_id, year):
    """Generate a year-in-review annual report."""
    start_date, end_date = _date_range_for_year(year)
    title = f"Annual Report - {year}"

    with get_db() as conn:
        applications = _fetch_spray_applications(conn, user_id, start_date, end_date)
        scouting = _fetch_scouting_reports(conn, user_id, start_date, end_date)
        expenses = _fetch_expenses(conn, user_id, start_date, end_date)
        budgets = _fetch_budgets(conn, user_id, year)
        line_items_by_budget = {}
        for b in budgets:
            line_items_by_budget[b['id']] = _fetch_budget_line_items(conn, b['id'])
        prev_start, prev_end = _date_range_for_year(year - 1)
        prev_applications = _fetch_spray_applications(conn, user_id, prev_start, prev_end)
        prev_expenses = _fetch_expenses(conn, user_id, prev_start, prev_end)
        prev_scouting = _fetch_scouting_reports(conn, user_id, prev_start, prev_end)

    monthly_summaries = []
    for m in range(1, 13):
        m_start, m_end = _date_range_for_month(year, m)
        m_apps = [a for a in applications if m_start <= a['date'] <= m_end]
        m_scout = [s for s in scouting if m_start <= s.get('scout_date', '') <= m_end]
        m_expenses = [e for e in expenses if e.get('date', '').startswith(f"{year}-{m:02d}")]
        monthly_summaries.append({
            'month': m, 'month_name': MONTH_NAMES[m],
            'applications_count': len(m_apps), 'scouting_reports_count': len(m_scout),
            'total_expenses': round(sum(e.get('amount', 0) for e in m_expenses), 2),
            'products_used': sorted(set(a['product_name'] for a in m_apps)),
        })

    chemical_apps = [a for a in applications if a.get('product_category') != 'fertilizer']
    fertilizer_apps = [a for a in applications if a.get('product_category') == 'fertilizer']
    total_chemicals = {'application_count': len(chemical_apps), 'products_used': sorted(set(a['product_name'] for a in chemical_apps))}
    total_fertilizer = {'application_count': len(fertilizer_apps), 'products_used': sorted(set(a['product_name'] for a in fertilizer_apps)), 'nutrients': _aggregate_nutrients(fertilizer_apps)}
    budget_perf = _summarize_budget(budgets, expenses, line_items_by_budget)

    prev_total_spent = round(sum(e.get('amount', 0) for e in prev_expenses), 2)
    yoy_comparison = {
        'current_year': year, 'previous_year': year - 1,
        'current_applications': len(applications), 'previous_applications': len(prev_applications),
        'current_scouting': len(scouting), 'previous_scouting': len(prev_scouting),
        'current_spend': budget_perf['total_spent'], 'previous_spend': prev_total_spent,
        'spend_change_pct': round(((budget_perf['total_spent'] - prev_total_spent) / prev_total_spent * 100), 1) if prev_total_spent > 0 else 0,
    }

    content = {
        'report_type': 'annual', 'year': year, 'date_range': {'start': start_date, 'end': end_date},
        'monthly_summaries': monthly_summaries, 'total_chemicals': total_chemicals,
        'total_fertilizer': total_fertilizer, 'nutrient_totals': _aggregate_nutrients(applications),
        'budget_performance': budget_perf, 'yoy_comparison': yoy_comparison,
        'total_applications': len(applications), 'total_scouting_reports': len(scouting),
    }
    report_id = _save_report_record(user_id, 'annual', title, start_date, end_date, content)
    content['report_id'] = report_id
    logger.info(f"Annual report generated: {title} (user={user_id}, apps={len(applications)}, expenses={len(expenses)})")
    return content


def generate_pesticide_compliance_report(user_id, year):
    """Generate a regulatory pesticide compliance report for the year."""
    start_date, end_date = _date_range_for_year(year)
    title = f"Pesticide Compliance Report - {year}"

    with get_db() as conn:
        applications = _fetch_spray_applications(conn, user_id, start_date, end_date)
        cursor = conn.execute(
            'SELECT * FROM compliance_records WHERE user_id = ? AND record_type = ? AND date >= ? AND date <= ? ORDER BY date ASC',
            (user_id, 'pesticide_application', start_date, end_date))
        compliance_rows = [dict(r) for r in cursor.fetchall()]

    application_records = []
    for app in applications:
        if app.get('product_category') == 'fertilizer':
            continue
        record = {
            'date': app['date'], 'product_name': app['product_name'],
            'product_category': app.get('product_category'), 'rate': app['rate'],
            'rate_unit': app['rate_unit'], 'area': app['area'],
            'area_acreage': app.get('area_acreage'), 'total_product': app.get('total_product'),
            'total_product_unit': app.get('total_product_unit'),
            'weather_temp': app.get('weather_temp'), 'weather_wind': app.get('weather_wind'),
            'weather_conditions': app.get('weather_conditions'), 'notes': app.get('notes'),
        }
        if app.get('products_json') and isinstance(app['products_json'], list):
            record['tank_mix_products'] = [{'product_name': p.get('product_name'), 'rate': p.get('rate'), 'rate_unit': p.get('rate_unit')} for p in app['products_json']]
        application_records.append(record)

    compliance_details = []
    for cr in compliance_rows:
        compliance_details.append({
            'date': cr['date'], 'product_name': cr.get('product_name'),
            'epa_reg_number': cr.get('epa_reg_number'), 'applicator_name': cr.get('applicator_name'),
            'applicator_license': cr.get('applicator_license'), 'target_pest': cr.get('target_pest'),
            'area_treated': cr.get('area_treated'), 'area_sqft': cr.get('area_sqft'),
            'rate_applied': cr.get('rate_applied'), 'rate_unit': cr.get('rate_unit'),
            'wind_speed': cr.get('wind_speed'), 'temperature': cr.get('temperature'),
            'rei_hours': cr.get('rei_hours'), 'description': cr.get('description'),
        })

    rei_issues = []
    for cr in compliance_rows:
        rei = cr.get('rei_hours')
        if rei is not None and rei <= 0:
            rei_issues.append({'date': cr['date'], 'product': cr.get('product_name'), 'rei_hours': rei, 'issue': 'REI hours recorded as zero or negative'})

    applicators = {}
    for cr in compliance_rows:
        name = cr.get('applicator_name')
        if name:
            if name not in applicators:
                applicators[name] = {'license': cr.get('applicator_license'), 'application_count': 0, 'products_applied': set()}
            applicators[name]['application_count'] += 1
            if cr.get('product_name'):
                applicators[name]['products_applied'].add(cr['product_name'])
    for name in applicators:
        applicators[name]['products_applied'] = sorted(applicators[name]['products_applied'])

    content = {
        'report_type': 'pesticide_compliance', 'year': year,
        'date_range': {'start': start_date, 'end': end_date},
        'application_records': application_records, 'compliance_details': compliance_details,
        'total_pesticide_applications': len(application_records),
        'total_compliance_records': len(compliance_details),
        'rei_issues': rei_issues, 'applicators': applicators,
    }
    report_id = _save_report_record(user_id, 'pesticide_compliance', title, start_date, end_date, content)
    content['report_id'] = report_id
    logger.info(f"Pesticide compliance report generated: {title} (user={user_id}, apps={len(application_records)}, compliance={len(compliance_details)})")
    return content


# ---------------------------------------------------------------------------
# Compliance Record CRUD
# ---------------------------------------------------------------------------

def log_compliance_record(user_id, data):
    """Create a new compliance record. Returns the record ID."""
    record_type = data.get('record_type', '')
    if record_type not in VALID_COMPLIANCE_RECORD_TYPES:
        raise ValueError(f"Invalid record_type '{record_type}'. Must be one of {VALID_COMPLIANCE_RECORD_TYPES}")
    record_date = data.get('date')
    if not record_date:
        raise ValueError("date is required")

    with get_db() as conn:
        cursor = conn.execute("""
            INSERT INTO compliance_records (
                user_id, record_type, date, description, applicator_name, applicator_license,
                product_name, epa_reg_number, target_pest, area_treated, area_sqft,
                rate_applied, rate_unit, wind_speed, temperature, rei_hours, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            user_id, record_type, record_date, data.get('description'),
            data.get('applicator_name'), data.get('applicator_license'),
            data.get('product_name'), data.get('epa_reg_number'),
            data.get('target_pest'), data.get('area_treated'), data.get('area_sqft'),
            data.get('rate_applied'), data.get('rate_unit'),
            data.get('wind_speed'), data.get('temperature'), data.get('rei_hours'), data.get('notes'),
        ))
        record_id = cursor.lastrowid
    logger.info(f"Compliance record created: {record_id} type={record_type} (user={user_id})")
    return record_id


def get_compliance_records(user_id, record_type=None, year=None):
    """Retrieve compliance records with optional filters."""
    query = 'SELECT * FROM compliance_records WHERE user_id = ?'
    params = [user_id]
    if record_type:
        if record_type not in VALID_COMPLIANCE_RECORD_TYPES:
            raise ValueError(f"Invalid record_type '{record_type}'")
        query += ' AND record_type = ?'
        params.append(record_type)
    if year:
        query += ' AND date LIKE ?'
        params.append(f'{year}-%')
    query += ' ORDER BY date DESC'
    with get_db() as conn:
        cursor = conn.execute(query, params)
        rows = cursor.fetchall()
    return [dict(r) for r in rows]


def check_compliance_gaps(user_id, year):
    """Identify missing or incomplete compliance records for the year."""
    start_date, end_date = _date_range_for_year(year)
    with get_db() as conn:
        applications = _fetch_spray_applications(conn, user_id, start_date, end_date)
        cursor = conn.execute('SELECT * FROM compliance_records WHERE user_id = ? AND date >= ? AND date <= ?', (user_id, start_date, end_date))
        compliance = [dict(r) for r in cursor.fetchall()]

    compliance_dates_products = set()
    for cr in compliance:
        compliance_dates_products.add((cr.get('date'), (cr.get('product_name') or '').lower()))

    missing_compliance = []
    for app in applications:
        if app.get('product_category') == 'fertilizer':
            continue
        key = (app['date'], app['product_name'].lower())
        if key not in compliance_dates_products:
            missing_compliance.append({'date': app['date'], 'product_name': app['product_name'], 'area': app['area'], 'issue': 'No compliance record found for this application'})

    incomplete_records = []
    required_fields = ['applicator_name', 'applicator_license', 'product_name']
    for cr in compliance:
        if cr.get('record_type') != 'pesticide_application':
            continue
        missing_fields = [f for f in required_fields if not cr.get(f)]
        if missing_fields:
            incomplete_records.append({'record_id': cr['id'], 'date': cr['date'], 'product_name': cr.get('product_name'), 'missing_fields': missing_fields})

    calibration_records = [cr for cr in compliance if cr.get('record_type') == 'calibration']
    last_calibration = calibration_records[-1]['date'] if calibration_records else None

    storage_records = [cr for cr in compliance if cr.get('record_type') == 'storage_inspection']
    quarters_covered = set()
    for sr in storage_records:
        try:
            m = int(sr['date'].split('-')[1])
            quarters_covered.add((m - 1) // 3 + 1)
        except (IndexError, ValueError):
            pass
    missing_quarters = [q for q in [1, 2, 3, 4] if q not in quarters_covered]

    return {
        'year': year,
        'total_pesticide_applications': len([a for a in applications if a.get('product_category') != 'fertilizer']),
        'total_compliance_records': len(compliance),
        'missing_compliance': missing_compliance, 'missing_compliance_count': len(missing_compliance),
        'incomplete_records': incomplete_records, 'incomplete_count': len(incomplete_records),
        'last_calibration_date': last_calibration,
        'missing_storage_inspection_quarters': missing_quarters,
    }


def get_applicator_records(user_id, applicator_name, year=None):
    """Get all compliance records for a specific applicator."""
    query = 'SELECT * FROM compliance_records WHERE user_id = ? AND applicator_name = ?'
    params = [user_id, applicator_name]
    if year:
        query += ' AND date LIKE ?'
        params.append(f'{year}-%')
    query += ' ORDER BY date DESC'
    with get_db() as conn:
        cursor = conn.execute(query, params)
        rows = cursor.fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Report CRUD
# ---------------------------------------------------------------------------

def _save_report_record(user_id, report_type, title, start_date, end_date, content):
    """Internal helper to persist a report record. Returns report ID."""
    with get_db() as conn:
        cursor = conn.execute("""
            INSERT INTO reports (user_id, report_type, title, date_range_start, date_range_end, content_json, format, status)
            VALUES (?, ?, ?, ?, ?, ?, 'json', 'draft')
        """, (user_id, report_type, title, start_date, end_date, json.dumps(content)))
        return cursor.lastrowid


def save_report(user_id, data):
    """Create or update a report from user-supplied data. Returns report ID."""
    report_type = data.get('report_type', 'custom')
    if report_type not in VALID_REPORT_TYPES:
        raise ValueError(f"Invalid report_type '{report_type}'")
    fmt = data.get('format', 'json')
    if fmt not in VALID_REPORT_FORMATS:
        fmt = 'json'
    status = data.get('status', 'draft')
    if status not in VALID_REPORT_STATUSES:
        status = 'draft'
    content_json = data.get('content_json')
    if isinstance(content_json, dict):
        content_json = json.dumps(content_json)
    report_id = data.get('id')

    with get_db() as conn:
        if report_id:
            conn.execute("""
                UPDATE reports SET title = ?, report_type = ?, date_range_start = ?, date_range_end = ?,
                    content_json = ?, format = ?, status = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND user_id = ?
            """, (data.get('title', 'Untitled Report'), report_type, data.get('date_range_start'),
                  data.get('date_range_end'), content_json, fmt, status, report_id, user_id))
        else:
            cursor = conn.execute("""
                INSERT INTO reports (user_id, report_type, title, date_range_start, date_range_end, content_json, format, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (user_id, report_type, data.get('title', 'Untitled Report'),
                  data.get('date_range_start'), data.get('date_range_end'), content_json, fmt, status))
            report_id = cursor.lastrowid
    logger.info(f"Report saved: {report_id} (user={user_id}, type={report_type})")
    return report_id


def get_report_by_id(report_id, user_id):
    """Get a single report by ID with ownership check."""
    with get_db() as conn:
        cursor = conn.execute('SELECT * FROM reports WHERE id = ? AND user_id = ?', (report_id, user_id))
        row = cursor.fetchone()
    if not row:
        return None
    result = dict(row)
    if result.get('content_json'):
        try:
            result['content_json'] = json.loads(result['content_json'])
        except (json.JSONDecodeError, TypeError):
            pass
    return result


def get_reports(user_id, report_type=None):
    """Get all reports for a user, optionally filtered by type."""
    query = 'SELECT id, user_id, report_type, title, date_range_start, date_range_end, format, status, created_at, updated_at FROM reports WHERE user_id = ?'
    params = [user_id]
    if report_type:
        if report_type not in VALID_REPORT_TYPES:
            raise ValueError(f"Invalid report_type '{report_type}'")
        query += ' AND report_type = ?'
        params.append(report_type)
    query += ' ORDER BY created_at DESC'
    with get_db() as conn:
        cursor = conn.execute(query, params)
        rows = cursor.fetchall()
    return [dict(r) for r in rows]


def delete_report(report_id, user_id):
    """Delete a report with ownership check. Returns True if deleted."""
    with get_db() as conn:
        cursor = conn.execute('DELETE FROM reports WHERE id = ? AND user_id = ?', (report_id, user_id))
        deleted = cursor.rowcount > 0
    if deleted:
        logger.info(f"Report deleted: {report_id} (user={user_id})")
    return deleted


# ---------------------------------------------------------------------------
# Export Functions
# ---------------------------------------------------------------------------

def _html_escape(text):
    """Basic HTML escaping."""
    if not text:
        return ''
    return str(text).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')


def _report_css():
    """Return CSS for printed/exported reports."""
    return """
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; max-width: 900px; margin: 0 auto; padding: 20px; color: #1a1a1a; line-height: 1.6; }
        h1 { color: #1b5e20; border-bottom: 3px solid #1b5e20; padding-bottom: 10px; }
        h2 { color: #2e7d32; margin-top: 30px; border-bottom: 1px solid #c8e6c9; padding-bottom: 5px; }
        h3 { color: #388e3c; }
        .meta { color: #666; font-style: italic; margin-bottom: 20px; }
        table { border-collapse: collapse; width: 100%; margin: 15px 0; }
        th, td { border: 1px solid #ddd; padding: 8px 12px; text-align: left; }
        th { background-color: #e8f5e9; font-weight: 600; }
        tr:nth-child(even) { background-color: #f9f9f9; }
        .summary-box { background: #f1f8e9; border: 1px solid #c5e1a5; border-radius: 8px; padding: 15px; margin: 15px 0; }
        .warning { color: #e65100; font-weight: 600; }
        .metric { display: inline-block; margin: 10px 20px 10px 0; }
        .metric-value { font-size: 1.5em; font-weight: bold; color: #1b5e20; }
        .metric-label { font-size: 0.85em; color: #666; }
        ul { margin: 5px 0; padding-left: 20px; }
        footer { margin-top: 40px; padding-top: 15px; border-top: 1px solid #ddd; color: #999; font-size: 0.85em; text-align: center; }
        @media print { body { max-width: none; } .no-print { display: none; } }
    """


def _render_metric(value, label):
    """Render a single metric box in HTML."""
    return f'<div class="metric"><div class="metric-value">{_html_escape(str(value))}</div><div class="metric-label">{_html_escape(label)}</div></div>'


def export_report_html(report_id, user_id):
    """Export a report as formatted HTML for printing or PDF generation."""
    report = get_report_by_id(report_id, user_id)
    if not report:
        return None
    content = report.get('content_json', {})
    if isinstance(content, str):
        try:
            content = json.loads(content)
        except (json.JSONDecodeError, TypeError):
            content = {}
    report_type = report.get('report_type', 'custom')
    title = report.get('title', 'Report')

    html_parts = [
        '<!DOCTYPE html>', '<html><head>', '<meta charset="utf-8">',
        f'<title>{_html_escape(title)}</title>', '<style>', _report_css(), '</style>',
        '</head><body>', f'<h1>{_html_escape(title)}</h1>',
        f'<p class="meta">Generated: {report.get("created_at", "N/A")} | Status: {report.get("status", "draft")}</p>',
    ]

    if report_type == 'monthly_super':
        html_parts.extend(_render_monthly_html(content))
    elif report_type == 'green_committee':
        html_parts.extend(_render_green_committee_html(content))
    elif report_type == 'annual':
        html_parts.extend(_render_annual_html(content))
    elif report_type == 'pesticide_compliance':
        html_parts.extend(_render_compliance_html(content))
    else:
        html_parts.append(f'<pre>{_html_escape(json.dumps(content, indent=2))}</pre>')

    html_parts.extend(['<footer>', '<p>Generated by Greenside AI Reporting Engine</p>', '</footer>', '</body></html>'])
    return '\n'.join(html_parts)


def _render_monthly_html(content):
    """Render monthly superintendent report as HTML sections."""
    parts = []
    weather = content.get('weather_summary', {})
    parts.append('<h2>Weather Summary</h2><div class="summary-box">')
    if weather.get('avg_temp') is not None:
        parts.append(_render_metric(f"{weather['avg_temp']}F", 'Avg Temp'))
    if weather.get('min_temp') is not None:
        parts.append(_render_metric(f"{weather['min_temp']}F", 'Low'))
    if weather.get('max_temp') is not None:
        parts.append(_render_metric(f"{weather['max_temp']}F", 'High'))
    parts.append(_render_metric(weather.get('application_days', 0), 'App Days'))
    parts.append('</div>')

    parts.append(f'<h2>Spray Applications ({content.get("spray_count", 0)})</h2>')
    sprays = content.get('spray_applications', [])
    if sprays:
        parts.append('<table><tr><th>Date</th><th>Area</th><th>Product</th><th>Rate</th><th>Notes</th></tr>')
        for s in sprays:
            products = s.get('tank_mix_products')
            pname = ', '.join(products) if products else s.get('product_name', '')
            parts.append(f'<tr><td>{_html_escape(s.get("date", ""))}</td><td>{_html_escape(s.get("area", ""))}</td><td>{_html_escape(pname)}</td><td>{s.get("rate", "")} {_html_escape(s.get("rate_unit", ""))}</td><td>{_html_escape(s.get("notes", "") or "")}</td></tr>')
        parts.append('</table>')
    else:
        parts.append('<p>No spray applications recorded this month.</p>')

    nutrients = content.get('nutrient_summary', {})
    if nutrients:
        parts.append('<h2>Nutrient Summary (lbs applied)</h2><table><tr><th>Area</th><th>N</th><th>P2O5</th><th>K2O</th></tr>')
        for area, vals in nutrients.items():
            parts.append(f'<tr><td>{_html_escape(area.title())}</td><td>{vals.get("N", 0)}</td><td>{vals.get("P2O5", 0)}</td><td>{vals.get("K2O", 0)}</td></tr>')
        parts.append('</table>')

    scouting = content.get('scouting', {})
    parts.append('<h2>Scouting Summary</h2><div class="summary-box">')
    parts.append(_render_metric(scouting.get('new_count', 0), 'New Issues'))
    parts.append(_render_metric(scouting.get('resolved_count', 0), 'Resolved'))
    parts.append(_render_metric(scouting.get('ongoing_count', 0), 'Ongoing'))
    parts.append('</div>')

    budget = content.get('budget', {})
    if budget:
        parts.append('<h2>Budget Status</h2><div class="summary-box">')
        parts.append(_render_metric(f"${budget.get('total_budgeted', 0):,.0f}", 'Budgeted'))
        parts.append(_render_metric(f"${budget.get('total_spent', 0):,.0f}", 'Spent'))
        parts.append(_render_metric(f"{budget.get('pct_used', 0)}%", 'Used'))
        parts.append('</div>')
        by_cat = budget.get('by_category', [])
        if by_cat:
            parts.append('<table><tr><th>Category</th><th>Budgeted</th><th>Spent</th><th>Remaining</th><th>% Used</th></tr>')
            for c in by_cat:
                parts.append(f'<tr><td>{_html_escape(c["category"].title())}</td><td>${c["budgeted"]:,.2f}</td><td>${c["spent"]:,.2f}</td><td>${c["remaining"]:,.2f}</td><td>{c["pct_used"]}%</td></tr>')
            parts.append('</table>')
    return parts


def _render_green_committee_html(content):
    """Render green committee report as HTML sections."""
    parts = []
    overview = content.get('conditions_overview', {})
    parts.append('<h2>Course Conditions Overview</h2><div class="summary-box">')
    parts.append(_render_metric(overview.get('total_applications', 0), 'Applications Made'))
    parts.append(_render_metric(overview.get('open_issues', 0), 'Open Issues'))
    parts.append(_render_metric(overview.get('resolved_issues', 0), 'Issues Resolved'))
    parts.append('</div>')
    areas = overview.get('areas_treated', [])
    if areas:
        parts.append(f'<p><strong>Areas treated:</strong> {", ".join(a.title() for a in areas)}</p>')
    for section, title in [('accomplishments', 'Key Accomplishments'), ('upcoming_plans', 'Upcoming Plans')]:
        items = content.get(section, [])
        if items:
            parts.append(f'<h2>{title}</h2><ul>')
            for item in items:
                parts.append(f'<li>{_html_escape(item)}</li>')
            parts.append('</ul>')
    budget = content.get('budget_summary', {})
    if budget:
        parts.append('<h2>Budget Summary</h2><div class="summary-box">')
        parts.append(_render_metric(f"${budget.get('total_budgeted', 0):,.0f}", 'Annual Budget'))
        parts.append(_render_metric(f"${budget.get('total_spent', 0):,.0f}", 'YTD Spent'))
        parts.append(_render_metric(f"{budget.get('pct_used', 0)}%", 'Utilized'))
        parts.append('</div>')
    weather = content.get('weather_impact', {})
    if weather:
        parts.append('<h2>Weather Impact</h2><div class="summary-box">')
        parts.append(_render_metric(weather.get('spray_days', 0), 'Spray Days'))
        if weather.get('avg_temp') is not None:
            parts.append(_render_metric(f"{weather['avg_temp']}F", 'Avg App Temp'))
        parts.append(_render_metric(weather.get('high_wind_days', 0), 'High Wind Days'))
        parts.append('</div>')
    issues = content.get('issues_and_resolutions', [])
    if issues:
        parts.append('<h2>Issues and Resolutions</h2><table><tr><th>Date</th><th>Area</th><th>Issue</th><th>Severity</th><th>Status</th><th>Treatment</th></tr>')
        for i in issues:
            parts.append(f'<tr><td>{_html_escape(i.get("date", ""))}</td><td>{_html_escape(i.get("area", ""))}</td><td>{_html_escape(i.get("issue_type", ""))}</td><td>{i.get("severity", "")}</td><td>{_html_escape(i.get("status", ""))}</td><td>{_html_escape(i.get("treatment", "") or "")}</td></tr>')
        parts.append('</table>')
    return parts


def _render_annual_html(content):
    """Render annual report as HTML sections."""
    parts = []
    yoy = content.get('yoy_comparison', {})
    if yoy:
        parts.append('<h2>Year-over-Year Comparison</h2><div class="summary-box">')
        parts.append(f'<p><strong>{yoy.get("current_year")} vs {yoy.get("previous_year")}</strong></p>')
        parts.append(_render_metric(yoy.get('current_applications', 0), 'Applications'))
        parts.append(_render_metric(yoy.get('current_scouting', 0), 'Scouting Reports'))
        parts.append(_render_metric(f"${yoy.get('current_spend', 0):,.0f}", 'Total Spend'))
        change = yoy.get('spend_change_pct', 0)
        direction = 'increase' if change > 0 else 'decrease'
        parts.append(_render_metric(f"{abs(change)}%", f'Spend {direction} vs prior year'))
        parts.append('</div>')
    monthly = content.get('monthly_summaries', [])
    if monthly:
        parts.append('<h2>Monthly Summaries</h2><table><tr><th>Month</th><th>Applications</th><th>Scouting</th><th>Expenses</th></tr>')
        for m in monthly:
            parts.append(f'<tr><td>{_html_escape(m.get("month_name", ""))}</td><td>{m.get("applications_count", 0)}</td><td>{m.get("scouting_reports_count", 0)}</td><td>${m.get("total_expenses", 0):,.2f}</td></tr>')
        parts.append('</table>')
    chemicals = content.get('total_chemicals', {})
    fertilizer = content.get('total_fertilizer', {})
    parts.append('<h2>Chemical and Fertilizer Summary</h2><div class="summary-box">')
    parts.append(_render_metric(chemicals.get('application_count', 0), 'Pesticide Apps'))
    parts.append(_render_metric(fertilizer.get('application_count', 0), 'Fertilizer Apps'))
    parts.append('</div>')
    for label, prods in [('Pesticide Products Used', chemicals.get('products_used', [])), ('Fertilizer Products Used', fertilizer.get('products_used', []))]:
        if prods:
            parts.append(f'<h3>{label}</h3><ul>')
            for p in prods:
                parts.append(f'<li>{_html_escape(p)}</li>')
            parts.append('</ul>')
    nutrients = content.get('nutrient_totals', {})
    if nutrients:
        parts.append('<h3>Total Nutrients Applied (lbs)</h3><table><tr><th>Area</th><th>N</th><th>P2O5</th><th>K2O</th></tr>')
        for area, vals in nutrients.items():
            parts.append(f'<tr><td>{_html_escape(area.title())}</td><td>{vals.get("N", 0)}</td><td>{vals.get("P2O5", 0)}</td><td>{vals.get("K2O", 0)}</td></tr>')
        parts.append('</table>')
    budget = content.get('budget_performance', {})
    if budget:
        parts.append('<h2>Budget Performance</h2><div class="summary-box">')
        parts.append(_render_metric(f"${budget.get('total_budgeted', 0):,.0f}", 'Total Budget'))
        parts.append(_render_metric(f"${budget.get('total_spent', 0):,.0f}", 'Total Spent'))
        parts.append(_render_metric(f"{budget.get('pct_used', 0)}%", 'Utilized'))
        parts.append('</div>')
    return parts


def _render_compliance_html(content):
    """Render pesticide compliance report as HTML sections."""
    parts = []
    parts.append('<h2>Compliance Summary</h2><div class="summary-box">')
    parts.append(_render_metric(content.get('total_pesticide_applications', 0), 'Pesticide Applications'))
    parts.append(_render_metric(content.get('total_compliance_records', 0), 'Compliance Records'))
    rei_issues = content.get('rei_issues', [])
    if rei_issues:
        parts.append(_render_metric(f'<span class="warning">{len(rei_issues)}</span>', 'REI Issues'))
    parts.append('</div>')
    applicators = content.get('applicators', {})
    if applicators:
        parts.append('<h2>Applicator Summary</h2><table><tr><th>Applicator</th><th>License</th><th>Applications</th><th>Products</th></tr>')
        for name, info in applicators.items():
            parts.append(f'<tr><td>{_html_escape(name)}</td><td>{_html_escape(info.get("license", ""))}</td><td>{info.get("application_count", 0)}</td><td>{_html_escape(", ".join(info.get("products_applied", [])))}</td></tr>')
        parts.append('</table>')
    records = content.get('application_records', [])
    if records:
        parts.append('<h2>Application Records</h2><table><tr><th>Date</th><th>Product</th><th>Rate</th><th>Area</th><th>Temp</th><th>Wind</th></tr>')
        for r in records:
            parts.append(f'<tr><td>{_html_escape(r.get("date", ""))}</td><td>{_html_escape(r.get("product_name", ""))}</td><td>{r.get("rate", "")} {_html_escape(r.get("rate_unit", ""))}</td><td>{_html_escape(r.get("area", ""))}</td><td>{r.get("weather_temp", "")}</td><td>{_html_escape(r.get("weather_wind", "") or "")}</td></tr>')
        parts.append('</table>')
    details = content.get('compliance_details', [])
    if details:
        parts.append('<h2>Compliance Detail Records</h2><table><tr><th>Date</th><th>Product</th><th>EPA Reg#</th><th>Applicator</th><th>License</th><th>Target Pest</th><th>REI (hrs)</th></tr>')
        for d in details:
            parts.append(f'<tr><td>{_html_escape(d.get("date", ""))}</td><td>{_html_escape(d.get("product_name", ""))}</td><td>{_html_escape(d.get("epa_reg_number", ""))}</td><td>{_html_escape(d.get("applicator_name", ""))}</td><td>{_html_escape(d.get("applicator_license", ""))}</td><td>{_html_escape(d.get("target_pest", ""))}</td><td>{d.get("rei_hours", "")}</td></tr>')
        parts.append('</table>')
    if rei_issues:
        parts.append('<h2 class="warning">REI Compliance Issues</h2><table><tr><th>Date</th><th>Product</th><th>REI (hrs)</th><th>Issue</th></tr>')
        for i in rei_issues:
            parts.append(f'<tr><td>{_html_escape(i.get("date", ""))}</td><td>{_html_escape(i.get("product", ""))}</td><td>{i.get("rei_hours", "")}</td><td class="warning">{_html_escape(i.get("issue", ""))}</td></tr>')
        parts.append('</table>')
    return parts


def export_spray_records_csv(user_id, year):
    """Export all spray application records for a year as CSV."""
    start_date, end_date = _date_range_for_year(year)
    with get_db() as conn:
        applications = _fetch_spray_applications(conn, user_id, start_date, end_date)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Date', 'Area', 'Product Name', 'Product Category', 'Rate', 'Rate Unit', 'Area (acres)', 'Total Product', 'Total Product Unit', 'Carrier Volume (GPA)', 'Total Carrier (gal)', 'Weather Temp (F)', 'Weather Wind', 'Weather Conditions', 'Application Method', 'Notes', 'N Applied (lbs)', 'P2O5 Applied (lbs)', 'K2O Applied (lbs)'])
    for app in applications:
        n_total = p_total = k_total = 0
        nutrients = app.get('nutrients_applied')
        if nutrients:
            n_data = nutrients.get('N')
            if isinstance(n_data, dict):
                n_total = n_data.get('total', 0)
            p_data = nutrients.get('P2O5')
            if isinstance(p_data, dict):
                p_total = p_data.get('total', 0)
            k_data = nutrients.get('K2O')
            if isinstance(k_data, dict):
                k_total = k_data.get('total', 0)
        writer.writerow([app['date'], app['area'], app['product_name'], app.get('product_category', ''), app['rate'], app['rate_unit'], app.get('area_acreage', ''), app.get('total_product', ''), app.get('total_product_unit', ''), app.get('carrier_volume_gpa', ''), app.get('total_carrier_gallons', ''), app.get('weather_temp', ''), app.get('weather_wind', ''), app.get('weather_conditions', ''), app.get('application_method', ''), app.get('notes', ''), round(n_total, 4) if n_total else '', round(p_total, 4) if p_total else '', round(k_total, 4) if k_total else ''])
    logger.info(f"Spray records CSV exported: {len(applications)} records (user={user_id}, year={year})")
    return output.getvalue()


def export_compliance_csv(user_id, year):
    """Export compliance records in a state-compatible CSV format."""
    records = get_compliance_records(user_id, year=year)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Date', 'Record Type', 'Applicator Name', 'Applicator License', 'Product Name', 'EPA Reg Number', 'Target Pest', 'Area Treated', 'Area (sq ft)', 'Rate Applied', 'Rate Unit', 'Wind Speed (mph)', 'Temperature (F)', 'REI (hours)', 'Description', 'Notes'])
    for cr in records:
        writer.writerow([cr.get('date', ''), cr.get('record_type', ''), cr.get('applicator_name', ''), cr.get('applicator_license', ''), cr.get('product_name', ''), cr.get('epa_reg_number', ''), cr.get('target_pest', ''), cr.get('area_treated', ''), cr.get('area_sqft', ''), cr.get('rate_applied', ''), cr.get('rate_unit', ''), cr.get('wind_speed', ''), cr.get('temperature', ''), cr.get('rei_hours', ''), cr.get('description', ''), cr.get('notes', '')])
    logger.info(f"Compliance CSV exported: {len(records)} records (user={user_id}, year={year})")
    return output.getvalue()


# ---------------------------------------------------------------------------
# State Pesticide Reporting Requirements
# ---------------------------------------------------------------------------

STATE_REQUIREMENTS = {
    'california': {'state_name': 'California', 'agency': 'CA Department of Pesticide Regulation (DPR)', 'report_name': 'Pesticide Use Report (PUR)', 'frequency': 'Monthly (due by 10th of following month)', 'required_fields': ['date_of_application', 'time_of_application', 'applicator_name', 'applicator_license_number', 'employer_name', 'employer_address', 'product_name', 'epa_registration_number', 'active_ingredient', 'amount_applied', 'unit_of_measure', 'acres_treated', 'crop_or_commodity_treated', 'site_location', 'county', 'section_township_range', 'fumigation_method', 'wind_speed_mph', 'wind_direction', 'temperature_f', 'target_pest'], 'notes': 'California has the most comprehensive pesticide reporting requirements in the US. All agricultural and structural pest control applications must be reported monthly. Golf courses and turf management fall under agricultural use reporting.'},
    'florida': {'state_name': 'Florida', 'agency': 'FL Department of Agriculture and Consumer Services (FDACS)', 'report_name': 'Restricted-Use Pesticide Records', 'frequency': 'Records maintained for 2 years; available on request', 'required_fields': ['date_of_application', 'applicator_name', 'applicator_license_number', 'product_name', 'epa_registration_number', 'amount_applied', 'area_treated', 'target_pest', 'crop_or_site', 'wind_speed_mph', 'temperature_f'], 'notes': 'Florida requires records for all restricted-use pesticide applications. General-use pesticide records are recommended but not mandated. Records must be kept for a minimum of 2 years.'},
    'new york': {'state_name': 'New York', 'agency': 'NY Department of Environmental Conservation (DEC)', 'report_name': 'Pesticide Application Report', 'frequency': 'Annual (due February 1)', 'required_fields': ['date_of_application', 'applicator_name', 'applicator_certification_number', 'product_name', 'epa_registration_number', 'amount_applied', 'unit_of_measure', 'area_treated_sqft', 'target_pest', 'location_address', 'county', 'application_method'], 'notes': 'New York requires annual reporting of all commercial pesticide applications. Reports are due by February 1 for the previous year. All certified applicators must report, including those applying to turf and ornamental sites.'},
    'texas': {'state_name': 'Texas', 'agency': 'TX Department of Agriculture (TDA)', 'report_name': 'Pesticide Application Records', 'frequency': 'Records maintained for 2 years; available on request', 'required_fields': ['date_of_application', 'applicator_name', 'applicator_license_number', 'product_name', 'epa_registration_number', 'amount_applied', 'area_treated', 'target_pest', 'weather_conditions', 'wind_speed_mph'], 'notes': 'Texas requires licensed applicators to maintain records of all pesticide applications for at least 2 years. Structural and non-structural applicators have different license categories. Records must be available for TDA inspection.'},
    'illinois': {'state_name': 'Illinois', 'agency': 'IL Department of Agriculture', 'report_name': 'Pesticide Application Records', 'frequency': 'Records maintained for 3 years', 'required_fields': ['date_of_application', 'applicator_name', 'applicator_license_number', 'product_name', 'epa_registration_number', 'amount_applied', 'area_treated', 'target_pest', 'application_method', 'wind_speed_mph', 'temperature_f'], 'notes': 'Illinois requires pesticide application records to be maintained for a minimum of 3 years. Both restricted-use and general-use application records are required for commercial applicators.'},
    'new jersey': {'state_name': 'New Jersey', 'agency': 'NJ Department of Environmental Protection (DEP)', 'report_name': 'Pesticide Application Records', 'frequency': 'Records maintained for 3 years; restricted-use reported annually', 'required_fields': ['date_of_application', 'time_of_application', 'applicator_name', 'applicator_certification_number', 'product_name', 'epa_registration_number', 'amount_applied', 'area_treated_sqft', 'target_pest', 'location_address', 'wind_speed_mph', 'temperature_f', 'notification_provided'], 'notes': 'New Jersey has stringent notification requirements for pesticide applications on turf, particularly on school grounds and near sensitive areas. Pre-application notification may be required.'},
    'massachusetts': {'state_name': 'Massachusetts', 'agency': 'MA Department of Agricultural Resources (DAR)', 'report_name': 'Pesticide Use Records', 'frequency': 'Records maintained for 3 years', 'required_fields': ['date_of_application', 'applicator_name', 'applicator_license_number', 'product_name', 'epa_registration_number', 'amount_applied', 'area_treated', 'target_pest', 'location', 'wind_speed_mph', 'temperature_f'], 'notes': 'Massachusetts requires all commercial applicators to maintain detailed records. Applications near water bodies require additional compliance with the Clean Waters Act.'},
    'georgia': {'state_name': 'Georgia', 'agency': 'GA Department of Agriculture', 'report_name': 'Pesticide Application Records', 'frequency': 'Records maintained for 2 years', 'required_fields': ['date_of_application', 'applicator_name', 'applicator_license_number', 'product_name', 'epa_registration_number', 'amount_applied', 'area_treated', 'target_pest', 'weather_conditions'], 'notes': 'Georgia requires licensed applicators to maintain records for at least 2 years. Both restricted-use and general-use pesticide applications should be recorded for commercial operations.'},
    'north carolina': {'state_name': 'North Carolina', 'agency': 'NC Department of Agriculture and Consumer Services', 'report_name': 'Pesticide Application Records', 'frequency': 'Records maintained for 3 years', 'required_fields': ['date_of_application', 'applicator_name', 'applicator_license_number', 'product_name', 'epa_registration_number', 'amount_applied', 'area_treated', 'target_pest', 'application_method', 'wind_speed_mph'], 'notes': 'North Carolina requires pesticide application records to be kept for 3 years. The state has additional buffer zone requirements near water bodies.'},
    'ohio': {'state_name': 'Ohio', 'agency': 'OH Department of Agriculture', 'report_name': 'Pesticide Application Records', 'frequency': 'Records maintained for 3 years', 'required_fields': ['date_of_application', 'applicator_name', 'applicator_license_number', 'product_name', 'epa_registration_number', 'amount_applied', 'area_treated', 'target_pest', 'wind_speed_mph', 'temperature_f'], 'notes': 'Ohio requires commercial applicators to maintain records for 3 years. Fertilizer applications on turf may also require separate nutrient management records.'},
    'michigan': {'state_name': 'Michigan', 'agency': 'MI Department of Agriculture and Rural Development (MDARD)', 'report_name': 'Pesticide Application Records', 'frequency': 'Records maintained for 3 years', 'required_fields': ['date_of_application', 'applicator_name', 'applicator_certification_number', 'product_name', 'epa_registration_number', 'amount_applied', 'area_treated', 'target_pest', 'wind_speed_mph', 'temperature_f', 'application_method'], 'notes': 'Michigan requires detailed records for all commercial pesticide applications with a 3-year retention period. Additional rules apply to applications near Great Lakes waterways.'},
    'pennsylvania': {'state_name': 'Pennsylvania', 'agency': 'PA Department of Agriculture', 'report_name': 'Pesticide Application Records', 'frequency': 'Records maintained for 3 years', 'required_fields': ['date_of_application', 'applicator_name', 'applicator_license_number', 'product_name', 'epa_registration_number', 'amount_applied', 'area_treated', 'target_pest', 'weather_conditions', 'wind_speed_mph'], 'notes': 'Pennsylvania requires all certified applicators to maintain records for 3 years. The state follows EPA guidelines for record-keeping with additional state-specific requirements.'},
    'virginia': {'state_name': 'Virginia', 'agency': 'VA Department of Agriculture and Consumer Services (VDACS)', 'report_name': 'Pesticide Application Records', 'frequency': 'Records maintained for 2 years', 'required_fields': ['date_of_application', 'applicator_name', 'applicator_license_number', 'product_name', 'epa_registration_number', 'amount_applied', 'area_treated', 'target_pest'], 'notes': 'Virginia requires pesticide applicator records for 2 years. Applications in the Chesapeake Bay watershed may have additional nutrient management and buffer zone requirements.'},
    'arizona': {'state_name': 'Arizona', 'agency': 'AZ Department of Agriculture', 'report_name': 'Pesticide Application Records', 'frequency': 'Records maintained for 2 years', 'required_fields': ['date_of_application', 'applicator_name', 'applicator_license_number', 'product_name', 'epa_registration_number', 'amount_applied', 'area_treated', 'target_pest', 'application_method'], 'notes': 'Arizona requires licensed applicators to maintain records for 2 years. Additional water use reporting may be required for golf courses in water-restricted areas.'},
    'colorado': {'state_name': 'Colorado', 'agency': 'CO Department of Agriculture', 'report_name': 'Pesticide Application Records', 'frequency': 'Records maintained for 3 years', 'required_fields': ['date_of_application', 'applicator_name', 'applicator_license_number', 'product_name', 'epa_registration_number', 'amount_applied', 'area_treated', 'target_pest', 'wind_speed_mph'], 'notes': 'Colorado requires commercial applicators to keep records for 3 years. High-altitude turf management may require adjusted application rates that should be documented.'},
    'south carolina': {'state_name': 'South Carolina', 'agency': 'Clemson University Department of Pesticide Regulation', 'report_name': 'Pesticide Application Records', 'frequency': 'Records maintained for 2 years', 'required_fields': ['date_of_application', 'applicator_name', 'applicator_license_number', 'product_name', 'epa_registration_number', 'amount_applied', 'area_treated', 'target_pest'], 'notes': 'South Carolina regulates pesticide use through Clemson University Department of Pesticide Regulation. Records must be maintained for 2 years for all commercial applications.'},
    'minnesota': {'state_name': 'Minnesota', 'agency': 'MN Department of Agriculture', 'report_name': 'Pesticide Application Records', 'frequency': 'Records maintained for 5 years', 'required_fields': ['date_of_application', 'applicator_name', 'applicator_license_number', 'product_name', 'epa_registration_number', 'amount_applied', 'area_treated', 'target_pest', 'wind_speed_mph', 'temperature_f', 'application_method'], 'notes': 'Minnesota has one of the longest record retention requirements at 5 years. The state also has specific pollinator protection requirements that may affect application timing.'},
    'connecticut': {'state_name': 'Connecticut', 'agency': 'CT Department of Energy and Environmental Protection (DEEP)', 'report_name': 'Pesticide Application Records', 'frequency': 'Records maintained for 5 years; annual reporting required', 'required_fields': ['date_of_application', 'time_of_application', 'applicator_name', 'applicator_certification_number', 'product_name', 'epa_registration_number', 'amount_applied', 'area_treated_sqft', 'target_pest', 'location_address', 'wind_speed_mph', 'temperature_f', 'notification_provided'], 'notes': 'Connecticut requires 5-year record retention and annual reporting. The state has strong notification requirements and restrictions on pesticide use near schools and day care centers.'},
}


def get_state_requirements(state):
    """Get pesticide reporting requirements for a given state."""
    if not state:
        return None
    key = state.lower().strip()
    reqs = STATE_REQUIREMENTS.get(key)
    if not reqs:
        state_aliases = {
            'ca': 'california', 'fl': 'florida', 'ny': 'new york', 'tx': 'texas',
            'il': 'illinois', 'nj': 'new jersey', 'ma': 'massachusetts', 'ga': 'georgia',
            'nc': 'north carolina', 'oh': 'ohio', 'mi': 'michigan', 'pa': 'pennsylvania',
            'va': 'virginia', 'az': 'arizona', 'co': 'colorado', 'sc': 'south carolina',
            'mn': 'minnesota', 'ct': 'connecticut',
        }
        resolved_key = state_aliases.get(key)
        if resolved_key:
            reqs = STATE_REQUIREMENTS.get(resolved_key)
    if not reqs:
        logger.warning(f"No state requirements found for '{state}'")
        return {
            'state_name': state.title(),
            'agency': 'Check with your state Department of Agriculture',
            'report_name': 'Pesticide Application Records',
            'frequency': 'Contact state agency for specific requirements',
            'required_fields': ['date_of_application', 'applicator_name', 'applicator_license_number', 'product_name', 'epa_registration_number', 'amount_applied', 'area_treated', 'target_pest'],
            'notes': f'Specific requirements for {state.title()} are not currently in our database. The fields listed are the minimum federal requirements under FIFRA. Contact your state Department of Agriculture for state-specific requirements.',
        }
    return reqs


def delete_compliance_record(record_id, user_id):
    """Delete a compliance record."""
    with get_db() as conn:
        conn.execute(
            'DELETE FROM compliance_records WHERE id = ? AND user_id = ?',
            (record_id, user_id)
        )
    return {'deleted': True}


def export_compliance_records(user_id, start_date=None, end_date=None, fmt='csv'):
    """Export compliance records in the specified format."""
    records = get_compliance_records(user_id, year=None)
    if start_date:
        records = [r for r in records if r.get('date', '') >= start_date]
    if end_date:
        records = [r for r in records if r.get('date', '') <= end_date]
    if fmt == 'csv':
        if not records:
            return {'csv': 'No records found', 'count': 0}
        headers = list(records[0].keys())
        lines = [','.join(headers)]
        for r in records:
            lines.append(','.join(str(r.get(h, '')) for h in headers))
        return {'csv': '\n'.join(lines), 'count': len(records)}
    return {'records': records, 'count': len(records)}
