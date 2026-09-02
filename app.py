"""
app.py — EduManage Pro SaaS entrypoint.

This file owns presentation only (pages, forms, CSS). It never issues raw
SQL — every data operation goes through services/*.py, and every one of
those calls is passed `st.session_state.user["school_id"]`, which is set
exactly once, at login, from the authenticated user's own database row
(see auth/authentication.py). No page here ever reads a school_id from a
URL, form field, or anything else the browser could tamper with.
"""

from datetime import date, datetime, timedelta

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import config
from database.connection import health_check
from auth.authentication import authenticate, signup_user, change_password
from auth.authorization import (
    ROLES, SIGNUP_ROLES, PLATFORM_ROLE, ROLE_PERMISSIONS, has_access, is_platform_role,
)
from services import school_service as school_svc
from services import academic_service as academic_svc
from services import finance_service as finance_svc
from services import hr_service as hr_svc
from services import facilities_service as facilities_svc
from services import communication_service as comm_svc
from services import report_service as report_svc
from services import audit_service as audit_svc
from utils.helpers import (
    grade_for, image_to_b64, b64_to_bytes, to_excel_bytes,
    build_receipt_html, build_certificate_html, build_report_card_html,
)

APP_NAME = config.APP_NAME


# ==============================================================================
# STYLING — copied forward from the audited desktop app (Phase 10)
# ==============================================================================

