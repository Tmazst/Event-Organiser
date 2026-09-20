from io import BytesIO
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import reportlab
from reportlab.platypus import Image as ReportImage
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


TEAL = colors.HexColor("#176B63")
INK = colors.HexColor("#1F2933")
MUTED = colors.HexColor("#66737D")
PALE = colors.HexColor("#EAF4F2")
FONT_DIR = Path(reportlab.__file__).parent / "fonts"
pdfmetrics.registerFont(TTFont("UmcimbySans", str(FONT_DIR / "Vera.ttf")))
pdfmetrics.registerFont(TTFont("UmcimbySansBold", str(FONT_DIR / "VeraBd.ttf")))


def build_event_report(event):
    output = BytesIO()
    document = SimpleDocTemplate(
        output, pagesize=A4, rightMargin=18 * mm, leftMargin=18 * mm,
        topMargin=18 * mm, bottomMargin=18 * mm,
        title=f"{event.title} - Umcimby Event Report",
    )
    styles = getSampleStyleSheet()
    styles["Normal"].fontName = "UmcimbySans"
    styles["BodyText"].fontName = "UmcimbySans"
    styles["Heading2"].fontName = "UmcimbySansBold"
    styles.add(ParagraphStyle(name="ReportTitle", parent=styles["Title"], textColor=TEAL,
                              fontName="UmcimbySansBold", fontSize=24, leading=28, spaceAfter=5 * mm))
    styles.add(ParagraphStyle(name="Label", parent=styles["Normal"], textColor=MUTED,
                              fontSize=8, leading=10, spaceAfter=1 * mm))
    styles.add(ParagraphStyle(name="RightMoney", parent=styles["Normal"], alignment=TA_RIGHT))

    selected_total = sum((category.selected_amount for category in event.categories), start=0)
    remaining = event.budget_target - selected_total
    event_date = event.event_date.strftime("%d %B %Y") if event.event_date else "Not set"
    event_type = (event.event_type or "Other").replace("_", " ").title()

    logo_path = Path(__file__).parent / "static" / "images" / "umcimby-logo.png"
    story = [
        ReportImage(str(logo_path), width=58 * mm, height=20 * mm),
        Spacer(1, 4 * mm),
        Paragraph(event.title, styles["ReportTitle"]),
        Table([
            [Paragraph("EVENT TYPE", styles["Label"]), Paragraph("DATE", styles["Label"]), Paragraph("LOCATION", styles["Label"])],
            [event_type, event_date, event.location or "Not set"],
        ], colWidths=[55 * mm, 55 * mm, 46 * mm], style=TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), PALE), ("TEXTCOLOR", (0, 1), (-1, -1), INK),
            ("FONTNAME", (0, 0), (-1, -1), "UmcimbySans"),
            ("FONTSIZE", (0, 0), (-1, 0), 7), ("FONTSIZE", (0, 1), (-1, -1), 9),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CFE3DF")),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CFE3DF")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8), ("TOPPADDING", (0, 0), (-1, -1), 7),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ])),
        Spacer(1, 6 * mm),
    ]
    if event.description:
        story.extend([Paragraph("Event summary", styles["Heading2"]), Paragraph(event.description, styles["BodyText"]), Spacer(1, 5 * mm)])

    story.extend([
        Paragraph("Budget summary", styles["Heading2"]),
        Table([
            ["Total budget", "Current estimate", "Remaining" if remaining >= 0 else "Over budget"],
            [f"E{event.budget_target:,.2f}", f"E{selected_total:,.2f}", f"E{abs(remaining):,.2f}"],
        ], colWidths=[52 * mm] * 3, style=TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), TEAL), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, -1), "UmcimbySansBold"),
            ("FONTSIZE", (0, 0), (-1, 0), 8), ("FONTSIZE", (0, 1), (-1, 1), 12),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"), ("BOX", (0, 0), (-1, -1), 0.5, TEAL),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CFE3DF")),
            ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ])),
        Spacer(1, 7 * mm), Paragraph("Budget and selected quotations", styles["Heading2"]),
    ])

    rows = [["Budget item", "Planned", "Selected vendor", "Final amount"]]
    for category in event.categories:
        quote = category.selected_quote
        rows.append([
            category.name,
            f"E{category.planned_amount:,.2f}",
            quote.vendor_name if quote else "Not selected",
            f"E{category.selected_amount:,.2f}",
        ])
    if len(rows) == 1:
        rows.append(["No budget items added", "-", "-", "-"])
    story.append(Table(rows, repeatRows=1, colWidths=[46 * mm, 30 * mm, 52 * mm, 32 * mm], style=TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), INK), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, -1), "UmcimbySans"),
        ("FONTNAME", (0, 0), (-1, 0), "UmcimbySansBold"), ("ALIGN", (1, 1), (1, -1), "RIGHT"),
        ("FONTSIZE", (0, 0), (-1, 0), 8), ("FONTSIZE", (0, 1), (-1, -1), 8.5),
        ("ALIGN", (3, 1), (3, -1), "RIGHT"), ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, PALE]),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#D8E1E4")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6), ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ])))

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor("#D8E1E4"))
        canvas.line(18 * mm, 13 * mm, 192 * mm, 13 * mm)
        canvas.setFont("UmcimbySans", 8)
        canvas.setFillColor(MUTED)
        canvas.drawString(18 * mm, 8 * mm, "Generated by Umcimby Event Planner")
        canvas.drawRightString(192 * mm, 8 * mm, f"Page {doc.page}")
        canvas.restoreState()

    document.build(story, onFirstPage=footer, onLaterPages=footer)
    output.seek(0)
    return output
