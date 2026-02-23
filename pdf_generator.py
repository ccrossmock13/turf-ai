"""
PDF generation for Greenside AI Spray Tracker.
Generates individual spray records and seasonal summary reports.
"""

import io
import json
from datetime import datetime
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer,
    HRFlowable, PageBreak
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT


# Brand colors
GREEN_DARK = colors.HexColor('#1a4d2e')
GREEN_MID = colors.HexColor('#2d7a4a')
GREEN_LIGHT = colors.HexColor('#dcfce7')
GRAY_LIGHT = colors.HexColor('#f9fafb')
GRAY_BORDER = colors.HexColor('#e5e7eb')
TEXT_PRIMARY = colors.HexColor('#1a1a1a')
TEXT_SECONDARY = colors.HexColor('#6b7280')

NUTRIENT_KEYS = ['N', 'P2O5', 'K2O']
NUTRIENT_LABELS = {
    'N': 'Nitrogen (N)',
    'P2O5': 'Phosphorus (P2O5)',
    'K2O': 'Potassium (K2O)',
}


def _get_styles():
    """Get custom paragraph styles."""
    styles = getSampleStyleSheet()

    styles.add(ParagraphStyle(
        'GreenTitle',
        parent=styles['Title'],
        textColor=GREEN_DARK,
        fontSize=20,
        spaceAfter=6,
    ))
    styles.add(ParagraphStyle(
        'GreenHeading',
        parent=styles['Heading2'],
        textColor=GREEN_DARK,
        fontSize=14,
        spaceBefore=12,
        spaceAfter=8,
    ))
    styles.add(ParagraphStyle(
        'SmallText',
        parent=styles['Normal'],
        fontSize=9,
        textColor=TEXT_SECONDARY,
    ))
    styles.add(ParagraphStyle(
        'TableHeader',
        parent=styles['Normal'],
        fontSize=9,
        textColor=colors.white,
        alignment=TA_CENTER,
    ))

    return styles


def _header_footer(canvas, doc, course_name='', title=''):
    """Add header and footer to each page."""
    canvas.saveState()
    # Header line
    canvas.setStrokeColor(GREEN_DARK)
    canvas.setLineWidth(2)
    canvas.line(36, letter[1] - 36, letter[0] - 36, letter[1] - 36)

    canvas.setFont('Helvetica-Bold', 10)
    canvas.setFillColor(GREEN_DARK)
    canvas.drawString(36, letter[1] - 30, 'Greenside AI')

    if course_name:
        canvas.setFont('Helvetica', 9)
        canvas.setFillColor(TEXT_SECONDARY)
        canvas.drawRightString(letter[0] - 36, letter[1] - 30, course_name)

    # Footer
    canvas.setFont('Helvetica', 8)
    canvas.setFillColor(TEXT_SECONDARY)
    canvas.drawString(36, 24, f'Generated {datetime.now().strftime("%B %d, %Y at %I:%M %p")}')
    canvas.drawRightString(letter[0] - 36, 24, f'Page {doc.page}')

    canvas.restoreState()