def inject_css():
    theme = st.session_state.get("theme", "Light")
    if theme == "Dark":
        bg, panel, text, subtext, border = "#0f1420", "#171d2e", "#eef1f8", "#a3acc2", "#2a3350"
    else:
        bg, panel, text, subtext, border = "#f4f6fb", "#ffffff", "#1c2333", "#5b6479", "#e6e9f2"

    st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700;800&display=swap');
    html, body, [class*="css"] {{ font-family: 'Poppins', sans-serif; }}
    .stApp {{ background: {bg}; color: {text}; }}
    section[data-testid="stSidebar"] {{ background: linear-gradient(180deg, #1a1f3c 0%, #2b3166 100%); }}
    section[data-testid="stSidebar"] * {{ color: #f1f3fb !important; }}

    div[data-testid="stMetric"] {{
        background: {panel}; border: 1px solid {border}; border-radius: 14px;
        padding: 14px 16px; box-shadow: 0 2px 10px rgba(20,25,50,0.06);
    }}
    .kpi-card {{ border-radius: 16px; padding: 18px 20px; color: white;
        box-shadow: 0 6px 18px rgba(20,25,60,0.18); min-height: 108px; }}
    .kpi-title {{ font-size: 13px; opacity: 0.9; font-weight: 500; }}
    .kpi-value {{ font-size: 28px; font-weight: 800; margin-top: 6px; }}
    .grad-1 {{ background: linear-gradient(135deg,#6a5cf5,#8f7bff); }}
    .grad-2 {{ background: linear-gradient(135deg,#17b88f,#3fd6ac); }}
    .grad-3 {{ background: linear-gradient(135deg,#ff8a3d,#ffb057); }}
    .grad-4 {{ background: linear-gradient(135deg,#ff5f8f,#ff8ab0); }}
    .grad-5 {{ background: linear-gradient(135deg,#2f8fff,#5fb2ff); }}
    .grad-6 {{ background: linear-gradient(135deg,#ff4d6d,#ff7a92); }}
    .grad-7 {{ background: linear-gradient(135deg,#22c1c3,#5cdbdd); }}
    .grad-8 {{ background: linear-gradient(135deg,#7b61ff,#b18bff); }}
    .grad-9 {{ background: linear-gradient(135deg,#f7b733,#fc4a1a); }}
    .grad-10 {{ background: linear-gradient(135deg,#43cea2,#185a9d); }}

    .stButton>button {{
        background: linear-gradient(135deg,#6a5cf5,#8f7bff); color: white; border: none;
        border-radius: 10px; padding: 0.5em 1.2em; font-weight: 600;
        box-shadow: 0 3px 10px rgba(106,92,245,0.25);
    }}
    section[data-testid="stSidebar"] div[data-testid="stButton"] > button {{
        text-align: left; justify-content: flex-start; border: none; border-radius: 10px;
        font-weight: 600; opacity: 0.92; box-shadow: 0 2px 8px rgba(0,0,0,0.18);
    }}
    section[data-testid="stSidebar"] div[data-testid="stButton"] > button[kind="primary"] {{
        opacity: 1; box-shadow: 0 0 0 2px rgba(255,255,255,0.55), 0 4px 14px rgba(0,0,0,0.35) !important;
    }}
    .st-key-nav_Dashboard button {{ background: linear-gradient(135deg,#6a5cf5,#8f7bff) !important; }}
    .st-key-nav_Students button {{ background: linear-gradient(135deg,#17b88f,#3fd6ac) !important; }}
    .st-key-nav_Classes button {{ background: linear-gradient(135deg,#ff8a3d,#ffb057) !important; }}
    .st-key-nav_Attendance button {{ background: linear-gradient(135deg,#ff5f8f,#ff8ab0) !important; }}
    .st-key-nav_Fees button {{ background: linear-gradient(135deg,#2f8fff,#5fb2ff) !important; }}
    .st-key-nav_Exams button {{ background: linear-gradient(135deg,#ff4d6d,#ff7a92) !important; }}
    .st-key-nav_Teachers button {{ background: linear-gradient(135deg,#22c1c3,#5cdbdd) !important; }}
    .st-key-nav_Staff button {{ background: linear-gradient(135deg,#7b61ff,#b18bff) !important; }}
    .st-key-nav_Library button {{ background: linear-gradient(135deg,#f7b733,#fc4a1a) !important; }}
    .st-key-nav_Transport button {{ background: linear-gradient(135deg,#43cea2,#185a9d) !important; }}
    .st-key-nav_Hostel button {{ background: linear-gradient(135deg,#8e54e9,#4776e6) !important; }}
    .st-key-nav_Notice-Board button {{ background: linear-gradient(135deg,#f857a6,#ff5858) !important; }}
    .st-key-nav_Certificates button {{ background: linear-gradient(135deg,#00b09b,#96c93d) !important; }}
    .st-key-nav_Reports button {{ background: linear-gradient(135deg,#ee0979,#ff6a00) !important; }}
    .st-key-nav_Global-Search button {{ background: linear-gradient(135deg,#2193b0,#6dd5ed) !important; }}
    .st-key-nav_Settings button {{ background: linear-gradient(135deg,#636fa4,#e8cbc0) !important; }}
    .st-key-nav_logout button {{ background: linear-gradient(135deg,#e14361,#ff7a92) !important; }}

    div[data-testid="stForm"] {{ background: {panel}; border: 1px solid {border}; border-radius: 16px; padding: 20px; }}
    .app-header {{ padding: 14px 20px; border-radius: 16px; background: linear-gradient(120deg,#1a1f3c,#3b3f8f); color: white; margin-bottom: 18px; }}
    .app-header h2 {{ margin: 0; }}
    .app-header span {{ opacity: 0.85; font-size: 13px; }}
    .section-card {{ background: {panel}; border: 1px solid {border}; border-radius: 16px; padding: 18px; margin-bottom: 14px; }}
    .badge {{ display: inline-block; padding: 3px 10px; border-radius: 999px; font-size: 12px; font-weight: 600; }}
    .badge-green {{ background:#dcf7ec; color:#0f9d64; }}
    .badge-red {{ background:#fde3e8; color:#e14361; }}
    .badge-orange {{ background:#fff1de; color:#e18b1f; }}
    footer {{visibility: hidden;}}
    #MainMenu {{visibility: hidden;}}

    @media (max-width: 768px) {{
        .app-header {{ padding: 10px 14px; }} .app-header h2 {{ font-size: 1.15rem; }}
        .kpi-card {{ padding: 12px 14px; min-height: 84px; }} .kpi-value {{ font-size: 22px; }}
    }}
    </style>
    """, unsafe_allow_html=True)


def page_header(title, subtitle=""):
    st.markdown(f'<div class="app-header"><h2>{title}</h2><span>{subtitle}</span></div>', unsafe_allow_html=True)


def kpi_card(col, title, value, grad_class):
    col.markdown(f'<div class="kpi-card {grad_class}"><div class="kpi-title">{title}</div>'
                 f'<div class="kpi-value">{value}</div></div>', unsafe_allow_html=True)


def alert(msg, kind="success"):
    {"success": st.success, "error": st.error}.get(kind, st.warning)(msg)


# ==============================================================================
# LOGIN / SCHOOL REGISTRATION / SUBSCRIPTION SCREENS
# ==============================================================================

def screen_login():
    inject_css()
    st.markdown(f"""
    <div style="text-align:center; margin-top:30px;">
        <h1 style="font-weight:800;">🏫 {APP_NAME}</h1>
        <p style="color:#5b6479;">Multi-School SaaS Edition</p>
    </div>
    """, unsafe_allow_html=True)

    _, mid, _ = st.columns([1, 1.2, 1])
    with mid:
        tab_signin, tab_register = st.tabs(["🔐 Sign In", "🏫 Register School"])

        with tab_signin:
            with st.form("login_form"):
                username = st.text_input("Username")
                password = st.text_input("Password", type="password")
                submitted = st.form_submit_button("Login", use_container_width=True)
                if submitted:
                    user = authenticate(username, password)
                    if user:
                        st.session_state.user = user
                        audit_svc.log(user["school_id"], user["id"], "login")
                        st.rerun()
                    else:
                        alert("Invalid username or password, or this account is inactive.", "error")
            st.caption("Just exploring? Use username **demo** / password **demo1234** — a fully working sample school.")

        with tab_register:
            st.caption("Register your school and get your own Super Admin account. No trial — activate with a subscription key now, or after registering.")
            with st.form("register_form", clear_on_submit=True):
                school_name = st.text_input("School Name *")
                col1, col2 = st.columns(2)
                phone = col1.text_input("School Phone")
                email = col2.text_input("School Email")
                address = st.text_area("School Address")
                principal_name = st.text_input("Principal / Administrator Name")
                st.markdown("---")
                col3, col4 = st.columns(2)
                admin_username = col3.text_input("Choose Admin Username *")
                admin_full_name = col4.text_input("Admin Full Name *")
                col5, col6 = st.columns(2)
                admin_password = col5.text_input("Password *", type="password")
                confirm_password = col6.text_input("Confirm Password *", type="password")
                st.markdown("---")
                license_key = st.text_input(
                    "Subscription Key (optional)",
                    placeholder="EDU-M-XXXX-XXXX-XXXX (Monthly) or EDU-Y-XXXX-XXXX-XXXX (Yearly)",
                    help="Have a key already? Enter it here to activate immediately. Otherwise you can activate later after signing in.",
                )
                submitted = st.form_submit_button("Register School", use_container_width=True)
                if submitted:
                    if admin_password != confirm_password:
                        alert("Passwords do not match.", "error")
                    else:
                        ok, msg, school_id = school_svc.register_school(
                            school_name, address, phone, email, principal_name,
                            admin_username, admin_password, admin_full_name)
                        if ok and license_key.strip():
                            key_ok, key_msg = school_svc.activate_subscription(school_id, license_key.strip())
                            msg = f"{msg} {key_msg}"
                            ok = ok and key_ok
                        alert(msg, "success" if ok else "error")


def screen_subscription(status_info, school):
    inject_css()
    status = status_info["status"]
    st.markdown(f"""
    <div style="text-align:center; margin-top:30px;">
        <h1>🔒 Subscription {'Required' if status=='pending' else status.capitalize()}</h1>
        <p style="color:#5b6479;">{school['school_name']} (Code: {school['school_code']})</p>
        <p style="color:#5b6479;">Signed in as <b>{st.session_state.user['full_name']}</b></p>
    </div>
    """, unsafe_allow_html=True)

    _, mid, _ = st.columns([1, 1.1, 1])
    with mid:
        if status == "suspended":
            st.error("This school's account has been suspended by the platform administrator. Please contact support.")
        else:
            st.info(f"📅 Monthly plan: {config.MONTHLY_VALIDITY_DAYS} days · 📆 Yearly plan: {config.YEARLY_VALIDITY_DAYS} days — no free trial.")
            with st.form("activation_form"):
                key_input = st.text_input("Subscription Key", placeholder="EDU-M-XXXX-XXXX-XXXX or EDU-Y-XXXX-XXXX-XXXX")
                submitted = st.form_submit_button("Activate Now", use_container_width=True)
                if submitted:
                    if not key_input:
                        alert("Please enter a subscription key.", "error")
                    else:
                        ok, msg = school_svc.activate_subscription(school["id"], key_input)
                        alert(msg, "success" if ok else "error")
                        if ok:
                            st.rerun()
        if st.button("Logout", use_container_width=True):
            del st.session_state.user
            st.rerun()


# ==============================================================================
# DASHBOARD
# ==============================================================================

def page_dashboard(sid):
    page_header("📊 Dashboard", f"Welcome back, {st.session_state.user['full_name']} ({st.session_state.user['role']})")
    k = report_svc.dashboard_kpis(sid)

    row1 = st.columns(5)
    kpi_card(row1[0], "Total Students", k["total_students"], "grad-1")
    kpi_card(row1[1], "Total Teachers", k["total_teachers"], "grad-2")
    kpi_card(row1[2], "Total Staff", k["total_staff"], "grad-3")
    kpi_card(row1[3], "Today's Attendance", k["today_attendance"], "grad-4")
    kpi_card(row1[4], "New Admissions (30d)", k["new_admissions"], "grad-5")

    st.write("")
    row2 = st.columns(5)
    kpi_card(row2[0], "Fees Collected Today", f"₹{k['fees_today']:,.0f}", "grad-6")
    kpi_card(row2[1], "Pending Fees", f"₹{k['pending_fees']:,.0f}", "grad-7")
    kpi_card(row2[2], "Library Books", k["library_books"], "grad-8")
    kpi_card(row2[3], "Issued Books", k["issued_books"], "grad-9")
    bdays = report_svc.todays_birthdays(sid)
    kpi_card(row2[4], "Today's Birthdays", len(bdays), "grad-10")

    st.write("")
    left, right = st.columns([1.3, 1])
    with left:
        st.markdown("##### 📈 Attendance Trend (Last 14 days)")
        att_df = report_svc.attendance_trend_df(sid)
        if not att_df.empty:
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=att_df["att_date"], y=att_df["present"], mode="lines+markers", name="Present", line=dict(color="#17b88f", width=3)))
            fig.add_trace(go.Scatter(x=att_df["att_date"], y=att_df["absent"], mode="lines+markers", name="Absent", line=dict(color="#ff5f8f", width=3)))
            fig.update_layout(height=320, margin=dict(l=10, r=10, t=10, b=10), plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", legend=dict(orientation="h", y=1.1))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No attendance data recorded yet.")
    with right:
        st.markdown("##### 🎓 Students by Class")
        class_df = report_svc.students_by_class_df(sid)
        if not class_df.empty:
            fig2 = px.pie(class_df, names="class_label", values="cnt", hole=0.5, color_discrete_sequence=px.colors.sequential.Purples_r)
            fig2.update_layout(height=320, margin=dict(l=10, r=10, t=10, b=10))
            st.plotly_chart(fig2, use_container_width=True)
        else:
            st.info("No classes created yet.")

    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("##### 🎂 Today's Birthdays")
        for b in bdays:
            st.markdown(f"🎉 **{b['full_name']}**")
        if not bdays:
            st.caption("No birthdays today.")
    with col_b:
        st.markdown("##### 🔔 Recent Notices")
        for n in comm_svc.list_notices(sid, limit=5):
            st.markdown(f"**{n['title']}** &nbsp; `{n['notice_date']}`  \n{n['description'] or ''}")


# ==============================================================================
# STUDENTS
# ==============================================================================

def page_students(sid):
    page_header("🎓 Student Management", "Admission, profiles, search, promotion and more")
    tabs = st.tabs(["➕ Admission", "🔍 Search / Profile", "✏️ Update", "⬆️ Promotion / Transfer"])
    c_opts = academic_svc.class_options(sid)

    with tabs[0]:
        if not c_opts:
            st.warning("Please create at least one Class & Section first (Classes module).")
        with st.form("admission_form", clear_on_submit=True):
            col1, col2, col3 = st.columns(3)
            full_name = col1.text_input("Full Name *")
            dob = col2.date_input("Date of Birth", value=date(2015, 1, 1), min_value=date(1990, 1, 1), max_value=date.today())
            gender = col3.selectbox("Gender", ["Male", "Female", "Other"])
            col4, col5, col6 = st.columns(3)
            blood_group = col4.selectbox("Blood Group", ["A+", "A-", "B+", "B-", "O+", "O-", "AB+", "AB-", "Unknown"])
            category = col5.selectbox("Category", ["General", "OBC", "SC", "ST", "Other"])
            class_label = col6.selectbox("Class - Section *", list(c_opts.keys()) if c_opts else ["-"])
            col7, col8 = st.columns(2)
            father_name = col7.text_input("Father's Name")
            mother_name = col8.text_input("Mother's Name")
            col9, col10 = st.columns(2)
            guardian_phone = col9.text_input("Guardian Phone *")
            guardian_email = col10.text_input("Guardian Email")
            address = st.text_area("Address")
            col11, col12 = st.columns(2)
            transport_required = col11.checkbox("Needs Transport")
            hostel_required = col12.checkbox("Needs Hostel")
            photo = st.file_uploader("Student Photo", type=["png", "jpg", "jpeg"])
            submitted = st.form_submit_button("Admit Student", use_container_width=True)
            if submitted:
                if not full_name or not guardian_phone or not c_opts:
                    alert("Full Name, Guardian Phone and a Class are required.", "error")
                else:
                    adm_no = academic_svc.next_admission_no(sid)
                    stu_id = academic_svc.next_student_id(sid)
                    academic_svc.add_student(
                        sid, admission_no=adm_no, student_id=stu_id, full_name=full_name,
                        dob=dob, gender=gender, blood_group=blood_group, category=category,
                        class_id=c_opts[class_label], father_name=father_name, mother_name=mother_name,
                        guardian_phone=guardian_phone, guardian_email=guardian_email, address=address,
                        transport_required=transport_required, hostel_required=hostel_required,
                        photo_blob=image_to_b64(photo),
                    )
                    audit_svc.log(sid, st.session_state.user["id"], "student_create", adm_no)
                    alert(f"Student admitted! Admission No: {adm_no} · Student ID: {stu_id}", "success")

    with tabs[1]:
        q = st.text_input("🔍 Search by name, admission no, student ID or phone")
        results = academic_svc.search_students_df(sid, q)
        st.caption(f"{len(results)} student(s) found")
        for _, r in results.head(50).iterrows():
            with st.expander(f"{r['full_name']} · {r['admission_no']} · Class {r['class_name'] or '-'}-{r['section'] or ''}"):
                cimg, cinfo = st.columns([1, 3])
                with cimg:
                    photo_bytes = b64_to_bytes(r["photo_blob"])
                    st.image(photo_bytes, width=120) if photo_bytes else st.markdown("🧑‍🎓")
                    badge = "badge-green" if r["status"] == "Active" else "badge-red"
                    st.markdown(f"<span class='badge {badge}'>{r['status']}</span>", unsafe_allow_html=True)
                with cinfo:
                    st.markdown(f"""
                    **Student ID:** {r['student_id']}  ·  **DOB:** {r['dob'] or '-'}  ·  **Gender:** {r['gender'] or '-'}  
                    **Father:** {r['father_name'] or '-'}  ·  **Mother:** {r['mother_name'] or '-'}  
                    **Guardian Phone:** {r['guardian_phone'] or '-'}  ·  **Email:** {r['guardian_email'] or '-'}  
                    **Address:** {r['address'] or '-'}
                    """)

    with tabs[2]:
        all_students = academic_svc.list_active_students(sid)
        options = {f"{s['full_name']} ({s['admission_no']})": s["id"] for s in all_students}
        if options:
            choice = st.selectbox("Select Student to Update", list(options.keys()))
            sid_pk = options[choice]
            rec = academic_svc.get_student(sid, sid_pk)
            inv_class = {v: k for k, v in c_opts.items()}
            with st.form("update_student_form"):
                col1, col2, col3 = st.columns(3)
                full_name = col1.text_input("Full Name", value=rec["full_name"])
                guardian_phone = col2.text_input("Guardian Phone", value=rec["guardian_phone"] or "")
                status_opts = ["Active", "Inactive", "Transferred", "Left"]
                status = col3.selectbox("Status", status_opts, index=status_opts.index(rec["status"]) if rec["status"] in status_opts else 0)
                current_label = inv_class.get(rec["class_id"], list(c_opts.keys())[0] if c_opts else "-")
                class_label = st.selectbox("Class - Section", list(c_opts.keys()) if c_opts else ["-"], index=list(c_opts.keys()).index(current_label) if current_label in c_opts else 0)
                submitted = st.form_submit_button("Save Changes", use_container_width=True)
                if submitted:
                    academic_svc.update_student(sid, sid_pk, full_name=full_name, guardian_phone=guardian_phone, status=status, class_id=c_opts.get(class_label))
                    audit_svc.log(sid, st.session_state.user["id"], "student_update", rec["admission_no"])
                    alert("Student record updated successfully.", "success")
        else:
            st.info("No students found. Please add a student first.")

    with tabs[3]:
        st.markdown("##### ⬆️ Class Promotion")
        if len(c_opts) >= 1:
            col1, col2 = st.columns(2)
            from_class = col1.selectbox("From Class - Section", list(c_opts.keys()), key="promo_from")
            to_class = col2.selectbox("To Class - Section", list(c_opts.keys()), key="promo_to")
            students_in_class = academic_svc.list_active_students(sid, c_opts[from_class])
            if students_in_class:
                sel = st.multiselect("Select students to promote", [f"{s['full_name']} ({s['admission_no']})" for s in students_in_class])
                if st.button("Promote Selected Students", use_container_width=True):
                    id_map = {f"{s['full_name']} ({s['admission_no']})": s["id"] for s in students_in_class}
                    ids = [id_map[label] for label in sel]
                    n = academic_svc.promote_students(sid, ids, c_opts[to_class])
                    alert(f"{n} student(s) promoted to {to_class}.", "success")
        else:
            st.info("Create classes first to enable promotion.")

        st.divider()
        st.markdown("##### 📄 Issue Transfer Certificate")
        all_students = academic_svc.list_active_students(sid)
        options = {f"{s['full_name']} ({s['admission_no']})": s["id"] for s in all_students}
        if options:
            choice = st.selectbox("Select Student", list(options.keys()), key="tc_select")
            reason = st.text_input("Reason for Transfer")
            if st.button("Generate Transfer Certificate", use_container_width=True):
                sid_pk = options[choice]
                academic_svc.update_student(sid, sid_pk, status="Transferred")
                comm_svc.log_certificate(sid, sid_pk, "Transfer Certificate")
                rec = academic_svc.get_student(sid, sid_pk)
                school = school_svc.get_school(sid)
                cert_html = build_certificate_html(rec, school, "Transfer Certificate", reason)
                st.success("Transfer Certificate generated.")
                st.download_button("⬇️ Download Certificate (HTML)", cert_html, file_name=f"TC_{rec['admission_no']}.html", mime="text/html")


# ==============================================================================
# CLASSES
# ==============================================================================

def page_classes(sid):
    page_header("🏷️ Class Management", "Classes, sections and academic sessions")
    col1, col2 = st.columns([1, 1.3])
    with col1:
        st.markdown("##### ➕ Create Class / Section")
        teachers = hr_svc.active_teachers(sid)
        t_opts = {t["full_name"]: t["id"] for t in teachers}
        with st.form("class_form", clear_on_submit=True):
            class_name = st.text_input("Class Name * (e.g. Grade 5)")
            section = st.text_input("Section * (e.g. A)")
            session = st.text_input("Academic Session *", value="2025-2026")
            teacher_choice = st.selectbox("Class Teacher", ["None"] + list(t_opts.keys()))
            submitted = st.form_submit_button("Create Class", use_container_width=True)
            if submitted:
                if not class_name or not section:
                    alert("Class Name and Section are required.", "error")
                else:
                    ok, msg = academic_svc.add_class(sid, class_name, section, session, t_opts.get(teacher_choice))
                    alert(msg, "success" if ok else "error")

    with col2:
        st.markdown("##### 📋 Existing Classes")
        classes_df = academic_svc.list_classes_df(sid)
        st.dataframe(classes_df.drop(columns=["id"]) if not classes_df.empty else classes_df, use_container_width=True, hide_index=True)
        if not classes_df.empty:
            labels = [f"{r.Class}-{r.Section} ({r.Session})" for r in classes_df.itertuples()]
            del_choice = st.selectbox("Delete a class", ["-"] + labels)
            if del_choice != "-" and st.button("🗑️ Delete Selected Class"):
                idx = labels.index(del_choice)
                ok, msg = academic_svc.delete_class(sid, int(classes_df.iloc[idx]["id"]))
                alert(msg, "success" if ok else "error")
                if ok:
                    st.rerun()


# ==============================================================================
# ATTENDANCE
# ==============================================================================

def page_attendance(sid):
    page_header("📅 Attendance", "Daily, class-wise, teacher and staff attendance")
    tabs = st.tabs(["🧑‍🎓 Student Attendance", "📊 Monthly Report", "🧑‍🏫 Teacher / Staff Attendance"])
    c_opts = academic_svc.class_options(sid)

    with tabs[0]:
        if not c_opts:
            st.info("Create a class first.")
        else:
            col1, col2 = st.columns(2)
            class_label = col1.selectbox("Class - Section", list(c_opts.keys()))
            att_date = col2.date_input("Attendance Date", value=date.today())
            students = academic_svc.list_active_students(sid, c_opts[class_label])
            if students:
                existing = academic_svc.get_attendance_for_class_date(sid, [s["id"] for s in students], att_date)
                with st.form("attendance_form"):
                    statuses = {}
                    for s in students:
                        default = existing.get(s["id"], "Present")
                        statuses[s["id"]] = st.radio(f"{s['full_name']} (Roll {s['roll_no'] or '-'})", ["Present", "Absent", "Leave"],
                                                      index=["Present", "Absent", "Leave"].index(default) if default in ["Present", "Absent", "Leave"] else 0,
                                                      horizontal=True, key=f"att_{s['id']}")
                    submitted = st.form_submit_button("Save Attendance", use_container_width=True)
                    if submitted:
                        for sid_stu, status in statuses.items():
                            academic_svc.mark_student_attendance(sid, sid_stu, att_date, status)
                        alert("Attendance saved successfully.", "success")
            else:
                st.info("No active students in this class.")

    with tabs[1]:
        col1, col2 = st.columns(2)
        class_label = col1.selectbox("Class - Section", ["All"] + list(c_opts.keys()), key="report_class")
        month = col2.text_input("Month (YYYY-MM)", value=date.today().strftime("%Y-%m"))
        report_df = academic_svc.attendance_report_df(sid, month, c_opts.get(class_label) if class_label != "All" else None)
        st.dataframe(report_df, use_container_width=True, hide_index=True)
        if not report_df.empty:
            st.download_button("⬇️ Export to Excel", to_excel_bytes(report_df, "Attendance"), file_name=f"attendance_{month}.xlsx")

    with tabs[2]:
        person_type = st.radio("Type", ["Teacher", "Staff"], horizontal=True)
        people = hr_svc.active_teachers(sid) if person_type == "Teacher" else hr_svc.active_staff(sid)
        att_date2 = st.date_input("Date", value=date.today(), key="staff_att_date")
        if people:
            with st.form("staff_attendance_form"):
                statuses = {}
                for p in people:
                    statuses[p["id"]] = st.radio(p["full_name"], ["Present", "Absent", "Leave"], horizontal=True, key=f"satt_{person_type}_{p['id']}")
                submitted = st.form_submit_button("Save", use_container_width=True)
                if submitted:
                    for pid, status in statuses.items():
                        academic_svc.mark_staff_attendance(sid, person_type, pid, att_date2, status)
                    alert("Attendance saved.", "success")
        else:
            st.info(f"No active {person_type.lower()} records found.")


# ==============================================================================
# FEES
# ==============================================================================

def page_fees(sid):
    page_header("💰 Fees Management", "Fee structure, collection, dues and reports")
    tabs = st.tabs(["🏗️ Fee Structure", "🧾 Collect Fee", "📉 Pending / Due List", "📈 Collection Reports"])
    c_opts = academic_svc.class_options(sid)

    with tabs[0]:
        with st.form("fee_structure_form", clear_on_submit=True):
            col1, col2, col3 = st.columns(3)
            class_label = col1.selectbox("Class - Section", list(c_opts.keys()) if c_opts else ["-"])
            fee_head = col2.text_input("Fee Head (e.g. Tuition)")
            amount = col3.number_input("Amount", min_value=0.0, step=100.0)
            session = st.text_input("Academic Session", value="2025-2026")
            submitted = st.form_submit_button("Add Fee Structure", use_container_width=True)
            if submitted:
                if not c_opts or not fee_head or amount <= 0:
                    alert("Please fill all fields correctly.", "error")
                else:
                    finance_svc.add_fee_structure(sid, c_opts[class_label], fee_head, amount, session)
                    alert("Fee structure added.", "success")
        st.dataframe(finance_svc.fee_structure_df(sid), use_container_width=True, hide_index=True)

    with tabs[1]:
        all_students = academic_svc.list_active_students(sid)
        options = {f"{s['full_name']} ({s['admission_no']})": s["id"] for s in all_students}
        if options:
            choice = st.selectbox("Select Student", list(options.keys()))
            stu_pk = options[choice]
            student = academic_svc.get_student(sid, stu_pk)
            due_total = finance_svc.class_due_total(sid, student["class_id"]) if student["class_id"] else 0
            paid_total = finance_svc.student_paid_total(sid, stu_pk)
            st.info(f"Total Due for Class: ₹{due_total:,.0f} · Already Paid: ₹{paid_total:,.0f} · Balance: ₹{max(due_total-paid_total,0):,.0f}")
            with st.form("fee_collect_form", clear_on_submit=True):
                col1, col2, col3 = st.columns(3)
                fee_head = col1.text_input("Fee Head", value="Tuition Fee")
                amount_paid = col2.number_input("Amount Paid *", min_value=0.0, step=100.0)
                payment_mode = col3.selectbox("Payment Mode", ["Cash", "Card", "UPI", "Bank Transfer", "Cheque"])
                col4, col5 = st.columns(2)
                discount = col4.number_input("Discount", min_value=0.0, step=50.0)
                fine = col5.number_input("Fine", min_value=0.0, step=50.0)
                remarks = st.text_input("Remarks")
                submitted = st.form_submit_button("Collect Fee & Generate Receipt", use_container_width=True)
                if submitted:
                    if amount_paid <= 0:
                        alert("Amount paid must be greater than 0.", "error")
                        st.session_state.pop("last_receipt", None)
                    else:
                        receipt_no = finance_svc.collect_fee(sid, stu_pk, amount_paid, discount, fine, payment_mode, fee_head, remarks)
                        audit_svc.log(sid, st.session_state.user["id"], "fee_entry", receipt_no)
                        school = school_svc.get_school(sid)
                        receipt_html = build_receipt_html(student, school, receipt_no, amount_paid, discount, fine, payment_mode, fee_head)
                        st.session_state["last_receipt"] = {"receipt_no": receipt_no, "html": receipt_html}
            last_receipt = st.session_state.get("last_receipt")
            if last_receipt:
                alert(f"Payment collected! Receipt No: {last_receipt['receipt_no']}", "success")
                st.download_button("⬇️ Download Receipt", last_receipt["html"], file_name=f"{last_receipt['receipt_no']}.html", mime="text/html", key=f"dl_{last_receipt['receipt_no']}")
        else:
            st.info("No active students found.")

    with tabs[2]:
        due_df = finance_svc.due_list_df(sid)
        st.dataframe(due_df, use_container_width=True, hide_index=True)
        if not due_df.empty:
            st.download_button("⬇️ Export Due List", to_excel_bytes(due_df, "Due List"), file_name="due_list.xlsx")

    with tabs[3]:
        col1, col2 = st.columns(2)
        report_date = col1.date_input("Daily Report Date", value=date.today())
        report_month = col2.text_input("Monthly Report (YYYY-MM)", value=date.today().strftime("%Y-%m"))
        daily_df = finance_svc.collection_report_df(sid, day=report_date)
        st.markdown("###### Daily Collection")
        st.dataframe(daily_df, use_container_width=True, hide_index=True)
        st.metric("Total Collected Today", f"₹{daily_df['Amount'].sum() if not daily_df.empty else 0:,.0f}")
        monthly_df = finance_svc.collection_report_df(sid, month=report_month)
        st.markdown("###### Monthly Collection")
        st.dataframe(monthly_df, use_container_width=True, hide_index=True)
        st.metric("Total Collected This Month", f"₹{monthly_df['Amount'].sum() if not monthly_df.empty else 0:,.0f}")


# ==============================================================================
# EXAMS
# ==============================================================================

def page_exams(sid):
    page_header("📝 Exam Management", "Exam types, subjects, marks entry and results")
    tabs = st.tabs(["🗂️ Exam Types", "📚 Subjects", "✍️ Marks Entry", "🏆 Result / Report Card"])
    c_opts = academic_svc.class_options(sid)

    with tabs[0]:
        with st.form("exam_type_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            exam_name = col1.text_input("Exam Name (e.g. Mid Term)")
            session = col2.text_input("Academic Session", value="2025-2026")
            submitted = st.form_submit_button("Add Exam Type", use_container_width=True)
            if submitted:
                if not exam_name:
                    alert("Exam name is required.", "error")
                else:
                    ok, msg = academic_svc.add_exam_type(sid, exam_name, session)
                    alert(msg, "success" if ok else "error")

    with tabs[1]:
        with st.form("subject_form", clear_on_submit=True):
            col1, col2, col3 = st.columns(3)
            class_label = col1.selectbox("Class - Section", list(c_opts.keys()) if c_opts else ["-"])
            subject_name = col2.text_input("Subject Name")
            max_marks = col3.number_input("Max Marks", min_value=1.0, value=100.0)
            submitted = st.form_submit_button("Add Subject", use_container_width=True)
            if submitted:
                if not c_opts or not subject_name:
                    alert("Please fill all fields.", "error")
                else:
                    ok, msg = academic_svc.add_exam_subject(sid, c_opts[class_label], subject_name, max_marks)
                    alert(msg, "success" if ok else "error")

    with tabs[2]:
        exams = academic_svc.list_exam_types(sid)
        if not exams or not c_opts:
            st.info("Create an exam type and class/subjects first.")
        else:
            e_opts = {e["exam_name"]: e["id"] for e in exams}
            col1, col2 = st.columns(2)
            exam_choice = col1.selectbox("Exam", list(e_opts.keys()))
            class_label = col2.selectbox("Class - Section", list(c_opts.keys()))
            subjects = academic_svc.list_exam_subjects(sid, c_opts[class_label])
            students = academic_svc.list_active_students(sid, c_opts[class_label])
            if subjects and students:
                sub_labels = [f"{s['subject_name']} (Max {s['max_marks']:.0f})" for s in subjects]
                subject = subjects[sub_labels.index(st.selectbox("Subject", sub_labels))]
                with st.form("marks_form"):
                    marks_input = {stu["id"]: st.number_input(stu["full_name"], min_value=0.0, max_value=float(subject["max_marks"]), key=f"mk_{stu['id']}") for stu in students}
                    submitted = st.form_submit_button("Save Marks", use_container_width=True)
                    if submitted:
                        academic_svc.save_marks(sid, e_opts[exam_choice], subject["id"], marks_input)
                        alert("Marks saved successfully.", "success")
            else:
                st.info("No subjects or students found for this class.")

    with tabs[3]:
        exams = academic_svc.list_exam_types(sid)
        all_students = academic_svc.list_active_students(sid)
        if exams and all_students:
            e_opts = {e["exam_name"]: e["id"] for e in exams}
            from database.connection import fetch_one as _fo
            s_lookup = {f"{s['full_name']} ({s['admission_no']})": s["id"] for s in all_students}
            col1, col2 = st.columns(2)
            exam_choice = col1.selectbox("Exam", list(e_opts.keys()), key="res_exam")
            student_choice = col2.selectbox("Student", list(s_lookup.keys()), key="res_stu")
            stu_pk = s_lookup[student_choice]
            student_rec = academic_svc.get_student(sid, stu_pk)
            result_df = academic_svc.get_result_df(sid, e_opts[exam_choice], stu_pk)
            if not result_df.empty:
                total_obtained = result_df["Obtained"].sum()
                total_max = result_df["Max"].sum()
                pct = round((total_obtained / total_max) * 100, 2) if total_max else 0
                grade = grade_for(pct)
                rank = academic_svc.get_class_rank(sid, e_opts[exam_choice], student_rec["class_id"], stu_pk)
                st.dataframe(result_df, use_container_width=True, hide_index=True)
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Total", f"{total_obtained:.0f}/{total_max:.0f}")
                m2.metric("Percentage", f"{pct}%")
                m3.metric("Grade", grade)
                m4.metric("Class Rank", rank)
                school = school_svc.get_school(sid)
                card_html = build_report_card_html(student_rec, school, exam_choice, result_df, total_obtained, total_max, pct, grade, rank)
                st.download_button("⬇️ Download Report Card", card_html, file_name=f"report_card_{student_rec['admission_no']}.html", mime="text/html")
            else:
                st.info("No marks recorded yet for this student/exam.")
        else:
            st.info("Add exams, subjects, students and marks first.")


# ==============================================================================
# TEACHERS / STAFF
# ==============================================================================

def page_teachers(sid):
    page_header("🧑‍🏫 Teacher Management", "Profiles, qualifications, salary and experience")
    tabs = st.tabs(["➕ Add Teacher", "📋 Teacher List"])
    with tabs[0]:
        with st.form("teacher_form", clear_on_submit=True):
            col1, col2, col3 = st.columns(3)
            full_name = col1.text_input("Full Name *")
            gender = col2.selectbox("Gender", ["Male", "Female", "Other"])
            phone = col3.text_input("Phone *")
            col4, col5 = st.columns(2)
            qualification = col4.text_input("Qualification")
            subject_spec = col5.text_input("Subject Specialization")
            col6, col7 = st.columns(2)
            experience = col6.number_input("Experience (years)", min_value=0.0, step=0.5)
            salary = col7.number_input("Salary", min_value=0.0, step=500.0)
            email = st.text_input("Email")
            submitted = st.form_submit_button("Add Teacher", use_container_width=True)
            if submitted:
                if not full_name or not phone:
                    alert("Name and Phone are required.", "error")
                else:
                    code = hr_svc.add_teacher(sid, full_name=full_name, gender=gender, qualification=qualification,
                                               subject_specialization=subject_spec, phone=phone, email=email,
                                               experience_years=experience, salary=salary)
                    alert(f"Teacher added successfully. Employee Code: {code}", "success")
    with tabs[1]:
        t_df = hr_svc.teachers_df(sid)
        st.dataframe(t_df, use_container_width=True, hide_index=True)
        if not t_df.empty:
            st.download_button("⬇️ Export Teacher List", to_excel_bytes(t_df, "Teachers"), file_name="teachers.xlsx")


def page_staff(sid):
    page_header("👷 Staff Management", "Office staff, peons, drivers, cleaners")
    tabs = st.tabs(["➕ Add Staff", "📋 Staff List"])
    with tabs[0]:
        with st.form("staff_form", clear_on_submit=True):
            col1, col2, col3 = st.columns(3)
            full_name = col1.text_input("Full Name *")
            designation = col2.selectbox("Designation", ["Office Staff", "Peon", "Driver", "Cleaner", "Security", "Other"])
            phone = col3.text_input("Phone *")
            salary = st.number_input("Salary", min_value=0.0, step=500.0)
            submitted = st.form_submit_button("Add Staff", use_container_width=True)
            if submitted:
                if not full_name or not phone:
                    alert("Name and Phone are required.", "error")
                else:
                    code = hr_svc.add_staff(sid, full_name=full_name, designation=designation, phone=phone, salary=salary)
                    alert(f"Staff added successfully. Employee Code: {code}", "success")
    with tabs[1]:
        s_df = hr_svc.staff_df(sid)
        st.dataframe(s_df, use_container_width=True, hide_index=True)
        if not s_df.empty:
            st.download_button("⬇️ Export Staff List", to_excel_bytes(s_df, "Staff"), file_name="staff.xlsx")


# ==============================================================================
# LIBRARY / TRANSPORT / HOSTEL
# ==============================================================================

def page_library(sid):
    page_header("📚 Library Management", "Books, categories, issue/return and fines")
    tabs = st.tabs(["📖 Books", "📤 Issue Book", "📥 Return Book"])
    with tabs[0]:
        with st.form("book_form", clear_on_submit=True):
            col1, col2, col3 = st.columns(3)
            title = col1.text_input("Book Title *")
            author = col2.text_input("Author")
            category = col3.text_input("Category")
            copies = st.number_input("Total Copies", min_value=1, value=1, step=1)
            submitted = st.form_submit_button("Add Book", use_container_width=True)
            if submitted:
                if not title:
                    alert("Book title is required.", "error")
                else:
                    code = facilities_svc.add_book(sid, title, author, category, copies)
                    alert(f"Book added successfully. Code: {code}", "success")
        st.dataframe(facilities_svc.books_df(sid), use_container_width=True, hide_index=True)

    with tabs[1]:
        books = facilities_svc.available_books(sid)
        students = academic_svc.list_active_students(sid)
        if books and students:
            b_opts = {f"{b['title']} ({b['available_copies']} available)": b["id"] for b in books}
            s_opts = {f"{s['full_name']} ({s['admission_no']})": s["id"] for s in students}
            with st.form("issue_form", clear_on_submit=True):
                book_choice = st.selectbox("Book", list(b_opts.keys()))
                student_choice = st.selectbox("Issue To (Student)", list(s_opts.keys()))
                due_date = st.date_input("Due Date", value=date.today() + timedelta(days=14))
                submitted = st.form_submit_button("Issue Book", use_container_width=True)
                if submitted:
                    facilities_svc.issue_book(sid, b_opts[book_choice], s_opts[student_choice], due_date)
                    alert("Book issued successfully.", "success")
        else:
            st.info("No available books or active students found.")

    with tabs[2]:
        issued = facilities_svc.issued_books(sid)
        if issued:
            i_opts = {f"{i['title']} → {i['full_name']} (Due {i['due_date']})": i for i in issued}
            choice = st.selectbox("Select Issued Book", list(i_opts.keys()))
            rec = i_opts[choice]
            if st.button("Confirm Return", use_container_width=True):
                fine, overdue_days = facilities_svc.return_book(sid, rec["id"], rec["book_id"])
                alert(f"Book returned. Overdue: {overdue_days} day(s), Fine: ₹{fine}", "success")
        else:
            st.info("No books currently issued.")


def page_transport(sid):
    page_header("🚌 Transport Management", "Vehicles, drivers and routes")
    tabs = st.tabs(["🚐 Vehicles", "🛣️ Routes"])
    with tabs[0]:
        with st.form("vehicle_form", clear_on_submit=True):
            col1, col2, col3 = st.columns(3)
            vehicle_no = col1.text_input("Vehicle Number *")
            driver_name = col2.text_input("Driver Name")
            driver_phone = col3.text_input("Driver Phone")
            capacity = st.number_input("Capacity", min_value=1, value=30)
            submitted = st.form_submit_button("Add Vehicle", use_container_width=True)
            if submitted:
                if not vehicle_no:
                    alert("Vehicle number is required.", "error")
                else:
                    try:
                        facilities_svc.add_vehicle(sid, vehicle_no, driver_name, driver_phone, capacity)
                        alert("Vehicle added.", "success")
                    except Exception as e:
                        alert("Vehicle number already exists." if "unique" in str(e).lower() else str(e), "error")
        st.dataframe(facilities_svc.vehicles_df(sid), use_container_width=True, hide_index=True)
    with tabs[1]:
        v_opts = facilities_svc.vehicle_options(sid)
        with st.form("route_form", clear_on_submit=True):
            col1, col2, col3 = st.columns(3)
            route_name = col1.text_input("Route Name *")
            vehicle_choice = col2.selectbox("Vehicle", ["None"] + list(v_opts.keys()))
            pickup_point = col3.text_input("Pickup Point")
            fare = st.number_input("Monthly Fare", min_value=0.0, step=50.0)
            submitted = st.form_submit_button("Add Route", use_container_width=True)
            if submitted:
                if not route_name:
                    alert("Route name is required.", "error")
                else:
                    facilities_svc.add_route(sid, route_name, v_opts.get(vehicle_choice), pickup_point, fare)
                    alert("Route added.", "success")
        st.dataframe(facilities_svc.routes_df(sid), use_container_width=True, hide_index=True)


def page_hostel(sid):
    page_header("🏠 Hostel Management", "Rooms, students and room allocation")
    tabs = st.tabs(["🛏️ Rooms", "🎓 Allocate Room", "📋 Allocation List"])
    with tabs[0]:
        with st.form("room_form", clear_on_submit=True):
            col1, col2, col3 = st.columns(3)
            room_no = col1.text_input("Room Number *")
            room_type = col2.selectbox("Room Type", ["Single", "Double", "Dormitory"])
            capacity = col3.number_input("Capacity", min_value=1, value=4)
            submitted = st.form_submit_button("Add Room", use_container_width=True)
            if submitted:
                if not room_no:
                    alert("Room number is required.", "error")
                else:
                    try:
                        facilities_svc.add_room(sid, room_no, room_type, capacity)
                        alert("Room added.", "success")
                    except Exception as e:
                        alert("Room number already exists." if "unique" in str(e).lower() else str(e), "error")
        st.dataframe(facilities_svc.rooms_df(sid), use_container_width=True, hide_index=True)
    with tabs[1]:
        rooms = facilities_svc.available_rooms(sid)
        students = facilities_svc.students_needing_hostel(sid)
        if rooms and students:
            r_opts = {f"{r['room_no']} ({r['occupied']}/{r['capacity']})": r["id"] for r in rooms}
            s_opts = {f"{s['full_name']} ({s['admission_no']})": s["id"] for s in students}
            with st.form("allocate_form", clear_on_submit=True):
                room_choice = st.selectbox("Room", list(r_opts.keys()))
                student_choice = st.selectbox("Student", list(s_opts.keys()))
                submitted = st.form_submit_button("Allocate Room", use_container_width=True)
                if submitted:
                    facilities_svc.allocate_room(sid, r_opts[room_choice], s_opts[student_choice])
                    alert("Room allocated successfully.", "success")
        else:
            st.info("No available rooms or students requiring hostel allocation.")
    with tabs[2]:
        st.dataframe(facilities_svc.allocations_df(sid), use_container_width=True, hide_index=True)


# ==============================================================================
# NOTICES / CERTIFICATES / REPORTS / SEARCH
# ==============================================================================

def page_notices(sid):
    page_header("🔔 Notice Board", "School notices, holidays and events")
    tabs = st.tabs(["➕ Post Notice", "📋 All Notices"])
    with tabs[0]:
        with st.form("notice_form", clear_on_submit=True):
            title = st.text_input("Title *")
            notice_type = st.selectbox("Type", ["Notice", "Holiday", "Event"])
            notice_date = st.date_input("Date", value=date.today())
            description = st.text_area("Description")
            submitted = st.form_submit_button("Post", use_container_width=True)
            if submitted:
                if not title:
                    alert("Title is required.", "error")
                else:
                    comm_svc.post_notice(sid, title, description, notice_type, notice_date, st.session_state.user["full_name"])
                    alert("Notice posted successfully.", "success")
    with tabs[1]:
        filter_type = st.selectbox("Filter by Type", ["All", "Notice", "Holiday", "Event"])
        for n in comm_svc.list_notices(sid, filter_type):
            icon = {"Notice": "📢", "Holiday": "🏖️", "Event": "🎉"}.get(n["notice_type"], "📌")
            st.markdown(f"""<div class="section-card"><b>{icon} {n['title']}</b>
                <span class="badge badge-orange">{n['notice_type']}</span>
                &nbsp; <span style="color:#888;">{n['notice_date']}</span>
                <p>{n['description'] or ''}</p></div>""", unsafe_allow_html=True)


def page_certificates(sid):
    page_header("📜 Certificates", "Bonafide, Transfer and Character Certificates")
    all_students = academic_svc.list_active_students(sid)
    options = {f"{s['full_name']} ({s['admission_no']})": s["id"] for s in all_students}
    if not options:
        st.info("No students found.")
        return
    choice = st.selectbox("Select Student", list(options.keys()))
    cert_type = st.selectbox("Certificate Type", ["Bonafide Certificate", "Transfer Certificate", "Character Certificate"])
    extra_note = st.text_input("Additional Note (optional)")
    if st.button("Generate Certificate", use_container_width=True):
        stu_pk = options[choice]
        rec = academic_svc.get_student(sid, stu_pk)
        school = school_svc.get_school(sid)
        comm_svc.log_certificate(sid, stu_pk, cert_type)
        cert_html = build_certificate_html(rec, school, cert_type, extra_note)
        alert("Certificate generated successfully.", "success")
        st.download_button("⬇️ Download Certificate", cert_html, file_name=f"{cert_type.replace(' ','_')}_{rec['admission_no']}.html", mime="text/html")
    st.divider()
    st.markdown("##### 📋 Issued Certificate Log")
    st.dataframe(comm_svc.certificate_log_df(sid), use_container_width=True, hide_index=True)


def page_reports(sid):
    page_header("📊 Reports", "Generate and export reports across all modules")
    report_choice = st.selectbox("Select Report", list(report_svc.REPORT_QUERIES.keys()) + ["Salary Report"])
    d = report_svc.get_report_df(sid, report_choice)
    st.dataframe(d, use_container_width=True, hide_index=True)
    if not d.empty:
        st.download_button("⬇️ Export to Excel", to_excel_bytes(d, report_choice[:28]), file_name=f"{report_choice.replace(' ','_').lower()}.xlsx")
    else:
        st.info("No data available for this report yet.")


def page_global_search(sid):
    page_header("🔍 Global Search", "Search across students, teachers and staff")
    q = st.text_input("Type a name, admission number, employee code or phone number")
    if not q:
        return
    st.markdown("##### 🎓 Students")
    st.dataframe(academic_svc.search_students_df(sid, q)[["full_name", "admission_no", "guardian_phone", "status"]], use_container_width=True, hide_index=True)
    st.markdown("##### 🧑‍🏫 Teachers")
    from database.connection import df as _df
    st.dataframe(_df("SELECT full_name AS \"Name\", employee_code AS \"Code\", phone AS \"Phone\", status AS \"Status\" "
                      "FROM teachers WHERE school_id=%(sid)s AND (full_name ILIKE %(q)s OR employee_code ILIKE %(q)s OR phone ILIKE %(q)s)",
                      {"sid": sid, "q": f"%{q}%"}), use_container_width=True, hide_index=True)
    st.markdown("##### 👷 Staff")
    st.dataframe(_df("SELECT full_name AS \"Name\", employee_code AS \"Code\", phone AS \"Phone\", status AS \"Status\" "
                      "FROM staff WHERE school_id=%(sid)s AND (full_name ILIKE %(q)s OR employee_code ILIKE %(q)s OR phone ILIKE %(q)s)",
                      {"sid": sid, "q": f"%{q}%"}), use_container_width=True, hide_index=True)


# ==============================================================================
# SETTINGS
# ==============================================================================

def page_settings(sid):
    page_header("⚙️ Settings", "School profile, user accounts and your own password")
    school = school_svc.get_school(sid)
    tabs = st.tabs(["🏫 School Profile", "👤 User Accounts", "🔑 My Account"])

    with tabs[0]:
        with st.form("settings_form"):
            school_name = st.text_input("School Name", value=school["school_name"])
            col1, col2 = st.columns(2)
            phone = col1.text_input("Phone", value=school["phone"] or "")
            email = col2.text_input("Email", value=school["email"] or "")
            address = st.text_area("Address", value=school["address"] or "")
            receipt_footer = st.text_input("Receipt Footer", value=school["receipt_footer"] or "")
            submitted = st.form_submit_button("Save Settings", use_container_width=True)
            if submitted:
                ok, msg = school_svc.update_school_settings(sid, school_name=school_name, phone=phone, email=email, address=address, receipt_footer=receipt_footer)
                alert(msg, "success" if ok else "error")
        st.info(f"🔑 Your School Code: **{school['school_code']}**")

    with tabs[1]:
        if st.session_state.user["role"] != "Super Admin":
            st.info("Only Super Admin can manage user accounts.")
        else:
            users = school_svc.list_school_users(sid)
            st.dataframe(pd.DataFrame(users)[["username", "full_name", "role", "active"]] if users else pd.DataFrame(), use_container_width=True, hide_index=True)
            non_self = [u for u in users if u["id"] != st.session_state.user["id"]]
            if non_self:
                u_opts = {f"{u['full_name']} ({u['username']}) · {'Active' if u['active'] else 'Inactive'}": u for u in non_self}
                choice = st.selectbox("Select User", list(u_opts.keys()))
                target = u_opts[choice]
                from auth.authentication import set_user_active
                if target["active"]:
                    if st.button("🚫 Deactivate User"):
                        ok, msg = set_user_active(sid, target["id"], False)
                        alert(msg, "success" if ok else "error")
                        st.rerun()
                else:
                    if st.button("✅ Activate User"):
                        ok, msg = set_user_active(sid, target["id"], True)
                        alert(msg, "success" if ok else "error")
                        st.rerun()

            st.markdown("---")
            st.markdown("##### ➕ Add Staff Account")
            if school["is_demo"]:
                st.info("Adding staff accounts is disabled in the Demo account.")
            else:
                with st.form("add_staff_form", clear_on_submit=True):
                    full_name = st.text_input("Full Name *")
                    col1, col2 = st.columns(2)
                    new_username = col1.text_input("Username *")
                    role = col2.selectbox("Role *", SIGNUP_ROLES)
                    email = st.text_input("Email")
                    col3, col4 = st.columns(2)
                    new_password = col3.text_input("Password *", type="password")
                    confirm_password = col4.text_input("Confirm Password *", type="password")
                    submitted = st.form_submit_button("Create Staff Account", use_container_width=True)
                    if submitted:
                        if new_password != confirm_password:
                            alert("Passwords do not match.", "error")
                        else:
                            ok, msg = signup_user(sid, new_username, new_password, full_name, role, email)
                            alert(msg, "success" if ok else "error")
                            if ok:
                                st.rerun()

    with tabs[2]:
        if school["is_demo"]:
            st.info("🔒 Password changes are disabled in the Demo account. Register your own school to manage your password.")
        else:
            st.caption(f"Logged in as {st.session_state.user['full_name']} ({st.session_state.user['username']})")
            with st.form("change_password_form", clear_on_submit=True):
                current_password = st.text_input("Current Password", type="password")
                col1, col2 = st.columns(2)
                new_password = col1.text_input("New Password", type="password")
                confirm_password = col2.text_input("Confirm New Password", type="password")
                submitted = st.form_submit_button("Update Password", use_container_width=True)
                if submitted:
                    ok, msg = change_password(st.session_state.user["id"], current_password, new_password, confirm_password)
                    alert(msg, "success" if ok else "error")


# ==============================================================================
# PLATFORM ADMIN (cross-school — Phase 6)
# ==============================================================================

def page_platform_dashboard():
    page_header("🌐 Platform Dashboard", "SaaS-wide overview across every school")
    summary = school_svc.platform_get_summary()
    cols = st.columns(4)
    kpi_card(cols[0], "Total Schools", summary["total_schools"], "grad-1")
    kpi_card(cols[1], "Active Subscriptions", summary["active_schools"], "grad-2")
    kpi_card(cols[2], "Expired", summary["expired_schools"], "grad-4")
    kpi_card(cols[3], "Pending Activation", summary["pending_schools"], "grad-7")


def page_platform_schools():
    page_header("🏫 Manage Schools", "Every registered school (demo school excluded)")
    schools = school_svc.platform_list_schools()
    real_schools = [s for s in schools if not s["is_demo"]]
    st.dataframe(pd.DataFrame(real_schools), use_container_width=True, hide_index=True)
    if real_schools:
        opts = {f"{s['school_name']} ({s['school_code']}) · {s['subscription_status']}": s for s in real_schools}
        choice = st.selectbox("Select School", list(opts.keys()))
        target = opts[choice]
        if target["subscription_status"] == "suspended":
            if st.button("✅ Reactivate School"):
                school_svc.platform_suspend_school(target["id"], False)
                st.rerun()
        else:
            if st.button("🚫 Suspend School"):
                school_svc.platform_suspend_school(target["id"], True)
                st.rerun()


def page_platform_license_keys():
    page_header("🔑 License Keys", "Platform-wide monthly & yearly subscription key pool")
    from database.connection import df as _df
    monthly = _df("SELECT license_key AS \"Key\", used AS \"Used\" FROM license_keys WHERE plan_type='monthly' ORDER BY used, license_key")
    yearly = _df("SELECT license_key AS \"Key\", used AS \"Used\" FROM license_keys WHERE plan_type='yearly' ORDER BY used, license_key")
    c1, c2 = st.columns(2)
    c1.metric("Monthly keys remaining", int((~monthly["Used"]).sum()) if not monthly.empty else 0)
    c2.metric("Yearly keys remaining", int((~yearly["Used"]).sum()) if not yearly.empty else 0)
    st.dataframe(monthly, use_container_width=True, hide_index=True)
    st.dataframe(yearly, use_container_width=True, hide_index=True)


# ==============================================================================
# NAVIGATION / MAIN
# ==============================================================================

SCHOOL_PAGES = {
    "Dashboard": page_dashboard, "Students": page_students, "Classes": page_classes,
    "Attendance": page_attendance, "Fees": page_fees, "Exams": page_exams,
    "Teachers": page_teachers, "Staff": page_staff, "Library": page_library,
    "Transport": page_transport, "Hostel": page_hostel, "Notice Board": page_notices,
    "Certificates": page_certificates, "Reports": page_reports,
    "Global Search": page_global_search, "Settings": page_settings,
}
PLATFORM_PAGES = {
    "Platform Dashboard": lambda sid: page_platform_dashboard(),
    "Manage Schools": lambda sid: page_platform_schools(),
    "Manage License Keys": lambda sid: page_platform_license_keys(),
}


def sidebar_menu():
    user = st.session_state.user
    with st.sidebar:
        st.markdown(f"### 🏫 {APP_NAME}")
        if not is_platform_role(user["role"]):
            school = school_svc.get_school(user["school_id"])
            st.caption(school["school_name"] if school else "")
        st.markdown(f"**{user['full_name']}**")
        st.caption(f"Role: {user['role']}")
        st.divider()

        pages = PLATFORM_PAGES if is_platform_role(user["role"]) else SCHOOL_PAGES
        names = [n for n in pages if has_access(user["role"], n)]
        if "current_module" not in st.session_state or st.session_state.current_module not in names:
            st.session_state.current_module = names[0] if names else None

        for name in names:
            is_selected = st.session_state.current_module == name
            icon = {"Dashboard": "📊", "Students": "🎓", "Classes": "🏷️", "Attendance": "📅", "Fees": "💰",
                    "Exams": "📝", "Teachers": "🧑‍🏫", "Staff": "👷", "Library": "📚", "Transport": "🚌",
                    "Hostel": "🏠", "Notice Board": "🔔", "Certificates": "📜", "Reports": "📊",
                    "Global Search": "🔍", "Settings": "⚙️", "Platform Dashboard": "🌐",
                    "Manage Schools": "🏫", "Manage License Keys": "🔑"}.get(name, "•")
            key = f"nav_{name.replace(' ', '-')}"
            if st.button(f"{icon}  {name}", key=key, use_container_width=True, type="primary" if is_selected else "secondary"):
                st.session_state.current_module = name
                st.rerun()

        st.divider()
        if not is_platform_role(user["role"]):
            status = school_svc.get_subscription_status(user["school_id"])
            if status["status"] == "active":
                plan_label = {"monthly": "Monthly", "yearly": "Yearly", "demo": "Demo"}.get(status["plan"], status["plan"])
                st.success(f"✅ {plan_label} plan · {status['days_left']} day(s) remaining" if status['days_left'] < 9999 else "✅ Demo school (unlimited)")

        if st.button("🚪 Logout", use_container_width=True, key="nav_logout"):
            audit_svc.log(user.get("school_id"), user["id"], "logout")
            del st.session_state.user
            st.rerun()

        return st.session_state.current_module


@st.cache_resource
def _run_once_per_process():
    """sync_license_keys()/ensure_demo_school() are idempotent but each does
    dozens of DB round-trips. They only ever need to run once per app
    process, not on every Streamlit rerun (every click/nav triggers a full
    script rerun) — st.cache_resource makes that guarantee."""
    school_svc.sync_license_keys()
    school_svc.ensure_demo_school()
    return True


def main():
    st.set_page_config(page_title=APP_NAME, page_icon="🏫", layout="wide", initial_sidebar_state="auto")

    ok, err = health_check()
    if not ok:
        inject_css()
        st.error("The database is temporarily unavailable. Please try again shortly.")
        with st.expander("Technical details (for the administrator)"):
            st.code(err or "unknown error")
        return

    _run_once_per_process()

    if "user" not in st.session_state:
        screen_login()
        return

    from database.connection import fetch_one
    fresh_user = fetch_one("SELECT * FROM users WHERE id = %s", (st.session_state.user["id"],))
    if not fresh_user or not fresh_user["active"]:
        inject_css()
        st.error("Your account is no longer active. Please contact your Super Admin.")
        if st.button("Logout"):
            del st.session_state.user
            st.rerun()
        return
    st.session_state.user = fresh_user

    if not is_platform_role(fresh_user["role"]):
        school = school_svc.get_school(fresh_user["school_id"])
        status = school_svc.get_subscription_status(fresh_user["school_id"])
        if status["status"] in ("pending", "expired", "suspended"):
            screen_subscription(status, school)
            return

    inject_css()
    module = sidebar_menu()
    if module:
        pages = PLATFORM_PAGES if is_platform_role(fresh_user["role"]) else SCHOOL_PAGES
        pages[module](fresh_user.get("school_id"))


if __name__ == "__main__":
    main()
