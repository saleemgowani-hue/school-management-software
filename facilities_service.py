"""services/facilities_service.py — Library, Transport, Hostel. All queries
school_id-scoped."""

from datetime import date, timedelta

from database.connection import fetch_one, fetch_all, execute, df

# ---------------------------------------------------------------------------
# Library
# ---------------------------------------------------------------------------

def next_book_code(school_id):
    row = fetch_one("SELECT COUNT(*) c FROM library_books WHERE school_id=%s", (school_id,))
    return f"BK{row['c'] + 1:04d}"


def add_book(school_id, title, author, category, copies):
    code = next_book_code(school_id)
    execute("""
        INSERT INTO library_books (school_id, book_code, title, author, category, total_copies, available_copies)
        VALUES (%s,%s,%s,%s,%s,%s,%s)
    """, (school_id, code, title, author, category, copies, copies))
    return code


def books_df(school_id):
    return df("""
        SELECT book_code AS "Code", title AS "Title", author AS "Author", category AS "Category",
               total_copies AS "Total", available_copies AS "Available"
        FROM library_books WHERE school_id=%(sid)s
    """, {"sid": school_id})


def available_books(school_id):
    return fetch_all(
        "SELECT id, title, available_copies FROM library_books WHERE school_id=%s AND available_copies > 0",
        (school_id,),
    )


def issue_book(school_id, book_id, student_id, due_date):
    execute("INSERT INTO book_issues (school_id, book_id, student_id, due_date) VALUES (%s,%s,%s,%s)",
            (school_id, book_id, student_id, due_date))
    execute("UPDATE library_books SET available_copies = available_copies - 1 WHERE id=%s AND school_id=%s",
            (book_id, school_id))


def issued_books(school_id):
    return fetch_all("""
        SELECT bi.id, lb.title, s.full_name, bi.due_date, bi.book_id
        FROM book_issues bi JOIN library_books lb ON lb.id = bi.book_id AND lb.school_id = bi.school_id
        LEFT JOIN students s ON s.id = bi.student_id AND s.school_id = bi.school_id
        WHERE bi.school_id = %s AND bi.status = 'Issued'
    """, (school_id,))


def return_book(school_id, issue_id, book_id):
    rec = fetch_one("SELECT due_date FROM book_issues WHERE id=%s AND school_id=%s", (issue_id, school_id))
    overdue_days = max((date.today() - rec["due_date"]).days, 0)
    fine = overdue_days * 5
    execute("UPDATE book_issues SET status='Returned', return_date=%s, fine=%s WHERE id=%s AND school_id=%s",
            (date.today(), fine, issue_id, school_id))
    execute("UPDATE library_books SET available_copies = available_copies + 1 WHERE id=%s AND school_id=%s",
            (book_id, school_id))
    return fine, overdue_days


# ---------------------------------------------------------------------------
# Transport
# ---------------------------------------------------------------------------

def add_vehicle(school_id, vehicle_no, driver_name, driver_phone, capacity):
    execute("INSERT INTO transport_vehicles (school_id, vehicle_no, driver_name, driver_phone, capacity) VALUES (%s,%s,%s,%s,%s)",
            (school_id, vehicle_no, driver_name, driver_phone, capacity))


def vehicles_df(school_id):
    return df('SELECT vehicle_no AS "Vehicle No", driver_name AS "Driver", driver_phone AS "Phone", capacity AS "Capacity" '
               'FROM transport_vehicles WHERE school_id=%(sid)s', {"sid": school_id})


def vehicle_options(school_id):
    rows = fetch_all("SELECT id, vehicle_no FROM transport_vehicles WHERE school_id=%s", (school_id,))
    return {r["vehicle_no"]: r["id"] for r in rows}


def add_route(school_id, route_name, vehicle_id, pickup_point, fare):
    execute("INSERT INTO transport_routes (school_id, route_name, vehicle_id, pickup_point, fare) VALUES (%s,%s,%s,%s,%s)",
            (school_id, route_name, vehicle_id, pickup_point, fare))


def routes_df(school_id):
    return df("""
        SELECT r.route_name AS "Route", COALESCE(v.vehicle_no,'-') AS "Vehicle",
               r.pickup_point AS "Pickup Point", r.fare AS "Fare"
        FROM transport_routes r LEFT JOIN transport_vehicles v ON v.id=r.vehicle_id AND v.school_id = r.school_id
        WHERE r.school_id = %(sid)s
    """, {"sid": school_id})


def route_options(school_id):
    rows = fetch_all("SELECT id, route_name FROM transport_routes WHERE school_id=%s", (school_id,))
    return {r["route_name"]: r["id"] for r in rows}


# ---------------------------------------------------------------------------
# Hostel
# ---------------------------------------------------------------------------

def add_room(school_id, room_no, room_type, capacity):
    execute("INSERT INTO hostel_rooms (school_id, room_no, room_type, capacity) VALUES (%s,%s,%s,%s)",
            (school_id, room_no, room_type, capacity))


def rooms_df(school_id):
    return df('SELECT room_no AS "Room", room_type AS "Type", capacity AS "Capacity", occupied AS "Occupied" '
               'FROM hostel_rooms WHERE school_id=%(sid)s', {"sid": school_id})


def available_rooms(school_id):
    return fetch_all("SELECT id, room_no, capacity, occupied FROM hostel_rooms WHERE school_id=%s AND occupied < capacity", (school_id,))


def students_needing_hostel(school_id):
    return fetch_all("""
        SELECT id, full_name, admission_no FROM students
        WHERE school_id=%s AND status='Active' AND hostel_required=TRUE
        AND id NOT IN (SELECT student_id FROM hostel_allocations WHERE school_id=%s AND status='Active')
    """, (school_id, school_id))


def allocate_room(school_id, room_id, student_id):
    execute("INSERT INTO hostel_allocations (school_id, room_id, student_id) VALUES (%s,%s,%s)",
            (school_id, room_id, student_id))
    execute("UPDATE hostel_rooms SET occupied = occupied + 1 WHERE id=%s AND school_id=%s", (room_id, school_id))


def allocations_df(school_id):
    return df("""
        SELECT s.full_name AS "Student", hr.room_no AS "Room", hr.room_type AS "Type",
               ha.allocation_date AS "Allocated On"
        FROM hostel_allocations ha
        JOIN hostel_rooms hr ON hr.id = ha.room_id AND hr.school_id = ha.school_id
        JOIN students s ON s.id = ha.student_id AND s.school_id = ha.school_id
        WHERE ha.school_id = %(sid)s AND ha.status='Active'
    """, {"sid": school_id})