def generate_single_spray_record(application, course_name=''):
    """Generate a single-page PDF for one spray application.

    Args:
        application: dict with spray application data
        course_name: Name of the course/facility

    Returns:
        io.BytesIO buffer containing the PDF
    """
    buffer = io.BytesIO()
    styles = _get_styles()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        topMargin=50,
        bottomMargin=40,
        leftMargin=36,
        rightMargin=36
    )

    elements = []

    # Basic info
    date_str = application.get('date', 'N/A')
    area = application.get('area', 'N/A').capitalize()
    product = application.get('product_name', 'N/A')
    category = application.get('product_category', 'N/A').capitalize()

    # Check if tank mix and if granular
    products_json = application.get('products_json')
    is_tank_mix = isinstance(products_json, list) and len(products_json) > 1
    app_method = application.get('application_method', '')
    is_granular = app_method in ('push_spreader', 'ride_on_spreader')

    if is_tank_mix:
        elements.append(Paragraph('Tank Mix Application Record', styles['GreenTitle']))
    elif is_granular:
        elements.append(Paragraph('Spreader Application Record', styles['GreenTitle']))
    else:
        elements.append(Paragraph('Spray Application Record', styles['GreenTitle']))
    elements.append(Spacer(1, 4))

    info_data = [
        ['Date:', date_str, 'Area:', area],
    ]
    if is_tank_mix:
        info_data.append(['Products:', f'{len(products_json)} products (Tank Mix)', '', ''])
    else:
        info_data.append(['Product:', product, 'Category:', category])

    info_table = Table(info_data, colWidths=[60, 200, 70, 200])
    info_table.setStyle(TableStyle([
        ('FONT', (0, 0), (0, -1), 'Helvetica-Bold', 10),
        ('FONT', (2, 0), (2, -1), 'Helvetica-Bold', 10),
        ('FONT', (1, 0), (1, -1), 'Helvetica', 10),
        ('FONT', (3, 0), (3, -1), 'Helvetica', 10),
        ('TEXTCOLOR', (0, 0), (0, -1), GREEN_DARK),
        ('TEXTCOLOR', (2, 0), (2, -1), GREEN_DARK),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, 12))
    elements.append(HRFlowable(width='100%', color=GRAY_BORDER, thickness=1))

    # Rate & Calculations
    acreage = application.get('area_acreage', 0)
    gpa = application.get('carrier_volume_gpa', '')
    total_carrier = application.get('total_carrier_gallons', '')

    tank_count = application.get('tank_count')
    tank_size = application.get('tank_size')

    if is_tank_mix:
        # Tank mix: show each product's rate, total, and per-tank amount
        elements.append(Paragraph('Tank Mix Products', styles['GreenHeading']))

        if not is_granular and tank_count and tank_count > 0:
            mix_header = ['Product', 'Rate', 'Per Tank', 'Total']
            mix_rows = [mix_header]
            for p in products_json:
                total_val = p.get('total_product', 0) or 0
                total_unit = p.get('total_product_unit', '')
                try:
                    per_tank = round(float(total_val) / tank_count, 2)
                except (ValueError, TypeError, ZeroDivisionError):
                    per_tank = ''
                mix_rows.append([
                    (p.get('product_name') or 'Unknown')[:35],
                    f"{p.get('rate', '')} {p.get('rate_unit', '')}",
                    f"{per_tank} {total_unit}" if per_tank != '' else '—',
                    f"{total_val} {total_unit}"
                ])
            mix_table = Table(mix_rows, colWidths=[170, 120, 110, 110])
        else:
            mix_header = ['Product', 'Rate', 'Total']
            mix_rows = [mix_header]
            for p in products_json:
                mix_rows.append([
                    (p.get('product_name') or 'Unknown')[:35],
                    f"{p.get('rate', '')} {p.get('rate_unit', '')}",
                    f"{p.get('total_product', '')} {p.get('total_product_unit', '')}"
                ])
            mix_table = Table(mix_rows, colWidths=[200, 150, 150])

        mix_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), GREEN_DARK),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONT', (0, 0), (-1, 0), 'Helvetica-Bold', 9),
            ('ALIGNMENT', (0, 0), (-1, 0), 'CENTER'),
            ('FONT', (0, 1), (-1, -1), 'Helvetica', 9),
            ('GRID', (0, 0), (-1, -1), 0.5, GRAY_BORDER),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, GRAY_LIGHT]),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ]))
        elements.append(mix_table)
        elements.append(Spacer(1, 8))

        # Carrier and area info
        elements.append(Paragraph('Application Details', styles['GreenHeading']))
        calc_data = [['Area Acreage:', f'{acreage} acres']]
        if not is_granular:
            if gpa:
                calc_data.append(['Carrier Volume:', f'{gpa} GPA'])
            if tank_count:
                calc_data.append(['Tanks:', f'{tank_count}' + (f' × {tank_size} gal' if tank_size else '')])
            if total_carrier:
                calc_data.append(['Total Amount:', f'{total_carrier} gallons'])
    else:
        # Single product
        elements.append(Paragraph('Rate & Calculations', styles['GreenHeading']))
        rate = application.get('rate', 0)
        rate_unit = application.get('rate_unit', '')
        total_product = application.get('total_product', 0)
        total_unit = application.get('total_product_unit', '')

        calc_data = [
            ['Application Rate:', f'{rate} {rate_unit}'],
            ['Area Acreage:', f'{acreage} acres'],
            ['Total Product:', f'{total_product} {total_unit}'],
        ]
        if not is_granular:
            if tank_count and tank_count > 0:
                try:
                    per_tank = round(float(total_product) / tank_count, 2)
                    calc_data.append(['Per Tank:', f'{per_tank} {total_unit}'])
                except (ValueError, TypeError, ZeroDivisionError):
                    pass
            if gpa:
                calc_data.append(['Carrier Volume:', f'{gpa} GPA'])
            if tank_count:
                calc_data.append(['Tanks:', f'{tank_count}' + (f' × {tank_size} gal' if tank_size else '')])
            if total_carrier:
                calc_data.append(['Total Amount:', f'{total_carrier} gallons'])

    calc_table = Table(calc_data, colWidths=[130, 400])
    calc_table.setStyle(TableStyle([
        ('FONT', (0, 0), (0, -1), 'Helvetica-Bold', 10),
        ('FONT', (1, 0), (1, -1), 'Helvetica', 10),
        ('TEXTCOLOR', (0, 0), (0, -1), TEXT_PRIMARY),
        ('BACKGROUND', (0, 0), (-1, -1), GREEN_LIGHT),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('ROUNDEDCORNERS', [4, 4, 4, 4]),
    ]))
    elements.append(calc_table)

    # Nutrients
    nutrients = application.get('nutrients_applied')
    if isinstance(nutrients, str):
        try:
            nutrients = json.loads(nutrients)
        except (json.JSONDecodeError, TypeError):
            nutrients = None

    if nutrients:
        elements.append(Spacer(1, 8))
        elements.append(Paragraph('Nutrients Applied', styles['GreenHeading']))

        nut_header = ['Nutrient', 'Analysis %', 'Per 1000 sq ft', 'Total']
        nut_rows = [nut_header]

        for key in NUTRIENT_KEYS:
            n_data = nutrients.get(key)
            if isinstance(n_data, dict):
                pct = n_data.get('pct', 0)
                per_1000 = n_data.get('per_1000', 0)
                total = n_data.get('total', 0)
                if pct > 0 or per_1000 > 0 or total > 0:
                    nut_rows.append([
                        NUTRIENT_LABELS.get(key, key),
                        f"{pct}%" if pct else '—',
                        f"{per_1000:.4f} lbs",
                        f"{total:.2f} lbs"
                    ])

        if len(nut_rows) > 1:
            nut_table = Table(nut_rows, colWidths=[150, 90, 120, 120])
            nut_table.setStyle(TableStyle([
                # Header
                ('BACKGROUND', (0, 0), (-1, 0), GREEN_DARK),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONT', (0, 0), (-1, 0), 'Helvetica-Bold', 9),
                ('ALIGNMENT', (0, 0), (-1, 0), 'CENTER'),
                # Body
                ('FONT', (0, 1), (-1, -1), 'Helvetica', 9),
                ('ALIGNMENT', (1, 1), (-1, -1), 'CENTER'),
                ('ALIGNMENT', (0, 1), (0, -1), 'LEFT'),
                # Grid
                ('GRID', (0, 0), (-1, -1), 0.5, GRAY_BORDER),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, GRAY_LIGHT]),
                ('TOPPADDING', (0, 0), (-1, -1), 5),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
                ('LEFTPADDING', (0, 0), (-1, -1), 6),
                ('RIGHTPADDING', (0, 0), (-1, -1), 6),
            ]))
            elements.append(nut_table)

    # Weather
    temp = application.get('weather_temp')
    wind = application.get('weather_wind')
    conditions = application.get('weather_conditions')
    if temp or wind or conditions:
        elements.append(Spacer(1, 8))
        elements.append(Paragraph('Weather Conditions', styles['GreenHeading']))
        weather_parts = []
        if temp:
            weather_parts.append(f'Temperature: {temp}°F')
        if wind:
            weather_parts.append(f'Wind: {wind}')
        if conditions:
            weather_parts.append(f'Conditions: {conditions.replace("_", " ").title()}')
        elements.append(Paragraph(' · '.join(weather_parts), styles['Normal']))

    # Notes
    notes = application.get('notes')
    if notes:
        elements.append(Spacer(1, 8))
        elements.append(Paragraph('Notes', styles['GreenHeading']))
        elements.append(Paragraph(notes, styles['Normal']))

    # Signature lines
    elements.append(Spacer(1, 40))
    sig_data = [
        ['Applicator: ________________________', '', 'Date: ________________________'],
        ['', '', ''],
        ['Supervisor: ________________________', '', 'Date: ________________________'],
    ]
    sig_table = Table(sig_data, colWidths=[220, 40, 220])
    sig_table.setStyle(TableStyle([
        ('FONT', (0, 0), (-1, -1), 'Helvetica', 10),
        ('TEXTCOLOR', (0, 0), (-1, -1), TEXT_SECONDARY),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
    ]))
    elements.append(sig_table)

    # Build
    doc.build(
        elements,
        onFirstPage=lambda c, d: _header_footer(c, d, course_name, 'Spray Record'),
        onLaterPages=lambda c, d: _header_footer(c, d, course_name, 'Spray Record')
    )

    buffer.seek(0)
    return buffer


