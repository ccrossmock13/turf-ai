"""Generic data export service for CSV and PDF generation."""

import csv
import io
import logging
from datetime import datetime

from flask import make_response

logger = logging.getLogger(__name__)


def export_csv(data, columns, filename):
    """Generate a CSV file response from a list of dicts.

    Args:
        data: list of dicts (rows)
        columns: list of (key, header_label) tuples
        filename: download filename (e.g. 'equipment_2026-03-01.csv')

    Returns:
        Flask Response with CSV content
    """
    output = io.StringIO()
    writer = csv.writer(output)

    # Header row
    writer.writerow([label for _, label in columns])

    # Data rows
    for row in data:
        writer.writerow([row.get(key, "") for key, _ in columns])

    response = make_response(output.getvalue())
    response.headers["Content-Type"] = "text/csv; charset=utf-8"
    response.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


def export_pdf(data, title, columns, filename=None):
    """Generate a PDF report using ReportLab.

    Args:
        data: list of dicts (rows)
        title: report title string
        columns: list of (key, header_label, width) tuples
        filename: download filename

    Returns:
        Flask Response with PDF content
    """
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import landscape, letter
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib.units import inch
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    except ImportError:
        from flask import jsonify

        return jsonify({"error": "PDF generation not available. Install reportlab."}), 500

    if not filename:
        filename = f'{title.lower().replace(" ", "_")}_{datetime.now().strftime("%Y-%m-%d")}.pdf'

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(letter), topMargin=0.5 * inch, bottomMargin=0.5 * inch)

    styles = getSampleStyleSheet()
    elements = []

    # Title
    elements.append(Paragraph(title, styles["Title"]))
    elements.append(Spacer(1, 12))

    # Subtitle with date
    elements.append(Paragraph(f"Generated: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}", styles["Normal"]))
    elements.append(Spacer(1, 18))

    if not data:
        elements.append(Paragraph("No data available.", styles["Normal"]))
    else:
        # Build table
        col_keys = [key for key, _, *_ in columns]
        col_labels = [label for _, label, *_ in columns]
        table_data = [col_labels]

        for row in data:
            table_data.append([str(row.get(key, "")) for key in col_keys])

        # Calculate column widths
        page_width = landscape(letter)[0] - 1 * inch
        col_count = len(columns)
        col_widths = [page_width / col_count] * col_count
        # Use explicit widths if provided
        for i, col in enumerate(columns):
            if len(col) >= 3 and col[2]:
                col_widths[i] = col[2]

        table = Table(table_data, colWidths=col_widths, repeatRows=1)
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.Color(0.102, 0.302, 0.180)),  # #1a4d2e
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, 0), 9),
                    ("FONTSIZE", (0, 1), (-1, -1), 8),
                    ("ALIGN", (0, 0), (-1, 0), "CENTER"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.Color(0.95, 0.97, 0.95)]),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        elements.append(table)

    doc.build(elements)

    response = make_response(buffer.getvalue())
    response.headers["Content-Type"] = "application/pdf"
    response.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response
