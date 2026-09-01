"""utils/helpers.py — presentation helpers with no database access of their
own (pure functions), carried forward from the original desktop app almost
unchanged (Phase 10: preserve existing workflow)."""

import base64
import io

import pandas as pd

GRADE_TABLE = [
    (90, 100, "A+"), (80, 89.99, "A"), (70, 79.99, "B+"),
    (60, 69.99, "B"), (50, 59.99, "C"), (40, 49.99, "D"), (0, 39.99, "F"),
]


def grade_for(pct):
    for low, high, g in GRADE_TABLE:
        if low <= pct <= high:
            return g
    return "N/A"


def image_to_b64(uploaded_file):
    if uploaded_file is None:
        return None
    return base64.b64encode(uploaded_file.getvalue()).decode("utf-8")


def b64_to_bytes(b64str):
    if not b64str:
        return None
    return base64.b64decode(b64str)


def to_excel_bytes(dataframe: pd.DataFrame, sheet_name="Report"):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        dataframe.to_excel(writer, index=False, sheet_name=sheet_name)
        ws = writer.sheets[sheet_name]
        for i, col in enumerate(dataframe.columns, start=1):
            max_len = max([len(str(col))] + [len(str(v)) for v in dataframe[col].astype(str)])
            letter = chr(64 + i) if i <= 26 else "A"
            ws.column_dimensions[letter].width = min(max_len + 3, 45)
    return output.getvalue()


def build_receipt_html(student, school, receipt_no, amount, discount, fine, mode, fee_head):
    from datetime import date
    total = amount - discount + fine
    return f"""
    <html><head><meta charset="utf-8"><style>
    body {{ font-family: Arial, sans-serif; padding: 30px; }}
    .receipt {{ border: 2px solid #333; padding: 25px; max-width: 500px; }}
    table {{ width: 100%; border-collapse: collapse; margin-top: 15px; }}
    td {{ padding: 6px 0; border-bottom: 1px solid #eee; }}
    </style></head><body>
    <div class="receipt">
        <h2>{school['school_name']}</h2>
        <p>{school.get('address') or ''}</p>
        <h3>Fee Receipt</h3>
        <table>
        <tr><td>Receipt No</td><td>{receipt_no}</td></tr>
        <tr><td>Student Name</td><td>{student['full_name']}</td></tr>
        <tr><td>Admission No</td><td>{student['admission_no']}</td></tr>
        <tr><td>Fee Head</td><td>{fee_head}</td></tr>
        <tr><td>Amount Paid</td><td>₹{amount:,.2f}</td></tr>
        <tr><td>Discount</td><td>₹{discount:,.2f}</td></tr>
        <tr><td>Fine</td><td>₹{fine:,.2f}</td></tr>
        <tr><td><b>Net Total</b></td><td><b>₹{total:,.2f}</b></td></tr>
        <tr><td>Payment Mode</td><td>{mode}</td></tr>
        <tr><td>Date</td><td>{date.today().isoformat()}</td></tr>
        </table>
        <p style="margin-top:30px;">{school.get('receipt_footer') or ''}</p>
    </div>
    </body></html>
    """


def build_certificate_html(student, school, cert_type, extra_note=""):
    from datetime import date
    return f"""
    <html><head><meta charset="utf-8"><style>
    body {{ font-family: 'Georgia', serif; padding: 50px; }}
    .box {{ border: 6px double #2b3166; padding: 40px; text-align:center; }}
    h1 {{ color:#2b3166; }}
    .sign {{ margin-top:60px; display:flex; justify-content:space-between; }}
    </style></head><body>
    <div class="box">
        <h1>{school['school_name']}</h1>
        <p>{school.get('address') or ''} &nbsp; | &nbsp; {school.get('phone') or ''} &nbsp; | &nbsp; {school.get('email') or ''}</p>
        <h2>{cert_type.upper()}</h2>
        <p>This is to certify that <b>{student['full_name']}</b>, Admission No. <b>{student['admission_no']}</b>,
        was a bonafide student of this institution.</p>
        <p>Date of Birth: <b>{student.get('dob') or '-'}</b></p>
        <p>{extra_note}</p>
        <p>Issued on: {date.today().strftime('%d %B %Y')}</p>
        <div class="sign">
            <span>_________________________<br>Class Teacher</span>
            <span>_________________________<br>Principal</span>
        </div>
    </div>
    </body></html>
    """


def build_report_card_html(student, school, exam_name, result_df, total, max_total, pct, grade, rank):
    rows = "".join(
        f"<tr><td>{r.Subject}</td><td>{r.Obtained:.0f}</td><td>{r.Max:.0f}</td></tr>"
        for r in result_df.itertuples()
    )
    return f"""
    <html><head><meta charset="utf-8"><style>
    body {{ font-family: Arial, sans-serif; padding: 30px; }}
    table {{ width:100%; border-collapse: collapse; margin-top:15px;}}
    th, td {{ border: 1px solid #ccc; padding: 8px; text-align:left; }}
    </style></head><body>
    <h2>{school['school_name']}</h2>
    <h3>Report Card &mdash; {exam_name}</h3>
    <p>Name: <b>{student['full_name']}</b> &nbsp; Admission No: <b>{student['admission_no']}</b></p>
    <table><tr><th>Subject</th><th>Marks Obtained</th><th>Max Marks</th></tr>{rows}</table>
    <p style="margin-top:15px;">Total: <b>{total:.0f}/{max_total:.0f}</b> &nbsp; Percentage: <b>{pct}%</b>
    &nbsp; Grade: <b>{grade}</b> &nbsp; Rank: <b>{rank}</b></p>
    </body></html>
    """