def generate_seasonal_report(applications, nutrient_summary, course_name='', date_range=''):
    """Generate multi-page seasonal spray report.

    Args:
        applications: list of application dicts
        nutrient_summary: dict from get_nutrient_summary()
        course_name: Name of the course/facility
        date_range: String like 'Season 2025'

    Returns:
        io.BytesIO buffer containing the PDF
    """
    buffer = io.BytesIO()
    styles = _get_styles()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        topMargin=50,
        bottomMargin=40,
        leftMargin=36,
        rightMargin=36
    )

    elements = []

    # ── Cover page ──
    elements.append(Spacer(1, 100))
    elements.append(Paragraph('Seasonal Spray Report', styles['GreenTitle']))
    if course_name:
        elements.append(Paragraph(course_name, ParagraphStyle(
            'CourseName',
            parent=styles['Normal'],
            fontSize=16,
            textColor=TEXT_SECONDARY,
            spaceAfter=8,
        )))
    if date_range:
        elements.append(Paragraph(date_range, ParagraphStyle(
            'DateRange',
            parent=styles['Normal'],
            fontSize=14,
            textColor=GREEN_MID,
            spaceAfter=20,
        )))

    elements.append(Spacer(1, 20))
    elements.append(HRFlowable(width='100%', color=GREEN_DARK, thickness=2))
    elements.append(Spacer(1, 16))

    # Summary stats
    total_apps = len(applications)
    areas_used = set(a['area'] for a in applications)
    products_used = set(a['product_name'] for a in applications)
    categories = {}
    for a in applications:
        cat = a.get('product_category', 'other')
        categories[cat] = categories.get(cat, 0) + 1

    summary_data = [
        ['Total Applications:', str(total_apps)],
        ['Areas Covered:', ', '.join(sorted(a.capitalize() for a in areas_used)) or 'None'],
        ['Unique Products:', str(len(products_used))],
        ['Categories:', ', '.join(f'{k.capitalize()} ({v})' for k, v in sorted(categories.items())) or 'None'],
    ]

    sum_table = Table(summary_data, colWidths=[140, 380])
    sum_table.setStyle(TableStyle([
        ('FONT', (0, 0), (0, -1), 'Helvetica-Bold', 11),
        ('FONT', (1, 0), (1, -1), 'Helvetica', 11),
        ('TEXTCOLOR', (0, 0), (0, -1), GREEN_DARK),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    elements.append(sum_table)

    elements.append(PageBreak())

    # ── Application Log ──
    elements.append(Paragraph('Application Log', styles['GreenTitle']))
    elements.append(Spacer(1, 8))

    if applications:
        app_header = ['Date', 'Area', 'Product', 'Rate', 'Total', 'Cat.']
        app_rows = [app_header]

        for a in applications:
            pj = a.get('products_json')
            is_mix = isinstance(pj, list) and len(pj) > 1
            if is_mix:
                product_str = f"Tank Mix ({len(pj)})"
                rate_str = ', '.join(f"{p.get('rate','')} {p.get('rate_unit','')}" for p in pj[:2])
                if len(pj) > 2:
                    rate_str += '...'
                total_str = f"{a.get('total_carrier_gallons','')} gal" if a.get('total_carrier_gallons') else '—'
                cat_str = 'Mix'
            else:
                product_str = a.get('product_name', '')[:30]
                rate_str = f"{a.get('rate', '')} {a.get('rate_unit', '')}"
                total_str = f"{a.get('total_product', '')} {a.get('total_product_unit', '')}"
                cat_str = a.get('product_category', '')[:8].capitalize()

            app_rows.append([
                a.get('date', ''),
                a.get('area', '').capitalize(),
                product_str,
                rate_str,
                total_str,
                cat_str
            ])

        col_widths = [65, 60, 150, 95, 90, 60]
        app_table = Table(app_rows, colWidths=col_widths, repeatRows=1)
        app_table.setStyle(TableStyle([
            # Header
            ('BACKGROUND', (0, 0), (-1, 0), GREEN_DARK),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONT', (0, 0), (-1, 0), 'Helvetica-Bold', 8),
            ('ALIGNMENT', (0, 0), (-1, 0), 'CENTER'),
            # Body
            ('FONT', (0, 1), (-1, -1), 'Helvetica', 8),
            # Grid
            ('GRID', (0, 0), (-1, -1), 0.5, GRAY_BORDER),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, GRAY_LIGHT]),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('LEFTPADDING', (0, 0), (-1, -1), 4),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        elements.append(app_table)
    else:
        elements.append(Paragraph('No applications logged.', styles['Normal']))

    elements.append(PageBreak())

    # ── Nutrient Summary ──
    elements.append(Paragraph('Nutrient Summary', styles['GreenTitle']))
    elements.append(Spacer(1, 8))

    areas_data = nutrient_summary.get('areas', {})
    for area_name in ['greens', 'fairways', 'tees', 'rough']:
        info = areas_data.get(area_name)
        if not info or info.get('applications_count', 0) == 0:
            continue

        area_title = area_name.capitalize()
        if info.get('acreage'):
            area_title += f' ({info["acreage"]} acres)'
        elements.append(Paragraph(area_title, styles['GreenHeading']))

        # N budget
        n_budget = info.get('n_budget', {})
        n_applied = n_budget.get('applied', 0)
        n_target = n_budget.get('target', 0)
        n_remaining = n_budget.get('remaining', 0)
        n_pct = n_budget.get('pct', 0)

        budget_text = (
            f'<b>N Budget:</b> {n_applied:.2f} / {n_target} lbs N per 1000 sq ft '
            f'({n_pct:.0f}% applied, {n_remaining:.2f} remaining)'
        )
        elements.append(Paragraph(budget_text, styles['Normal']))
        elements.append(Spacer(1, 6))

        # Nutrient table
        nut_header = ['Nutrient', 'Per 1000 sq ft', 'Total Applied']
        nut_rows = [nut_header]

        per_1000 = info.get('per_1000', {})
        totals = info.get('totals', {})

        for key in NUTRIENT_KEYS:
            val = per_1000.get(key, 0)
            total_val = totals.get(key, 0)
            if val > 0 or total_val > 0:
                nut_rows.append([
                    NUTRIENT_LABELS.get(key, key),
                    f'{val:.3f} lbs',
                    f'{total_val:.2f} lbs'
                ])

        if len(nut_rows) > 1:
            nut_table = Table(nut_rows, colWidths=[180, 120, 120])
            nut_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), GREEN_DARK),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONT', (0, 0), (-1, 0), 'Helvetica-Bold', 9),
                ('ALIGNMENT', (0, 0), (-1, 0), 'CENTER'),
                ('FONT', (0, 1), (-1, -1), 'Helvetica', 9),
                ('ALIGNMENT', (1, 1), (-1, -1), 'CENTER'),
                ('ALIGNMENT', (0, 1), (0, -1), 'LEFT'),
                ('GRID', (0, 0), (-1, -1), 0.5, GRAY_BORDER),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, GRAY_LIGHT]),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                ('LEFTPADDING', (0, 0), (-1, -1), 6),
                ('RIGHTPADDING', (0, 0), (-1, -1), 6),
            ]))
            elements.append(nut_table)
        elements.append(Spacer(1, 12))

    # ── Product Usage Summary ──
    elements.append(PageBreak())
    elements.append(Paragraph('Product Usage Summary', styles['GreenTitle']))
    elements.append(Spacer(1, 8))

    # Aggregate by product (including tank mix components)
    product_usage = {}
    for a in applications:
        pj = a.get('products_json')
        area = a.get('area', '')
        if isinstance(pj, list) and len(pj) > 1:
            # Tank mix: count each component product
            for p in pj:
                pname = p.get('product_name', 'Unknown')
                if pname not in product_usage:
                    product_usage[pname] = {
                        'category': p.get('product_category', ''),
                        'count': 0,
                        'areas': set()
                    }
                product_usage[pname]['count'] += 1
                product_usage[pname]['areas'].add(area)
        else:
            pname = a.get('product_name', 'Unknown')
            if pname not in product_usage:
                product_usage[pname] = {
                    'category': a.get('product_category', ''),
                    'count': 0,
                    'areas': set()
                }
            product_usage[pname]['count'] += 1
            product_usage[pname]['areas'].add(area)

    if product_usage:
        prod_header = ['Product', 'Category', 'Applications', 'Areas']
        prod_rows = [prod_header]

        for pname, pinfo in sorted(product_usage.items(), key=lambda x: -x[1]['count']):
            prod_rows.append([
                pname[:35],
                pinfo['category'].capitalize(),
                str(pinfo['count']),
                ', '.join(sorted(a.capitalize() for a in pinfo['areas']))
            ])

        prod_table = Table(prod_rows, colWidths=[180, 80, 80, 180], repeatRows=1)
        prod_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), GREEN_DARK),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONT', (0, 0), (-1, 0), 'Helvetica-Bold', 9),
            ('ALIGNMENT', (0, 0), (-1, 0), 'CENTER'),
            ('FONT', (0, 1), (-1, -1), 'Helvetica', 9),
            ('ALIGNMENT', (2, 1), (2, -1), 'CENTER'),
            ('GRID', (0, 0), (-1, -1), 0.5, GRAY_BORDER),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, GRAY_LIGHT]),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ]))
        elements.append(prod_table)

    # Build
    doc.build(
        elements,
        onFirstPage=lambda c, d: _header_footer(c, d, course_name, 'Seasonal Report'),
        onLaterPages=lambda c, d: _header_footer(c, d, course_name, 'Seasonal Report')
    )

    buffer.seek(0)
    return buffer


