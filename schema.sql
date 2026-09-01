-- ============================================================================
-- EduManage Pro SaaS — PostgreSQL Schema
-- Multi-tenant: every school-owned table carries school_id and is indexed on it.
-- Safe to re-run: every statement is CREATE ... IF NOT EXISTS.
-- ============================================================================

-- ---------------------------------------------------------------------------
-- PLATFORM-LEVEL TABLES (no school_id — these ARE the tenant registry)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS schools (
    id                      SERIAL PRIMARY KEY,
    school_code             TEXT UNIQUE NOT NULL,
    school_name             TEXT NOT NULL,
    address                 TEXT,
    phone                   TEXT,
    email                   TEXT,
    principal_name          TEXT,
    logo_blob               TEXT,
    receipt_footer          TEXT DEFAULT 'Thank you!',
    academic_session        TEXT DEFAULT '2025-2026',
    theme                   TEXT DEFAULT 'Light',
    is_demo                 BOOLEAN NOT NULL DEFAULT FALSE,
    subscription_plan       TEXT,                         -- 'monthly' | 'yearly' | NULL
    subscription_status     TEXT NOT NULL DEFAULT 'pending', -- pending|active|expired|suspended
    subscription_start      DATE,
    subscription_expiry     DATE,
    license_key_used        TEXT,
    created_at              TIMESTAMP NOT NULL DEFAULT now(),
    updated_at              TIMESTAMP NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS license_keys (
    id                  SERIAL PRIMARY KEY,
    license_key         TEXT UNIQUE NOT NULL,
    plan_type           TEXT NOT NULL DEFAULT 'yearly',   -- 'monthly' | 'yearly'
    used                BOOLEAN NOT NULL DEFAULT FALSE,
    used_by_school_id   INTEGER REFERENCES schools(id),
    used_at             TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_license_keys_plan ON license_keys(plan_type, used);

-- ---------------------------------------------------------------------------
-- USERS (school_id NULL only for Platform Admin)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS users (
    id              SERIAL PRIMARY KEY,
    school_id       INTEGER REFERENCES schools(id),
    username        TEXT UNIQUE NOT NULL,
    password_hash   TEXT NOT NULL,
    full_name       TEXT NOT NULL,
    role            TEXT NOT NULL,
    email           TEXT,
    phone           TEXT,
    active          BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMP NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_users_school ON users(school_id);

CREATE TABLE IF NOT EXISTS audit_log (
    id          SERIAL PRIMARY KEY,
    school_id   INTEGER REFERENCES schools(id),
    user_id     INTEGER REFERENCES users(id),
    action      TEXT NOT NULL,
    details     TEXT,
    created_at  TIMESTAMP NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_audit_school ON audit_log(school_id, created_at);

-- ---------------------------------------------------------------------------
-- ACADEMIC
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS classes (
    id                  SERIAL PRIMARY KEY,
    school_id           INTEGER NOT NULL REFERENCES schools(id),
    class_name          TEXT NOT NULL,
    section             TEXT NOT NULL,
    academic_session    TEXT NOT NULL,
    class_teacher_id    INTEGER,
    UNIQUE(school_id, class_name, section, academic_session)
);
CREATE INDEX IF NOT EXISTS idx_classes_school ON classes(school_id);

CREATE TABLE IF NOT EXISTS students (
    id                  SERIAL PRIMARY KEY,
    school_id           INTEGER NOT NULL REFERENCES schools(id),
    admission_no        TEXT NOT NULL,
    student_id          TEXT NOT NULL,
    full_name           TEXT NOT NULL,
    dob                 DATE,
    gender              TEXT,
    blood_group         TEXT,
    category            TEXT,
    class_id            INTEGER REFERENCES classes(id),
    roll_no             TEXT,
    father_name         TEXT,
    mother_name         TEXT,
    guardian_phone      TEXT,
    guardian_email      TEXT,
    address             TEXT,
    emergency_contact   TEXT,
    transport_required  BOOLEAN DEFAULT FALSE,
    route_id            INTEGER,
    hostel_required     BOOLEAN DEFAULT FALSE,
    photo_blob          TEXT,
    documents_note      TEXT,
    status              TEXT DEFAULT 'Active',
    admission_date      DATE DEFAULT CURRENT_DATE,
    UNIQUE(school_id, admission_no),
    UNIQUE(school_id, student_id)
);
CREATE INDEX IF NOT EXISTS idx_students_school ON students(school_id);
CREATE INDEX IF NOT EXISTS idx_students_class ON students(school_id, class_id);
CREATE INDEX IF NOT EXISTS idx_students_admission ON students(school_id, admission_no);

CREATE TABLE IF NOT EXISTS student_attendance (
    id          SERIAL PRIMARY KEY,
    school_id   INTEGER NOT NULL REFERENCES schools(id),
    student_id  INTEGER NOT NULL REFERENCES students(id),
    att_date    DATE NOT NULL,
    status      TEXT NOT NULL,
    UNIQUE(school_id, student_id, att_date)
);
CREATE INDEX IF NOT EXISTS idx_student_att_school_date ON student_attendance(school_id, att_date);

CREATE TABLE IF NOT EXISTS exam_types (
    id                  SERIAL PRIMARY KEY,
    school_id           INTEGER NOT NULL REFERENCES schools(id),
    exam_name           TEXT NOT NULL,
    academic_session    TEXT NOT NULL,
    UNIQUE(school_id, exam_name)
);
CREATE INDEX IF NOT EXISTS idx_exam_types_school ON exam_types(school_id);

CREATE TABLE IF NOT EXISTS exam_subjects (
    id          SERIAL PRIMARY KEY,
    school_id   INTEGER NOT NULL REFERENCES schools(id),
    class_id    INTEGER NOT NULL REFERENCES classes(id),
    subject_name TEXT NOT NULL,
    max_marks   NUMERIC DEFAULT 100,
    UNIQUE(school_id, class_id, subject_name)
);
CREATE INDEX IF NOT EXISTS idx_exam_subjects_school ON exam_subjects(school_id);

CREATE TABLE IF NOT EXISTS marks (
    id              SERIAL PRIMARY KEY,
    school_id       INTEGER NOT NULL REFERENCES schools(id),
    exam_id         INTEGER NOT NULL REFERENCES exam_types(id),
    student_id      INTEGER NOT NULL REFERENCES students(id),
    subject_id      INTEGER NOT NULL REFERENCES exam_subjects(id),
    marks_obtained  NUMERIC NOT NULL,
    UNIQUE(school_id, exam_id, student_id, subject_id)
);
CREATE INDEX IF NOT EXISTS idx_marks_school ON marks(school_id);

-- ---------------------------------------------------------------------------
-- HR (Teachers / Staff)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS teachers (
    id                      SERIAL PRIMARY KEY,
    school_id               INTEGER NOT NULL REFERENCES schools(id),
    employee_code           TEXT NOT NULL,
    full_name               TEXT NOT NULL,
    gender                  TEXT,
    qualification           TEXT,
    subject_specialization  TEXT,
    phone                   TEXT,
    email                   TEXT,
    address                 TEXT,
    joining_date            DATE DEFAULT CURRENT_DATE,
    experience_years        NUMERIC DEFAULT 0,
    salary                  NUMERIC DEFAULT 0,
    status                  TEXT DEFAULT 'Active',
    UNIQUE(school_id, employee_code)
);
CREATE INDEX IF NOT EXISTS idx_teachers_school ON teachers(school_id);

CREATE TABLE IF NOT EXISTS staff (
    id              SERIAL PRIMARY KEY,
    school_id       INTEGER NOT NULL REFERENCES schools(id),
    employee_code   TEXT NOT NULL,
    full_name       TEXT NOT NULL,
    designation     TEXT,
    phone           TEXT,
    address         TEXT,
    joining_date    DATE DEFAULT CURRENT_DATE,
    salary          NUMERIC DEFAULT 0,
    status          TEXT DEFAULT 'Active',
    UNIQUE(school_id, employee_code)
);
CREATE INDEX IF NOT EXISTS idx_staff_school ON staff(school_id);

CREATE TABLE IF NOT EXISTS staff_attendance (
    id          SERIAL PRIMARY KEY,
    school_id   INTEGER NOT NULL REFERENCES schools(id),
    person_type TEXT NOT NULL,      -- 'Teacher' | 'Staff'
    person_id   INTEGER NOT NULL,
    att_date    DATE NOT NULL,
    status      TEXT NOT NULL,
    UNIQUE(school_id, person_type, person_id, att_date)
);
CREATE INDEX IF NOT EXISTS idx_staff_att_school_date ON staff_attendance(school_id, att_date);

-- ---------------------------------------------------------------------------
-- FINANCE
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS fee_structure (
    id                  SERIAL PRIMARY KEY,
    school_id           INTEGER NOT NULL REFERENCES schools(id),
    class_id            INTEGER NOT NULL REFERENCES classes(id),
    fee_head            TEXT NOT NULL,
    amount              NUMERIC NOT NULL,
    academic_session    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_fee_structure_school ON fee_structure(school_id);

CREATE TABLE IF NOT EXISTS fee_payments (
    id              SERIAL PRIMARY KEY,
    school_id       INTEGER NOT NULL REFERENCES schools(id),
    receipt_no      TEXT NOT NULL,
    student_id      INTEGER NOT NULL REFERENCES students(id),
    amount_paid     NUMERIC NOT NULL,
    discount        NUMERIC DEFAULT 0,
    fine            NUMERIC DEFAULT 0,
    payment_mode    TEXT,
    fee_head        TEXT,
    remarks         TEXT,
    payment_date    DATE DEFAULT CURRENT_DATE,
    UNIQUE(school_id, receipt_no)
);
CREATE INDEX IF NOT EXISTS idx_fee_payments_school_date ON fee_payments(school_id, payment_date);
CREATE INDEX IF NOT EXISTS idx_fee_payments_student ON fee_payments(school_id, student_id);

-- ---------------------------------------------------------------------------
-- FACILITIES (Library / Transport / Hostel)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS library_books (
    id                  SERIAL PRIMARY KEY,
    school_id           INTEGER NOT NULL REFERENCES schools(id),
    book_code           TEXT NOT NULL,
    title               TEXT NOT NULL,
    author              TEXT,
    category            TEXT,
    total_copies        INTEGER DEFAULT 1,
    available_copies    INTEGER DEFAULT 1,
    UNIQUE(school_id, book_code)
);
CREATE INDEX IF NOT EXISTS idx_library_books_school ON library_books(school_id);

CREATE TABLE IF NOT EXISTS book_issues (
    id              SERIAL PRIMARY KEY,
    school_id       INTEGER NOT NULL REFERENCES schools(id),
    book_id         INTEGER NOT NULL REFERENCES library_books(id),
    student_id      INTEGER REFERENCES students(id),
    issued_to_name  TEXT,
    issue_date      DATE DEFAULT CURRENT_DATE,
    due_date        DATE,
    return_date     DATE,
    fine            NUMERIC DEFAULT 0,
    status          TEXT DEFAULT 'Issued'
);
CREATE INDEX IF NOT EXISTS idx_book_issues_school ON book_issues(school_id);

CREATE TABLE IF NOT EXISTS transport_vehicles (
    id              SERIAL PRIMARY KEY,
    school_id       INTEGER NOT NULL REFERENCES schools(id),
    vehicle_no      TEXT NOT NULL,
    driver_name     TEXT,
    driver_phone    TEXT,
    capacity        INTEGER,
    UNIQUE(school_id, vehicle_no)
);
CREATE INDEX IF NOT EXISTS idx_transport_vehicles_school ON transport_vehicles(school_id);

CREATE TABLE IF NOT EXISTS transport_routes (
    id              SERIAL PRIMARY KEY,
    school_id       INTEGER NOT NULL REFERENCES schools(id),
    route_name      TEXT NOT NULL,
    vehicle_id      INTEGER REFERENCES transport_vehicles(id),
    pickup_point    TEXT,
    fare            NUMERIC DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_transport_routes_school ON transport_routes(school_id);

CREATE TABLE IF NOT EXISTS hostel_rooms (
    id          SERIAL PRIMARY KEY,
    school_id   INTEGER NOT NULL REFERENCES schools(id),
    room_no     TEXT NOT NULL,
    room_type   TEXT,
    capacity    INTEGER DEFAULT 1,
    occupied    INTEGER DEFAULT 0,
    UNIQUE(school_id, room_no)
);
CREATE INDEX IF NOT EXISTS idx_hostel_rooms_school ON hostel_rooms(school_id);

CREATE TABLE IF NOT EXISTS hostel_allocations (
    id                  SERIAL PRIMARY KEY,
    school_id           INTEGER NOT NULL REFERENCES schools(id),
    room_id             INTEGER NOT NULL REFERENCES hostel_rooms(id),
    student_id          INTEGER NOT NULL REFERENCES students(id),
    allocation_date     DATE DEFAULT CURRENT_DATE,
    status              TEXT DEFAULT 'Active'
);
CREATE INDEX IF NOT EXISTS idx_hostel_alloc_school ON hostel_allocations(school_id);

-- ---------------------------------------------------------------------------
-- COMMUNICATION
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS notices (
    id              SERIAL PRIMARY KEY,
    school_id       INTEGER NOT NULL REFERENCES schools(id),
    title           TEXT NOT NULL,
    description     TEXT,
    notice_type     TEXT DEFAULT 'Notice',
    notice_date     DATE DEFAULT CURRENT_DATE,
    posted_by       TEXT
);
CREATE INDEX IF NOT EXISTS idx_notices_school_date ON notices(school_id, notice_date);

CREATE TABLE IF NOT EXISTS certificates_log (
    id          SERIAL PRIMARY KEY,
    school_id   INTEGER NOT NULL REFERENCES schools(id),
    student_id  INTEGER NOT NULL REFERENCES students(id),
    cert_type   TEXT NOT NULL,
    issue_date  DATE DEFAULT CURRENT_DATE
);
CREATE INDEX IF NOT EXISTS idx_certificates_school ON certificates_log(school_id);
