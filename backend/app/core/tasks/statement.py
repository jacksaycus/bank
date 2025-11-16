from datetime import datetime, timedelta
from io import BytesIO

from celery import Task
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from backend.app.core.celery_app import celery_app
from backend.app.core.config import settings
from backend.app.core.logging import get_logger

logger = get_logger()


class StatementGenerationTask(Task):
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        logger.error(f"Statement generation failed: {exc}", exc_info=einfo)
        super().on_failure(exc, task_id, args, kwargs, einfo)


@celery_app.task(
    base=StatementGenerationTask,
    name="generate_statement_pdf",
    bind=True,
    max_retries=3,
    soft_time_limit=300,
)
def generate_statement_pdf(self, statement_data: dict, statement_id: str) -> dict:
    try:
        buffer = BytesIO()
        PAGE_WIDTH = A4[0]

        MARGIN = 72

        USABLE_WIDTH = PAGE_WIDTH - (2 * MARGIN)

        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=MARGIN,
            leftMargin=MARGIN,
            topMargin=MARGIN,
            bottomMargin=MARGIN,
        )

        styles = getSampleStyleSheet()

        styles.add(
            ParagraphStyle(name="SmallText", parent=styles["Normal"], fontSize=8)
        )

        styles.add(
            ParagraphStyle(
                name="AccountInfo", parent=styles["Normal"], fontSize=10, spaceAfter=6
            )
        )

        styles.add(
            ParagraphStyle(
                name="SectionTitle",
                parent=styles["Heading3"],
                fontSize=12,
                spaceAfter=6,
                alignment=1,
            )
        )

        elements = []

        elements.append(
            Paragraph(f"{settings.SITE_NAME} Account Statement", styles["Heading1"])
        )

        elements.append(Spacer(1, 12))

        elements.append(
            Paragraph(
                f"Statement Period: {statement_data['start_date']} to {statement_data['end_date']}",
                styles["Normal"],
            )
        )

        elements.append(Spacer(1, 12))

        user = statement_data["user"]

        account = (
            user["accounts"][0]
            if statement_data.get("is_single_account")
            else user["accounts"][0]
        )

        col_width = USABLE_WIDTH / 2

        user_info = [
            [Paragraph("Customer Information:", styles["Heading4"]), ""],
            ["Name:", user["full_name"]],
            ["Username:", user["username"]],
            ["Email:", user["email"]],
        ]

        account_info = [
            [Paragraph("Account Information:", styles["Heading4"]), ""],
            ["Account Number:", account["account_number"]],
            ["Account Name:", account["account_name"]],
            ["Account Type:", account["account_type"]],
            ["Currency:", account["currency"]],
            ["Current Balance:", str(account["balance"])],
        ]
        table_style = TableStyle(
            [
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                (
                    "FONTNAME",
                    (0, 1),
                    (0, -1),
                    "Helvetica-Bold",
                ),
                ("FONTNAME", (1, 1), (1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("SPAN", (0, 0), (1, 0)),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ]
        )

        label_width = col_width * 0.4
        value_width = col_width * 0.6

        user_table = Table(user_info, colWidths=[label_width, value_width])

        user_table.setStyle(table_style)

        account_table = Table(account_info, colWidths=[label_width, value_width])

        account_table.setStyle(table_style)

        wrapper_table = Table(
            [[user_table, account_table]],
            colWidths=[col_width, col_width],
            spaceBefore=10,
            spaceAfter=10,
        )

        wrapper_table.setStyle(
            TableStyle(
                [
                    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 10),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ]
            )
        )

        elements.append(wrapper_table)
        elements.append(Spacer(1, 20))

        transactions = statement_data["transactions"]

        if transactions:
            elements.append(Paragraph("Transaction History", styles["SectionTitle"]))
            elements.append(Spacer(1, 12))

            table_data = [
                ["Date", "Reference", "Description", "Type", "Amount", "Balance"]
            ]

            for txn in transactions:
                amount_str = (
                    f"+{txn["amount"]}"
                    if txn["transaction_category"] == "credit"
                    else f"-{txn["amount"]}"
                )
                description = (
                    txn["description"][:30] + "..."
                    if len(txn["description"]) > 30
                    else txn["description"]
                )
                table_data.append(
                    [
                        txn["created_at"],
                        txn["reference"],
                        description,
                        txn["transaction_type"],
                        amount_str,
                        txn["balance_after"],
                    ]
                )
            col_ratios = [0.12, 0.20, 0.30, 0.15, 0.11, 0.12]

            trans_col_widths = [USABLE_WIDTH * ratio for ratio in col_ratios]

            trans_table = Table(table_data, colWidths=trans_col_widths, repeatRows=1)

            trans_table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                        ("FONTSIZE", (0, 0), (-1, 0), 10),
                        ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
                        ("BACKGROUND", (0, 1), (-1, -1), colors.white),
                        ("TEXTCOLOR", (0, 1), (-1, -1), colors.black),
                        ("FONTSIZE", (0, 1), (-1, -1), 8),
                        ("ALIGN", (0, 1), (-1, -1), "CENTER"),
                        ("GRID", (0, 0), (-1, -1), 1, colors.black),
                    ]
                )
            )
            elements.append(trans_table)
        else:
            elements.append(
                Paragraph("No transaction found for this period.", styles["Normal"])
            )

        elements.append(Spacer(1, 12))
        elements.append(
            Paragraph(
                f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                styles["SmallText"],
            )
        )
        elements.append(
            Paragraph(
                "This is a computer-generated statement and does not require signature.",
                styles["SmallText"],
            )
        )

        doc.build(elements)
        pdf_data = buffer.getvalue()
        buffer.close()

        redis_client = celery_app.backend.client
        redis_key = f"statement:{statement_id}"
        redis_client.setex(redis_key, 3600, pdf_data)

        return {
            "status": "success",
            "statement_id": statement_id,
            "generated_at": datetime.now().isoformat(),
            "expires_at": (datetime.now() + timedelta(hours=1)).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to generate statement: {e}")
        raise self.retry(exc=e, countdown=5)
    