def generate_nutrient_report(nutrient_summary, course_name='', year=''):
    """Generate a nutrient tracking PDF report.

    Args:
        nutrient_summary: dict from get_nutrient_summary()
        course_name: Name of the course/facility
        year: Year string like '2026'

    Returns:
        io.BytesIO buffer containing the PDF
    """
    buffer = io.BytesIO()
    styles = _get_styles()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        topMargin=50,
        bottomMargin=40,
        leftMargin=36,
        rightMargin=36
    )

    elements = []

    # Title
    elements.append(Paragraph('Nutrient Tracking Report', styles['GreenTitle']))
    if course_name:
        elements.append(Paragraph(course_name, ParagraphStyle(
            'CourseName2',
            parent=styles['Normal'],
            fontSize=14,
            textColor=TEXT_SECONDARY,
            spaceAfter=4,
        )))
    if year:
        elements.append(Paragraph(f'Season {year}', ParagraphStyle(
            'Year',
            parent=styles['Normal'],
            fontSize=12,
            textColor=GREEN_MID,
            spaceAfter=12,
        )))

    elements.append(HRFlowable(width='100%', color=GREEN_DARK, thickness=2))
    elements.append(Spacer(1, 16))

    areas_data = nutrient_summary.get('areas', {})

    for area_name in ['greens', 'fairways', 'tees', 'rough']:
        info = areas_data.get(area_name)
        if not info or info.get('applications_count', 0) == 0:
            continue

        # Area heading
        area_title = area_name.capitalize()
        if info.get('acreage'):
            area_title += f' ({info["acreage"]} acres)'
        elements.append(Paragraph(area_title, styles['GreenHeading']))

        app_count = info.get('applications_count', 0)
        elements.append(Paragraph(
            f'{app_count} application{"s" if app_count != 1 else ""}',
            styles['SmallText']
        ))
        elements.append(Spacer(1, 6))

        # N Budget box
        n_budget = info.get('n_budget', {})
        n_applied = n_budget.get('applied', 0)
        n_target = n_budget.get('target', 0)
        n_remaining = n_budget.get('remaining', 0)
        n_pct = n_budget.get('pct', 0)

        budget_data = [
            ['N Applied:', f'{n_applied:.2f} lbs/1000 sq ft',
             'Target:', f'{n_target} lbs/1000 sq ft'],
            ['Remaining:', f'{n_remaining:.2f} lbs/1000 sq ft',
             'Progress:', f'{n_pct:.0f}%'],
        ]
        budget_table = Table(budget_data, colWidths=[80, 150, 70, 150])
        budget_table.setStyle(TableStyle([
            ('FONT', (0, 0), (0, -1), 'Helvetica-Bold', 10),
            ('FONT', (2, 0), (2, -1), 'Helvetica-Bold', 10),
            ('FONT', (1, 0), (1, -1), 'Helvetica', 10),
            ('FONT', (3, 0), (3, -1), 'Helvetica', 10),
            ('TEXTCOLOR', (0, 0), (0, -1), GREEN_DARK),
            ('TEXTCOLOR', (2, 0), (2, -1), GREEN_DARK),
            ('BACKGROUND', (0, 0), (-1, -1), GREEN_LIGHT),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ]))
        elements.append(budget_table)
        elements.append(Spacer(1, 8))

        # Nutrient detail table
        per_1000 = info.get('per_1000', {})
        totals = info.get('totals', {})

        nut_header = ['Nutrient', 'Per 1000 sq ft', 'Total Applied']
        nut_rows = [nut_header]

        for key in NUTRIENT_KEYS:
            val = per_1000.get(key, 0)
            total_val = totals.get(key, 0)
            if val > 0 or total_val > 0:
                nut_rows.append([
                    NUTRIENT_LABELS.get(key, key),
                    f'{val:.3f} lbs',
                    f'{total_val:.2f} lbs'
                ])

        if len(nut_rows) > 1:
            nut_table = Table(nut_rows, colWidths=[180, 120, 120])
            nut_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), GREEN_DARK),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONT', (0, 0), (-1, 0), 'Helvetica-Bold', 9),
                ('ALIGNMENT', (0, 0), (-1, 0), 'CENTER'),
                ('FONT', (0, 1), (-1, -1), 'Helvetica', 9),
                ('ALIGNMENT', (1, 1), (-1, -1), 'CENTER'),
                ('ALIGNMENT', (0, 1), (0, -1), 'LEFT'),
                ('GRID', (0, 0), (-1, -1), 0.5, GRAY_BORDER),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, GRAY_LIGHT]),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                ('LEFTPADDING', (0, 0), (-1, -1), 6),
                ('RIGHTPADDING', (0, 0), (-1, -1), 6),
            ]))
            elements.append(nut_table)

        elements.append(Spacer(1, 16))

    if not any(
        areas_data.get(a, {}).get('applications_count', 0) > 0
        for a in ['greens', 'fairways', 'tees', 'rough']
    ):
        elements.append(Paragraph('No nutrient data available.', styles['Normal']))

    # Build
    doc.build(
        elements,
        onFirstPage=lambda c, d: _header_footer(c, d, course_name, 'Nutrient Report'),
        onLaterPages=lambda c, d: _header_footer(c, d, course_name, 'Nutrient Report')
    )

    buffer.seek(0)
    return buffer
