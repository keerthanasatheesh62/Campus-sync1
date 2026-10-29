import os
import io
import csv
import json
import math
import sqlite3
from datetime import datetime, date, timedelta
from flask import Flask, render_template, request, jsonify, send_file, make_response
import database

# Initialize Flask app
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, 'templates'),
    static_folder=os.path.join(BASE_DIR, 'static')
)
app.config['SECRET_KEY'] = 'CampusSyncSecretKey2026'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB max upload limit

# Upload folder
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Initialize DB
database.init_db()

# --- Helper Utilities ---
def dict_from_row(row):
    return dict(row) if row else None

def get_current_user_role():
    # Passed in header or query or defaults to current role
    role = request.headers.get('X-User-Role')
    if role not in ['Administrator', 'Campus Supervisor']:
        role = request.args.get('role', 'Administrator')
    return role if role in ['Administrator', 'Campus Supervisor'] else 'Administrator'

# --- Main Route ---
@app.route('/')
def index():
    return render_template('index.html')

# --- Campus Endpoints ---
@app.route('/api/campuses', methods=['GET'])
def get_campuses():
    conn = database.get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT c.*, 
               COUNT(s.id) as student_count,
               COALESCE(SUM(s.total_fee), 0) as total_assessed,
               COALESCE(SUM(s.concession), 0) as total_concession
        FROM campuses c
        LEFT JOIN students s ON s.campus_id = c.id AND s.status != 'Archived'
        GROUP BY c.id
        ORDER BY c.id ASC
    """)
    campuses = [dict_from_row(r) for r in cursor.fetchall()]
    conn.close()
    return jsonify({"success": True, "campuses": campuses})

# --- Dashboard Statistics ---
@app.route('/api/dashboard/stats', methods=['GET'])
def get_dashboard_stats():
    campus_id = request.args.get('campus_id', '')
    filter_campus = campus_id.isdigit()
    cid = int(campus_id) if filter_campus else None

    conn = database.get_db()
    cursor = conn.cursor()

    # Threshold setting
    cursor.execute("SELECT value FROM app_settings WHERE key = 'attendance_threshold'")
    t_row = cursor.fetchone()
    threshold = float(t_row['value']) if t_row else 75.0

    # Total students
    query = "SELECT COUNT(*) as count FROM students WHERE status != 'Archived'"
    params = []
    if filter_campus:
        query += " AND campus_id = ?"
        params.append(cid)
    cursor.execute(query, params)
    total_students = cursor.fetchone()['count']

    # Fee metrics
    fee_query = """
        SELECT 
            COALESCE(SUM(total_fee), 0) as total_assessed,
            COALESCE(SUM(concession), 0) as total_concession
        FROM students 
        WHERE status != 'Archived'
    """
    fee_params = []
    if filter_campus:
        fee_query += " AND campus_id = ?"
        fee_params.append(cid)
    cursor.execute(fee_query, fee_params)
    fee_summary = cursor.fetchone()
    total_assessed = float(fee_summary['total_assessed'])
    total_concession = float(fee_summary['total_concession'])

    # Total fees collected
    coll_query = "SELECT COALESCE(SUM(amount), 0) as collected FROM fee_payments WHERE 1=1"
    coll_params = []
    if filter_campus:
        coll_query += " AND campus_id = ?"
        coll_params.append(cid)
    cursor.execute(coll_query, coll_params)
    total_collected = float(cursor.fetchone()['collected'])

    total_outstanding = max(0.0, total_assessed - total_concession - total_collected)

    # Attendance metrics
    att_query = """
        SELECT 
            COUNT(*) as total_records,
            SUM(CASE WHEN ar.status = 'Present' THEN 1 ELSE 0 END) as present_records
        FROM attendance_records ar
        JOIN students s ON s.student_id = ar.student_id
        WHERE s.status != 'Archived'
    """
    att_params = []
    if filter_campus:
        att_query += " AND ar.campus_id = ?"
        att_params.append(cid)
    cursor.execute(att_query, att_params)
    att_summary = cursor.fetchone()
    total_att_records = att_summary['total_records']
    present_att_records = att_summary['present_records'] or 0
    avg_attendance = round((present_att_records / total_att_records * 100), 1) if total_att_records > 0 else 100.0

    # Low attendance count (< threshold)
    low_att_query = """
        SELECT s.student_id,
               COUNT(ar.id) as total_days,
               SUM(CASE WHEN ar.status = 'Present' THEN 1 ELSE 0 END) as present_days
        FROM students s
        LEFT JOIN attendance_records ar ON ar.student_id = s.student_id
        WHERE s.status != 'Archived'
    """
    low_att_params = []
    if filter_campus:
        low_att_query += " AND s.campus_id = ?"
        low_att_params.append(cid)
    low_att_query += " GROUP BY s.student_id"

    cursor.execute(low_att_query, low_att_params)
    student_att_rows = cursor.fetchall()

    low_att_count = 0
    attention_list = []

    for r in student_att_rows:
        tdays = r['total_days']
        pdays = r['present_days'] or 0
        pct = round((pdays / tdays * 100), 1) if tdays > 0 else 100.0
        if pct < threshold:
            low_att_count += 1

    # Detailed Students Requiring Attention (low attendance or high pending fee)
    att_alert_query = """
        SELECT s.student_id, s.full_name, s.course, c.name as campus_name, s.total_fee, s.concession,
               COALESCE((SELECT SUM(amount) FROM fee_payments fp WHERE fp.student_id = s.student_id), 0) as paid,
               COUNT(ar.id) as total_days,
               SUM(CASE WHEN ar.status = 'Present' THEN 1 ELSE 0 END) as present_days
        FROM students s
        JOIN campuses c ON c.id = s.campus_id
        LEFT JOIN attendance_records ar ON ar.student_id = s.student_id
        WHERE s.status != 'Archived'
    """
    att_alert_params = []
    if filter_campus:
        att_alert_query += " AND s.campus_id = ?"
        att_alert_params.append(cid)
    att_alert_query += " GROUP BY s.student_id ORDER BY s.id ASC"

    cursor.execute(att_alert_query, att_alert_params)
    all_students_meta = cursor.fetchall()

    for sm in all_students_meta:
        tdays = sm['total_days']
        pdays = sm['present_days'] or 0
        pct = round((pdays / tdays * 100), 1) if tdays > 0 else 100.0
        pending = max(0.0, sm['total_fee'] - sm['concession'] - sm['paid'])
        
        reasons = []
        if pct < threshold:
            reasons.append(f"Low Attendance ({pct}%)")
        if pending > 40000:
            reasons.append(f"High Pending Balance (₹{pending:,.0f})")

        if reasons:
            attention_list.append({
                "student_id": sm['student_id'],
                "name": sm['full_name'],
                "course": sm['course'],
                "campus_name": sm['campus_name'],
                "attendance_pct": pct,
                "pending_fee": pending,
                "reason": " & ".join(reasons)
            })

    # Hostel stats
    hostel_query = """
        SELECT 
            COALESCE(SUM(capacity), 0) as total_cap,
            COALESCE(SUM(occupied_beds), 0) as total_occ
        FROM hostel_rooms hr
        WHERE 1=1
    """
    hostel_params = []
    if filter_campus:
        hostel_query += " AND hr.campus_id = ?"
        hostel_params.append(cid)
    cursor.execute(hostel_query, hostel_params)
    h_row = cursor.fetchone()
    hostel_capacity = h_row['total_cap']
    hostel_occupied = h_row['total_occ']
    hostel_pct = round((hostel_occupied / hostel_capacity * 100), 1) if hostel_capacity > 0 else 0.0

    # Campus Breakdown data for charts
    cursor.execute("""
        SELECT 
            c.id, c.name, c.code,
            COUNT(s.id) as student_count,
            COALESCE(SUM(s.total_fee), 0) as assessed,
            COALESCE(SUM(s.concession), 0) as concession,
            COALESCE((
                SELECT SUM(fp.amount) 
                FROM fee_payments fp 
                WHERE fp.campus_id = c.id
            ), 0) as collected,
            COALESCE((
                SELECT SUM(hr.capacity)
                FROM hostel_rooms hr
                WHERE hr.campus_id = c.id
            ), 0) as hostel_capacity,
            COALESCE((
                SELECT SUM(hr.occupied_beds)
                FROM hostel_rooms hr
                WHERE hr.campus_id = c.id
            ), 0) as hostel_occupied
        FROM campuses c
        LEFT JOIN students s ON s.campus_id = c.id AND s.status != 'Archived'
        GROUP BY c.id
        ORDER BY c.id ASC
    """)
    campus_breakdown = []
    for cb in cursor.fetchall():
        c_assessed = float(cb['assessed'])
        c_concession = float(cb['concession'])
        c_collected = float(cb['collected'])
        c_pending = max(0.0, c_assessed - c_concession - c_collected)
        campus_breakdown.append({
            "id": cb['id'],
            "name": cb['name'],
            "code": cb['code'],
            "students": cb['student_count'],
            "assessed": c_assessed,
            "concession": c_concession,
            "collected": c_collected,
            "pending": c_pending,
            "hostel_capacity": cb['hostel_capacity'],
            "hostel_occupied": cb['hostel_occupied']
        })

    # Recent Audit Activities
    act_query = "SELECT * FROM audit_logs WHERE 1=1"
    act_params = []
    if filter_campus:
        cursor.execute("SELECT name FROM campuses WHERE id = ?", (cid,))
        c_name_row = cursor.fetchone()
        if c_name_row:
            act_query += " AND (campus_name = ? OR campus_name = 'All Campuses')"
            act_params.append(c_name_row['name'])
    act_query += " ORDER BY id DESC LIMIT 8"
    cursor.execute(act_query, act_params)
    recent_activities = [dict_from_row(r) for r in cursor.fetchall()]

    conn.close()

    return jsonify({
        "success": True,
        "metrics": {
            "total_students": total_students,
            "total_assessed": total_assessed,
            "total_concession": total_concession,
            "total_collected": total_collected,
            "total_outstanding": total_outstanding,
            "avg_attendance": avg_attendance,
            "low_attendance_count": low_att_count,
            "attendance_threshold": threshold,
            "hostel_capacity": hostel_capacity,
            "hostel_occupied": hostel_occupied,
            "hostel_occupancy_pct": hostel_pct
        },
        "campus_breakdown": campus_breakdown,
        "attention_list": attention_list[:6],
        "recent_activities": recent_activities
    })

# --- Student Management ---
@app.route('/api/students', methods=['GET'])
def get_students():
    campus_id = request.args.get('campus_id', '')
    search = request.args.get('search', '').strip()
    status = request.args.get('status', '').strip()
    course = request.args.get('course', '').strip()
    fee_status = request.args.get('fee_status', '').strip()
    try:
        page = max(1, int(request.args.get('page', 1)))
        per_page = min(200, max(1, int(request.args.get('per_page', 100))))
    except ValueError:
        return jsonify({"success": False, "error": "Invalid page parameters."}), 400

    conn = database.get_db()
    cursor = conn.cursor()

    where = ["s.status != 'Archived'"]
    params = []
    if campus_id.isdigit():
        where.append("s.campus_id = ?")
        params.append(int(campus_id))
    if search:
        where.append("(s.student_id LIKE ? OR s.full_name LIKE ? OR s.email LIKE ? OR s.phone LIKE ?)")
        wildcard = f"%{search}%"
        params.extend([wildcard, wildcard, wildcard, wildcard])
    if status:
        where.append("s.status = ?")
        params.append(status)
    if course:
        where.append("s.course = ?")
        params.append(course)
    paid_sql = """
        COALESCE((SELECT SUM(fp.amount) FROM fee_payments fp WHERE fp.student_id = s.student_id), 0)
    """
    pending_sql = f"(s.total_fee - s.concession - {paid_sql})"
    if fee_status == "Paid":
        where.append(f"{pending_sql} <= 0")
    elif fee_status == "Partially Paid":
        where.append(f"{pending_sql} > 0 AND {paid_sql} > 0")
    elif fee_status == "Pending":
        where.append(f"{pending_sql} > 0 AND {paid_sql} <= 0")
    where_sql = " AND ".join(where)

    cursor.execute(f"SELECT COUNT(*) AS total FROM students s WHERE {where_sql}", params)
    total_count = cursor.fetchone()["total"]
    query = """
        SELECT 
            s.*,
            c.name as campus_name,
            c.code as campus_code,
            COALESCE((
                SELECT SUM(fp.amount) 
                FROM fee_payments fp 
                WHERE fp.student_id = s.student_id
            ), 0) as paid_amount,
            (
                SELECT hr.room_number || ' (' || hr.block_name || ')'
                FROM hostel_allocations ha
                JOIN hostel_rooms hr ON hr.id = ha.room_id
                WHERE ha.student_id = s.student_id AND ha.status = 'Active'
                LIMIT 1
            ) as hostel_room,
            (
                SELECT 
                    ROUND(SUM(CASE WHEN ar.status = 'Present' THEN 1 ELSE 0 END) * 100.0 / COUNT(ar.id), 1)
                FROM attendance_records ar
                WHERE ar.student_id = s.student_id
            ) as attendance_pct
        FROM students s
        JOIN campuses c ON c.id = s.campus_id
        WHERE 
    """
    query += f"{where_sql} ORDER BY s.id DESC LIMIT ? OFFSET ?"
    cursor.execute(query, params + [per_page, (page - 1) * per_page])
    raw_students = cursor.fetchall()

    students = []
    for row in raw_students:
        s = dict_from_row(row)
        total_fee = float(s['total_fee'])
        concession = float(s['concession'])
        paid = float(s['paid_amount'])
        pending = max(0.0, total_fee - concession - paid)
        s['pending_amount'] = pending
        
        # Determine fee status label
        if pending <= 0:
            s_fee_status = "Paid"
        elif paid > 0:
            s_fee_status = "Partially Paid"
        else:
            s_fee_status = "Pending"
        s['fee_status'] = s_fee_status

        students.append(s)

    conn.close()
    return jsonify({
        "success": True,
        "students": students,
        "total": total_count,
        "page": page,
        "per_page": per_page,
        "pages": (total_count + per_page - 1) // per_page
    })

@app.route('/api/students/<student_id>', methods=['GET'])
def get_student_details(student_id):
    conn = database.get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT s.*, c.name as campus_name, c.code as campus_code, c.has_hostel
        FROM students s
        JOIN campuses c ON c.id = s.campus_id
        WHERE s.student_id = ?
    """, (student_id,))
    student_row = cursor.fetchone()

    if not student_row:
        conn.close()
        return jsonify({"success": False, "error": "Student not found"}), 404

    student = dict_from_row(student_row)

    # Fee payments
    cursor.execute("""
        SELECT * FROM fee_payments 
        WHERE student_id = ? 
        ORDER BY id DESC
    """, (student_id,))
    payments = [dict_from_row(r) for r in cursor.fetchall()]

    total_paid = sum(p['amount'] for p in payments)
    pending = max(0.0, student['total_fee'] - student['concession'] - total_paid)
    student['paid_amount'] = total_paid
    student['pending_amount'] = pending

    # Attendance logs & stats
    cursor.execute("""
        SELECT date, status, marked_by 
        FROM attendance_records 
        WHERE student_id = ? 
        ORDER BY date DESC LIMIT 30
    """, (student_id,))
    att_records = [dict_from_row(r) for r in cursor.fetchall()]
    total_days = len(att_records)
    present_days = sum(1 for a in att_records if a['status'] == 'Present')
    att_pct = round((present_days / total_days * 100), 1) if total_days > 0 else 100.0

    # Hostel allocation
    cursor.execute("""
        SELECT ha.*, hr.room_number, hr.block_name, hr.capacity
        FROM hostel_allocations ha
        JOIN hostel_rooms hr ON hr.id = ha.room_id
        WHERE ha.student_id = ? AND ha.status = 'Active'
    """, (student_id,))
    hostel_row = cursor.fetchone()

    # Transfer history
    cursor.execute("""
        SELECT st.*, fc.name as from_campus_name, tc.name as to_campus_name
        FROM student_transfers st
        JOIN campuses fc ON fc.id = st.from_campus_id
        JOIN campuses tc ON tc.id = st.to_campus_id
        WHERE st.student_id = ?
        ORDER BY st.id DESC
    """, (student_id,))
    transfers = [dict_from_row(r) for r in cursor.fetchall()]

    conn.close()

    return jsonify({
        "success": True,
        "student": student,
        "payments": payments,
        "attendance": {
            "records": att_records,
            "total_days": total_days,
            "present_days": present_days,
            "percentage": att_pct
        },
        "hostel": dict_from_row(hostel_row) if hostel_row else None,
        "transfers": transfers
    })

# --- Duplicate Check Endpoint ---
@app.route('/api/students/check-duplicate', methods=['POST'])
def check_duplicate_student():
    data = request.json or {}
    email = data.get('email', '').strip()
    phone = data.get('phone', '').strip()
    first_name = data.get('first_name', '').strip()
    last_name = data.get('last_name', '').strip()
    full_name = f"{first_name} {last_name}".strip()
    exclude_id = data.get('exclude_student_id')

    conn = database.get_db()
    cursor = conn.cursor()

    matches = []
    if email:
        q = "SELECT student_id, full_name, campus_id, email, phone FROM students WHERE email = ? AND status != 'Archived'"
        p = [email]
        if exclude_id:
            q += " AND student_id != ?"
            p.append(exclude_id)
        cursor.execute(q, p)
        row = cursor.fetchone()
        if row:
            matches.append({"field": "Email", "value": email, "existing_student": dict_from_row(row)})

    if phone:
        q = "SELECT student_id, full_name, campus_id, email, phone FROM students WHERE phone = ? AND status != 'Archived'"
        p = [phone]
        if exclude_id:
            q += " AND student_id != ?"
            p.append(exclude_id)
        cursor.execute(q, p)
        row = cursor.fetchone()
        if row:
            matches.append({"field": "Phone Number", "value": phone, "existing_student": dict_from_row(row)})

    if full_name:
        q = "SELECT student_id, full_name, campus_id, email, phone FROM students WHERE LOWER(full_name) = LOWER(?) AND status != 'Archived'"
        p = [full_name]
        if exclude_id:
            q += " AND student_id != ?"
            p.append(exclude_id)
        cursor.execute(q, p)
        row = cursor.fetchone()
        if row:
            matches.append({"field": "Full Name", "value": full_name, "existing_student": dict_from_row(row)})

    conn.close()

    if matches:
        return jsonify({
            "is_duplicate": True,
            "message": f"Potential duplicate record found matching {matches[0]['field']}: '{matches[0]['value']}'.",
            "matches": matches
        })
    return jsonify({"is_duplicate": False})

# --- Create Student / Admission ---
@app.route('/api/students', methods=['POST'])
def create_student():
    data = request.json or {}
    first_name = data.get('first_name', '').strip()
    last_name = data.get('last_name', '').strip()
    campus_id = data.get('campus_id')
    course = data.get('course', '').strip()
    admission_year = data.get('admission_year')
    email = data.get('email', '').strip()
    phone = data.get('phone', '').strip()
    gender = data.get('gender', 'Other')
    force_duplicate = data.get('force_duplicate', False)

    # Validations
    if not first_name or not last_name or not campus_id or not course or not admission_year:
        return jsonify({"success": False, "error": "Missing required fields (Name, Campus, Course, Year)."}), 400

    try:
        campus_id = int(campus_id)
        admission_year = int(admission_year)
        total_fee = float(data.get('total_fee', 0))
        concession = float(data.get('concession', 0))
        if total_fee < 0 or concession < 0:
            return jsonify({"success": False, "error": "Fee amounts cannot be negative."}), 400
        if concession > total_fee:
            return jsonify({"success": False, "error": "Concession cannot exceed total fee."}), 400
    except (ValueError, TypeError):
        return jsonify({"success": False, "error": "Invalid numerical values provided."}), 400

    conn = database.get_db()
    cursor = conn.cursor()

    # Campus lookup
    cursor.execute("SELECT id, name, code, default_fee FROM campuses WHERE id = ?", (campus_id,))
    campus = cursor.fetchone()
    if not campus:
        conn.close()
        return jsonify({"success": False, "error": "Invalid campus selected."}), 400

    if total_fee == 0:
        total_fee = campus['default_fee']

    # Duplicate check unless forced
    if not force_duplicate:
        cursor.execute("""
            SELECT student_id, full_name, email, phone FROM students 
            WHERE (email = ? OR phone = ?) AND status != 'Archived'
        """, (email, phone))
        dup = cursor.fetchone()
        if dup:
            conn.close()
            return jsonify({
                "success": False,
                "is_duplicate_warning": True,
                "error": f"A student with this contact already exists: {dup['full_name']} ({dup['student_id']}). You can confirm to proceed or edit the details."
            }), 409

    # Generate sequential unique student ID
    student_id = database.get_next_student_id(campus['code'], conn)
    full_name = f"{first_name} {last_name}"

    cursor.execute("""
        INSERT INTO students (student_id, first_name, last_name, full_name, email, phone, campus_id, course, admission_year, gender, status, total_fee, concession)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Active', ?, ?)
    """, (student_id, first_name, last_name, full_name, email, phone, campus_id, course, admission_year, gender, total_fee, concession))

    # Initialize 10 days of attendance
    today = date.today()
    for i in range(10):
        d = (today - timedelta(days=i)).isoformat()
        cursor.execute("""
            INSERT OR IGNORE INTO attendance_records (student_id, campus_id, date, status, marked_by)
            VALUES (?, ?, ?, 'Present', 'Admission Initializer')
        """, (student_id, campus_id, d))

    # Log audit
    role = get_current_user_role()
    database.log_audit(
        role,
        "STUDENT_ADMISSION",
        campus['name'],
        f"Admitted student {full_name} with generated ID {student_id} into {course}.",
        conn
    )

    conn.commit()
    conn.close()

    return jsonify({
        "success": True,
        "message": f"Student registered successfully with ID {student_id}.",
        "student_id": student_id
    })

# --- Update Student ---
@app.route('/api/students/<student_id>', methods=['PUT'])
def update_student(student_id):
    data = request.json or {}
    first_name = data.get('first_name', '').strip()
    last_name = data.get('last_name', '').strip()
    course = data.get('course', '').strip()
    email = data.get('email', '').strip()
    phone = data.get('phone', '').strip()
    status = data.get('status', 'Active')
    gender = data.get('gender', 'Other')

    try:
        total_fee = float(data.get('total_fee', 0))
        concession = float(data.get('concession', 0))
        if total_fee < 0 or concession < 0 or concession > total_fee:
            return jsonify({"success": False, "error": "Invalid fee or concession amounts."}), 400
    except (ValueError, TypeError):
        return jsonify({"success": False, "error": "Invalid numerical values."}), 400

    conn = database.get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT s.*, c.name as campus_name FROM students s JOIN campuses c ON c.id = s.campus_id WHERE s.student_id = ?", (student_id,))
    existing = cursor.fetchone()
    if not existing:
        conn.close()
        return jsonify({"success": False, "error": "Student not found."}), 404

    full_name = f"{first_name} {last_name}" if (first_name and last_name) else existing['full_name']

    cursor.execute("""
        UPDATE students 
        SET first_name = COALESCE(NULLIF(?, ''), first_name),
            last_name = COALESCE(NULLIF(?, ''), last_name),
            full_name = ?,
            course = COALESCE(NULLIF(?, ''), course),
            email = COALESCE(NULLIF(?, ''), email),
            phone = COALESCE(NULLIF(?, ''), phone),
            gender = ?,
            status = ?,
            total_fee = ?,
            concession = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE student_id = ?
    """, (first_name, last_name, full_name, course, email, phone, gender, status, total_fee, concession, student_id))

    role = get_current_user_role()
    database.log_audit(
        role,
        "STUDENT_RECORD_UPDATE",
        existing['campus_name'],
        f"Updated details for student {student_id} ({full_name}).",
        conn
    )

    conn.commit()
    conn.close()

    return jsonify({"success": True, "message": "Student details updated successfully."})

# --- Delete / Archive Student ---
@app.route('/api/students/<student_id>', methods=['DELETE'])
def delete_student(student_id):
    conn = database.get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT s.*, c.name as campus_name FROM students s JOIN campuses c ON c.id = s.campus_id WHERE s.student_id = ?", (student_id,))
    student = cursor.fetchone()
    if not student:
        conn.close()
        return jsonify({"success": False, "error": "Student not found."}), 404

    # Release any active hostel room
    cursor.execute("""
        SELECT room_id FROM hostel_allocations 
        WHERE student_id = ? AND status = 'Active'
    """, (student_id,))
    active_hostel = cursor.fetchone()
    if active_hostel:
        cursor.execute("UPDATE hostel_allocations SET status = 'Released', released_date = date('now') WHERE student_id = ?", (student_id,))
        cursor.execute("""
            UPDATE hostel_rooms 
            SET occupied_beds = MAX(0, occupied_beds - 1),
                status = 'Available'
            WHERE id = ?
        """, (active_hostel['room_id'],))

    # Soft archive to guarantee ID is never reused!
    cursor.execute("UPDATE students SET status = 'Archived', updated_at = CURRENT_TIMESTAMP WHERE student_id = ?", (student_id,))

    role = get_current_user_role()
    database.log_audit(
        role,
        "STUDENT_ARCHIVED",
        student['campus_name'],
        f"Archived student record for {student_id} ({student['full_name']}). Assigned ID permanently preserved.",
        conn
    )

    conn.commit()
    conn.close()

    return jsonify({"success": True, "message": f"Student {student_id} archived. ID permanently preserved."})

# --- Campus Transfer ---
@app.route('/api/students/transfer', methods=['POST'])
def transfer_student():
    data = request.json or {}
    student_id = data.get('student_id', '').strip()
    to_campus_id = data.get('to_campus_id')
    reason = data.get('reason', '').strip()

    if not student_id or not to_campus_id:
        return jsonify({"success": False, "error": "Missing student ID or destination campus."}), 400

    conn = database.get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT s.*, c.name as current_campus_name 
        FROM students s 
        JOIN campuses c ON c.id = s.campus_id 
        WHERE s.student_id = ?
    """, (student_id,))
    student = cursor.fetchone()
    if not student:
        conn.close()
        return jsonify({"success": False, "error": "Student not found."}), 404

    from_campus_id = student['campus_id']
    if int(to_campus_id) == from_campus_id:
        conn.close()
        return jsonify({"success": False, "error": "Destination campus must be different from current campus."}), 400

    cursor.execute("SELECT id, name, code, has_hostel FROM campuses WHERE id = ?", (to_campus_id,))
    to_campus = cursor.fetchone()
    if not to_campus:
        conn.close()
        return jsonify({"success": False, "error": "Destination campus does not exist."}), 400

    # If student has active hostel in old campus, release it
    cursor.execute("SELECT room_id FROM hostel_allocations WHERE student_id = ? AND status = 'Active'", (student_id,))
    active_alloc = cursor.fetchone()
    if active_alloc:
        cursor.execute("UPDATE hostel_allocations SET status = 'Released', released_date = date('now') WHERE student_id = ?", (student_id,))
        cursor.execute("UPDATE hostel_rooms SET occupied_beds = MAX(0, occupied_beds - 1), status = 'Available' WHERE id = ?", (active_alloc['room_id'],))

    # Log transfer history
    role = get_current_user_role()
    cursor.execute("""
        INSERT INTO student_transfers (student_id, from_campus_id, to_campus_id, reason, transferred_by)
        VALUES (?, ?, ?, ?, ?)
    """, (student_id, from_campus_id, int(to_campus_id), reason or "Campus transfer request", role))

    # Update student campus
    cursor.execute("""
        UPDATE students 
        SET campus_id = ?, updated_at = CURRENT_TIMESTAMP 
        WHERE student_id = ?
    """, (int(to_campus_id), student_id))

    database.log_audit(
        role,
        "STUDENT_TRANSFER",
        to_campus['name'],
        f"Transferred student {student_id} ({student['full_name']}) from {student['current_campus_name']} to {to_campus['name']}. Identity preserved.",
        conn
    )

    conn.commit()
    conn.close()

    return jsonify({
        "success": True,
        "message": f"Student {student_id} successfully transferred to {to_campus['name']}."
    })

@app.route('/api/students/<student_id>/examinations', methods=['GET'])
def get_student_examinations(student_id):
    conn = database.get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT campus_id, course FROM students WHERE student_id = ? AND status != 'Archived'",
        (student_id,)
    )
    student = cursor.fetchone()
    if not student:
        conn.close()
        return jsonify({"success": False, "error": "Student not found."}), 404

    cursor.execute("""
        SELECT e.*, c.name AS campus_name
        FROM examinations e
        JOIN campuses c ON c.id = e.campus_id
        WHERE e.campus_id = ? AND e.course = ?
        ORDER BY CASE WHEN e.exam_date >= date('now') THEN 0 ELSE 1 END,
                 e.exam_date ASC, e.start_time ASC
    """, (student["campus_id"], student["course"]))
    exams = [dict_from_row(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify({"success": True, "examinations": exams})

# --- Scholarship Management ---
@app.route('/api/scholarships', methods=['GET', 'POST'])
def scholarships():
    if request.method == 'POST':
        data = request.get_json(silent=True) or {}
        scholarship_name = str(data.get('scholarship_name', '')).strip()
        student_id = str(data.get('student_id', '')).strip()
        eligibility = str(data.get('eligibility', '')).strip()
        application_status = str(data.get('application_status', 'Pending')).strip()
        approval_status = str(data.get('approval_status', 'Pending')).strip()
        try:
            campus_id = int(data.get('campus_id'))
            amount = float(data.get('amount'))
        except (TypeError, ValueError):
            return jsonify({"success": False, "error": "Campus and scholarship amount must be valid numbers."}), 400
        if not scholarship_name or not student_id or not eligibility or not math.isfinite(amount) or amount < 0:
            return jsonify({"success": False, "error": "Scholarship name, student ID, eligibility, and a non-negative amount are required."}), 400
        if application_status not in {"Pending", "Submitted", "Under Review", "Withdrawn"}:
            return jsonify({"success": False, "error": "Invalid application status."}), 400
        if approval_status not in {"Pending", "Approved", "Rejected"}:
            return jsonify({"success": False, "error": "Invalid approval status."}), 400

        conn = database.get_db()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT campus_id FROM students WHERE student_id = ? AND status != 'Archived'",
            (student_id,)
        )
        student = cursor.fetchone()
        if not student:
            conn.close()
            return jsonify({"success": False, "error": "Active student not found."}), 404
        if student["campus_id"] != campus_id:
            conn.close()
            return jsonify({"success": False, "error": "Selected campus does not match the student's campus."}), 400
        try:
            cursor.execute("""
                INSERT INTO scholarships (
                    scholarship_name, student_id, campus_id, amount, eligibility,
                    application_status, approval_status
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                scholarship_name, student_id, campus_id, amount, eligibility,
                application_status, approval_status
            ))
        except sqlite3.IntegrityError:
            conn.close()
            return jsonify({"success": False, "error": "This student already has an application for that scholarship."}), 409
        scholarship_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return jsonify({"success": True, "id": scholarship_id, "message": "Scholarship application added."})

    search = request.args.get('search', '').strip()
    campus_id = request.args.get('campus_id', '').strip()
    application_status = request.args.get('application_status', '').strip()
    approval_status = request.args.get('approval_status', '').strip()
    try:
        page = max(1, int(request.args.get('page', 1)))
        per_page = min(200, max(1, int(request.args.get('per_page', 100))))
    except ValueError:
        return jsonify({"success": False, "error": "Invalid page parameters."}), 400

    where = ["1 = 1"]
    params = []
    if campus_id.isdigit():
        where.append("s.campus_id = ?")
        params.append(int(campus_id))
    if application_status:
        where.append("s.application_status = ?")
        params.append(application_status)
    if approval_status:
        where.append("s.approval_status = ?")
        params.append(approval_status)
    if search:
        wildcard = f"%{search}%"
        where.append("(s.scholarship_name LIKE ? OR s.student_id LIKE ? OR st.full_name LIKE ?)")
        params.extend([wildcard, wildcard, wildcard])
    where_sql = " AND ".join(where)

    conn = database.get_db()
    cursor = conn.cursor()
    cursor.execute(f"""
        SELECT COUNT(*) AS total,
               COALESCE(SUM(s.approval_status = 'Approved'), 0) AS approved,
               COALESCE(SUM(s.approval_status = 'Pending'), 0) AS pending,
               COALESCE(SUM(s.amount), 0) AS amount_total
        FROM scholarships s
        JOIN students st ON st.student_id = s.student_id
        WHERE {where_sql}
    """, params)
    stats = dict_from_row(cursor.fetchone())
    cursor.execute(f"""
        SELECT s.*, c.name AS campus_name, st.full_name AS student_name, st.course
        FROM scholarships s
        JOIN campuses c ON c.id = s.campus_id
        JOIN students st ON st.student_id = s.student_id
        WHERE {where_sql}
        ORDER BY s.id DESC LIMIT ? OFFSET ?
    """, params + [per_page, (page - 1) * per_page])
    records = [dict_from_row(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify({
        "success": True,
        "scholarships": records,
        "total": stats["total"],
        "page": page,
        "per_page": per_page,
        "stats": {
            "total_scholarships": stats["total"],
            "approved_applications": stats["approved"],
            "pending_applications": stats["pending"],
            "scholarship_amounts": stats["amount_total"]
        }
    })

@app.route('/api/scholarships/<int:scholarship_id>', methods=['PUT'])
def update_scholarship(scholarship_id):
    data = request.get_json(silent=True) or {}
    scholarship_name = str(data.get('scholarship_name', '')).strip()
    student_id = str(data.get('student_id', '')).strip()
    eligibility = str(data.get('eligibility', '')).strip()
    application_status = str(data.get('application_status', 'Pending')).strip()
    approval_status = str(data.get('approval_status', 'Pending')).strip()
    try:
        campus_id = int(data.get('campus_id'))
        amount = float(data.get('amount'))
    except (TypeError, ValueError):
        return jsonify({"success": False, "error": "Campus and scholarship amount must be valid numbers."}), 400
    if not scholarship_name or not student_id or not eligibility or not math.isfinite(amount) or amount < 0:
        return jsonify({"success": False, "error": "Scholarship name, student ID, eligibility, and a non-negative amount are required."}), 400
    if application_status not in {"Pending", "Submitted", "Under Review", "Withdrawn"}:
        return jsonify({"success": False, "error": "Invalid application status."}), 400
    if approval_status not in {"Pending", "Approved", "Rejected"}:
        return jsonify({"success": False, "error": "Invalid approval status."}), 400

    conn = database.get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT campus_id FROM students WHERE student_id = ? AND status != 'Archived'",
        (student_id,)
    )
    student = cursor.fetchone()
    if not student:
        conn.close()
        return jsonify({"success": False, "error": "Active student not found."}), 404
    if student["campus_id"] != campus_id:
        conn.close()
        return jsonify({"success": False, "error": "Selected campus does not match the student's campus."}), 400
    try:
        cursor.execute("""
            UPDATE scholarships
            SET scholarship_name = ?, student_id = ?, campus_id = ?, amount = ?,
                eligibility = ?, application_status = ?, approval_status = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (
            scholarship_name, student_id, campus_id, amount, eligibility,
            application_status, approval_status, scholarship_id
        ))
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({"success": False, "error": "This student already has an application for that scholarship."}), 409
    if cursor.rowcount == 0:
        conn.close()
        return jsonify({"success": False, "error": "Scholarship application not found."}), 404
    conn.commit()
    conn.close()
    return jsonify({"success": True, "message": "Scholarship application updated."})

# --- Examination Management ---
@app.route('/api/examinations', methods=['GET', 'POST'])
def examinations():
    if request.method == 'POST':
        data = request.get_json(silent=True) or {}
        try:
            campus_id = int(data.get('campus_id'))
            exam_date = date.fromisoformat(str(data.get('exam_date', '')))
            start_time = datetime.strptime(str(data.get('start_time', '')), '%H:%M').time()
            end_time = datetime.strptime(str(data.get('end_time', '')), '%H:%M').time()
        except (TypeError, ValueError):
            return jsonify({"success": False, "error": "Campus, exam date, and times must be valid."}), 400
        course = str(data.get('course', '')).strip()
        subject_name = str(data.get('subject_name', '')).strip()
        subject_code = str(data.get('subject_code', '')).strip()
        exam_type = str(data.get('exam_type', '')).strip()
        status = str(data.get('status', 'Scheduled')).strip()
        if not course or not subject_name or not subject_code or not exam_type:
            return jsonify({"success": False, "error": "Course, subject, subject code, and exam type are required."}), 400
        if end_time <= start_time:
            return jsonify({"success": False, "error": "Exam end time must be after its start time."}), 400
        if status not in {"Scheduled", "Completed", "Cancelled"}:
            return jsonify({"success": False, "error": "Invalid examination status."}), 400

        conn = database.get_db()
        cursor = conn.cursor()
        if not cursor.execute("SELECT id FROM campuses WHERE id = ?", (campus_id,)).fetchone():
            conn.close()
            return jsonify({"success": False, "error": "Invalid campus selected."}), 400
        try:
            cursor.execute("""
                INSERT INTO examinations (
                    campus_id, course, subject_name, subject_code, exam_date,
                    start_time, end_time, exam_type, status
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                campus_id, course, subject_name, subject_code, exam_date.isoformat(),
                start_time.strftime('%H:%M'), end_time.strftime('%H:%M'), exam_type, status
            ))
        except sqlite3.IntegrityError:
            conn.close()
            return jsonify({"success": False, "error": "This examination is already scheduled."}), 409
        exam_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return jsonify({"success": True, "id": exam_id, "message": "Examination scheduled."})

    search = request.args.get('search', '').strip()
    campus_id = request.args.get('campus_id', '').strip()
    status = request.args.get('status', '').strip()
    where = ["1 = 1"]
    params = []
    if campus_id.isdigit():
        where.append("e.campus_id = ?")
        params.append(int(campus_id))
    if status:
        where.append("e.status = ?")
        params.append(status)
    if search:
        wildcard = f"%{search}%"
        where.append("(e.course LIKE ? OR e.subject_name LIKE ? OR e.subject_code LIKE ? OR c.name LIKE ?)")
        params.extend([wildcard, wildcard, wildcard, wildcard])
    where_sql = " AND ".join(where)
    conn = database.get_db()
    cursor = conn.cursor()
    cursor.execute(f"""
        SELECT COUNT(*) AS total,
               COALESCE(SUM(e.status = 'Scheduled' AND e.exam_date >= date('now')), 0) AS upcoming,
               COALESCE(SUM(e.status = 'Completed'), 0) AS completed
        FROM examinations e
        JOIN campuses c ON c.id = e.campus_id
        WHERE {where_sql}
    """, params)
    stats = dict_from_row(cursor.fetchone())
    cursor.execute(f"""
        SELECT e.*, c.name AS campus_name
        FROM examinations e
        JOIN campuses c ON c.id = e.campus_id
        WHERE {where_sql}
        ORDER BY e.exam_date ASC, e.start_time ASC
    """, params)
    records = [dict_from_row(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify({
        "success": True,
        "examinations": records,
        "total": stats["total"],
        "stats": {"upcoming_examinations": stats["upcoming"], "completed_examinations": stats["completed"]}
    })

@app.route('/api/examinations/<int:exam_id>', methods=['PUT'])
def update_examination(exam_id):
    data = request.get_json(silent=True) or {}
    try:
        campus_id = int(data.get('campus_id'))
        exam_date = date.fromisoformat(str(data.get('exam_date', '')))
        start_time = datetime.strptime(str(data.get('start_time', '')), '%H:%M').time()
        end_time = datetime.strptime(str(data.get('end_time', '')), '%H:%M').time()
    except (TypeError, ValueError):
        return jsonify({"success": False, "error": "Campus, exam date, and times must be valid."}), 400
    course = str(data.get('course', '')).strip()
    subject_name = str(data.get('subject_name', '')).strip()
    subject_code = str(data.get('subject_code', '')).strip()
    exam_type = str(data.get('exam_type', '')).strip()
    status = str(data.get('status', 'Scheduled')).strip()
    if not course or not subject_name or not subject_code or not exam_type:
        return jsonify({"success": False, "error": "Course, subject, subject code, and exam type are required."}), 400
    if end_time <= start_time:
        return jsonify({"success": False, "error": "Exam end time must be after its start time."}), 400
    if status not in {"Scheduled", "Completed", "Cancelled"}:
        return jsonify({"success": False, "error": "Invalid examination status."}), 400
    conn = database.get_db()
    cursor = conn.cursor()
    if not cursor.execute("SELECT id FROM campuses WHERE id = ?", (campus_id,)).fetchone():
        conn.close()
        return jsonify({"success": False, "error": "Invalid campus selected."}), 400
    try:
        cursor.execute("""
            UPDATE examinations
            SET campus_id = ?, course = ?, subject_name = ?, subject_code = ?,
                exam_date = ?, start_time = ?, end_time = ?, exam_type = ?, status = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (
            campus_id, course, subject_name, subject_code, exam_date.isoformat(),
            start_time.strftime('%H:%M'), end_time.strftime('%H:%M'),
            exam_type, status, exam_id
        ))
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({"success": False, "error": "This examination is already scheduled."}), 409
    if cursor.rowcount == 0:
        conn.close()
        return jsonify({"success": False, "error": "Examination not found."}), 404
    conn.commit()
    conn.close()
    return jsonify({"success": True, "message": "Examination updated."})

# --- Fee Management ---
@app.route('/api/fees/payments', methods=['POST'])
def add_fee_payment():
    data = request.json or {}
    student_id = data.get('student_id', '').strip()
    payment_mode = data.get('payment_mode', 'UPI').strip()
    notes = data.get('notes', '').strip()
    payment_date = data.get('payment_date', date.today().isoformat())

    try:
        amount = float(data.get('amount', 0))
        if amount <= 0:
            return jsonify({"success": False, "error": "Payment amount must be greater than zero."}), 400
    except (ValueError, TypeError):
        return jsonify({"success": False, "error": "Invalid payment amount format."}), 400

    conn = database.get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT s.*, c.name as campus_name,
               COALESCE((SELECT SUM(amount) FROM fee_payments fp WHERE fp.student_id = s.student_id), 0) as paid
        FROM students s
        JOIN campuses c ON c.id = s.campus_id
        WHERE s.student_id = ?
    """, (student_id,))
    student = cursor.fetchone()
    if not student:
        conn.close()
        return jsonify({"success": False, "error": "Student not found."}), 404

    pending_balance = max(0.0, student['total_fee'] - student['concession'] - student['paid'])
    if amount > pending_balance:
        conn.close()
        return jsonify({
            "success": False, 
            "error": f"Payment amount (₹{amount:,.2f}) cannot exceed outstanding pending balance of ₹{pending_balance:,.2f}."
        }), 400

    # Generate receipt number
    cursor.execute("SELECT COUNT(*) as cnt FROM fee_payments")
    rec_count = cursor.fetchone()['cnt'] + 1001
    receipt_no = f"REC-{datetime.now().year}-{rec_count:04d}"

    role = get_current_user_role()
    cursor.execute("""
        INSERT INTO fee_payments (receipt_no, student_id, campus_id, amount, payment_date, payment_mode, notes, created_by)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (receipt_no, student_id, student['campus_id'], amount, payment_date, payment_mode, notes, role))

    database.log_audit(
        role,
        "FEE_PAYMENT",
        student['campus_name'],
        f"Recorded fee payment of ₹{amount:,.2f} ({payment_mode}) for {student_id} ({student['full_name']}). Receipt: {receipt_no}",
        conn
    )

    conn.commit()
    conn.close()

    return jsonify({
        "success": True,
        "message": f"Payment of ₹{amount:,.2f} recorded successfully.",
        "receipt_no": receipt_no
    })

# --- Fee Payment Reversal ---
@app.route('/api/fees/reversal', methods=['POST'])
def reverse_fee_payment():
    data = request.json or {}
    receipt_no = data.get('receipt_no', '').strip()
    reason = data.get('reason', '').strip()

    if not receipt_no or not reason:
        return jsonify({"success": False, "error": "Receipt number and reversal reason are required."}), 400

    conn = database.get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT fp.*, s.full_name, c.name as campus_name
        FROM fee_payments fp
        JOIN students s ON s.student_id = fp.student_id
        JOIN campuses c ON c.id = fp.campus_id
        WHERE fp.receipt_no = ?
    """, (receipt_no,))
    orig = cursor.fetchone()

    if not orig:
        conn.close()
        return jsonify({"success": False, "error": "Original payment receipt not found."}), 404

    if orig['amount'] <= 0:
        conn.close()
        return jsonify({"success": False, "error": "Cannot reverse a reversal entry."}), 400

    # Check if already reversed
    cursor.execute("SELECT id FROM fee_payments WHERE reference_receipt_no = ?", (receipt_no,))
    if cursor.fetchone():
        conn.close()
        return jsonify({"success": False, "error": "This receipt has already been reversed."}), 400

    # Create reversal entry (negative amount)
    cursor.execute("SELECT COUNT(*) as cnt FROM fee_payments")
    rec_count = cursor.fetchone()['cnt'] + 1001
    rev_receipt_no = f"REV-{datetime.now().year}-{rec_count:04d}"
    reversal_amount = -abs(orig['amount'])

    role = get_current_user_role()
    cursor.execute("""
        INSERT INTO fee_payments (receipt_no, student_id, campus_id, amount, payment_date, payment_mode, transaction_type, reference_receipt_no, notes, created_by)
        VALUES (?, ?, ?, ?, date('now'), ?, 'Reversal', ?, ?, ?)
    """, (rev_receipt_no, orig['student_id'], orig['campus_id'], reversal_amount, orig['payment_mode'], receipt_no, f"Reversal: {reason}", role))

    database.log_audit(
        role,
        "FEE_REVERSAL",
        orig['campus_name'],
        f"Reversed payment {receipt_no} of ₹{orig['amount']:,.2f} for {orig['student_id']}. Reversal reference: {rev_receipt_no}. Reason: {reason}",
        conn
    )

    conn.commit()
    conn.close()

    return jsonify({
        "success": True,
        "message": f"Payment {receipt_no} reversed successfully. Reversal receipt: {rev_receipt_no}.",
        "reversal_receipt": rev_receipt_no
    })

# --- Attendance Management ---
@app.route('/api/attendance', methods=['GET'])
def get_attendance():
    campus_id = request.args.get('campus_id', '')
    att_date = request.args.get('date', date.today().isoformat())
    course = request.args.get('course', '')

    conn = database.get_db()
    cursor = conn.cursor()

    query = """
        SELECT s.student_id, s.full_name, s.course, c.name as campus_name,
               COALESCE(ar.status, 'Not Marked') as status,
               ar.id as attendance_id,
               (
                   SELECT ROUND(SUM(CASE WHEN a.status = 'Present' THEN 1 ELSE 0 END) * 100.0 / COUNT(a.id), 1)
                   FROM attendance_records a
                   WHERE a.student_id = s.student_id
               ) as overall_pct
        FROM students s
        JOIN campuses c ON c.id = s.campus_id
        LEFT JOIN attendance_records ar ON ar.student_id = s.student_id AND ar.date = ?
        WHERE s.status != 'Archived'
    """
    params = [att_date]

    if campus_id.isdigit():
        query += " AND s.campus_id = ?"
        params.append(int(campus_id))

    if course:
        query += " AND s.course = ?"
        params.append(course)

    query += " ORDER BY s.student_id ASC"
    cursor.execute(query, params)
    records = [dict_from_row(r) for r in cursor.fetchall()]

    # Summary
    present_cnt = sum(1 for r in records if r['status'] == 'Present')
    absent_cnt = sum(1 for r in records if r['status'] == 'Absent')
    not_marked_cnt = sum(1 for r in records if r['status'] == 'Not Marked')

    conn.close()

    return jsonify({
        "success": True,
        "date": att_date,
        "summary": {
            "total": len(records),
            "present": present_cnt,
            "absent": absent_cnt,
            "not_marked": not_marked_cnt
        },
        "records": records
    })

@app.route('/api/attendance/mark', methods=['POST'])
def mark_attendance():
    data = request.json or {}
    records = data.get('records', [])  # list of {student_id, status}
    att_date = data.get('date', date.today().isoformat())

    if not records:
        return jsonify({"success": False, "error": "No attendance records provided."}), 400

    conn = database.get_db()
    cursor = conn.cursor()
    role = get_current_user_role()

    marked_count = 0
    for r in records:
        sid = r.get('student_id')
        st = r.get('status')
        if not sid or st not in ['Present', 'Absent']:
            continue

        cursor.execute("SELECT campus_id FROM students WHERE student_id = ?", (sid,))
        s_row = cursor.fetchone()
        if not s_row:
            continue

        cursor.execute("""
            INSERT INTO attendance_records (student_id, campus_id, date, status, marked_by)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(student_id, date) DO UPDATE SET
                status = excluded.status,
                marked_by = excluded.marked_by
        """, (sid, s_row['campus_id'], att_date, st, role))
        marked_count += 1

    database.log_audit(
        role,
        "ATTENDANCE_MARKED",
        "Multiple",
        f"Recorded daily attendance for {marked_count} students on {att_date}.",
        conn
    )

    conn.commit()
    conn.close()

    return jsonify({"success": True, "message": f"Successfully updated attendance for {marked_count} students."})

# --- Hostel Management ---
@app.route('/api/hostel/rooms', methods=['GET'])
def get_hostel_rooms():
    campus_id = request.args.get('campus_id', '')
    conn = database.get_db()
    cursor = conn.cursor()

    query = """
        SELECT hr.*, c.name as campus_name, c.code as campus_code,
               (hr.capacity - hr.occupied_beds) as available_beds,
               ROUND(hr.occupied_beds * 100.0 / hr.capacity, 1) as occupancy_pct
        FROM hostel_rooms hr
        JOIN campuses c ON c.id = hr.campus_id
        WHERE 1=1
    """
    params = []
    if campus_id.isdigit():
        query += " AND hr.campus_id = ?"
        params.append(int(campus_id))

    query += " ORDER BY hr.campus_id, hr.room_number"
    cursor.execute(query, params)
    rooms = [dict_from_row(r) for r in cursor.fetchall()]

    # Fetch active allocations for these rooms
    for rm in rooms:
        cursor.execute("""
            SELECT ha.*, s.full_name, s.course, s.phone
            FROM hostel_allocations ha
            JOIN students s ON s.student_id = ha.student_id
            WHERE ha.room_id = ? AND ha.status = 'Active'
        """, (rm['id'],))
        rm['allocated_students'] = [dict_from_row(ar) for ar in cursor.fetchall()]

    conn.close()
    return jsonify({"success": True, "rooms": rooms})

@app.route('/api/hostel/rooms', methods=['POST'])
def add_hostel_room():
    data = request.json or {}
    room_number = data.get('room_number', '').strip()
    campus_id = data.get('campus_id')
    block_name = data.get('block_name', 'Main Block').strip()
    capacity = data.get('capacity', 3)

    if not room_number or not campus_id:
        return jsonify({"success": False, "error": "Room number and campus are required."}), 400

    try:
        capacity = int(capacity)
        campus_id = int(campus_id)
        if capacity <= 0:
            return jsonify({"success": False, "error": "Capacity must be greater than zero."}), 400
    except ValueError:
        return jsonify({"success": False, "error": "Invalid numerical parameters."}), 400

    conn = database.get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT id, name, has_hostel FROM campuses WHERE id = ?", (campus_id,))
    camp = cursor.fetchone()
    if not camp:
        conn.close()
        return jsonify({"success": False, "error": "Campus not found."}), 400

    if not camp['has_hostel']:
        conn.close()
        return jsonify({"success": False, "error": f"{camp['name']} is configured as a non-residential campus with no hostel facilities."}), 400

    try:
        cursor.execute("""
            INSERT INTO hostel_rooms (room_number, campus_id, block_name, capacity, occupied_beds, status)
            VALUES (?, ?, ?, ?, 0, 'Available')
        """, (room_number, campus_id, block_name, capacity))
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({"success": False, "error": f"Room '{room_number}' already exists for {camp['name']}."}), 400

    role = get_current_user_role()
    database.log_audit(
        role,
        "HOSTEL_ROOM_ADDED",
        camp['name'],
        f"Added hostel room {room_number} ({block_name}) with capacity {capacity}.",
        conn
    )
    conn.close()

    return jsonify({"success": True, "message": f"Hostel room {room_number} added successfully."})

@app.route('/api/hostel/allocate', methods=['POST'])
def allocate_hostel_room():
    data = request.json or {}
    room_id = data.get('room_id')
    student_id = data.get('student_id', '').strip()
    remarks = data.get('remarks', 'Standard room allotment').strip()

    if not room_id or not student_id:
        return jsonify({"success": False, "error": "Room and Student are required."}), 400

    conn = database.get_db()
    cursor = conn.cursor()

    # Verify student
    cursor.execute("""
        SELECT s.*, c.name as campus_name, c.has_hostel 
        FROM students s 
        JOIN campuses c ON c.id = s.campus_id 
        WHERE s.student_id = ?
    """, (student_id,))
    student = cursor.fetchone()
    if not student:
        conn.close()
        return jsonify({"success": False, "error": "Student not found."}), 404

    # Verify room
    cursor.execute("""
        SELECT hr.*, c.name as campus_name 
        FROM hostel_rooms hr 
        JOIN campuses c ON c.id = hr.campus_id 
        WHERE hr.id = ?
    """, (room_id,))
    room = cursor.fetchone()
    if not room:
        conn.close()
        return jsonify({"success": False, "error": "Hostel room not found."}), 404

    # Validate campus match
    if room['campus_id'] != student['campus_id']:
        conn.close()
        return jsonify({"success": False, "error": f"Cannot allocate room in {room['campus_name']} to student enrolled in {student['campus_name']}."}), 400

    # Check if student already has active allocation
    cursor.execute("SELECT id FROM hostel_allocations WHERE student_id = ? AND status = 'Active'", (student_id,))
    if cursor.fetchone():
        conn.close()
        return jsonify({"success": False, "error": f"Student {student_id} already has an active hostel room allocation."}), 400

    # Check room capacity
    if room['occupied_beds'] >= room['capacity']:
        conn.close()
        return jsonify({"success": False, "error": f"Room {room['room_number']} is full (Capacity: {room['capacity']})."}), 400

    bed_number = room['occupied_beds'] + 1
    cursor.execute("""
        INSERT INTO hostel_allocations (room_id, student_id, campus_id, bed_number, allocated_date, status, remarks)
        VALUES (?, ?, ?, ?, date('now'), 'Active', ?)
    """, (room_id, student_id, student['campus_id'], bed_number, remarks))

    new_occupied = room['occupied_beds'] + 1
    new_status = 'Full' if new_occupied >= room['capacity'] else 'Available'
    cursor.execute("UPDATE hostel_rooms SET occupied_beds = ?, status = ? WHERE id = ?", (new_occupied, new_status, room_id))

    role = get_current_user_role()
    database.log_audit(
        role,
        "HOSTEL_ALLOCATED",
        room['campus_name'],
        f"Allocated bed {bed_number} in Room {room['room_number']} to student {student_id} ({student['full_name']}).",
        conn
    )

    conn.commit()
    conn.close()

    return jsonify({"success": True, "message": f"Student {student_id} successfully allocated to Room {room['room_number']}."})

@app.route('/api/hostel/release', methods=['POST'])
def release_hostel_room():
    data = request.json or {}
    allocation_id = data.get('allocation_id')

    if not allocation_id:
        return jsonify({"success": False, "error": "Allocation ID is required."}), 400

    conn = database.get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT ha.*, hr.room_number, s.full_name, c.name as campus_name
        FROM hostel_allocations ha
        JOIN hostel_rooms hr ON hr.id = ha.room_id
        JOIN students s ON s.student_id = ha.student_id
        JOIN campuses c ON c.id = ha.campus_id
        WHERE ha.id = ? AND ha.status = 'Active'
    """, (allocation_id,))
    alloc = cursor.fetchone()

    if not alloc:
        conn.close()
        return jsonify({"success": False, "error": "Active allocation not found."}), 404

    cursor.execute("""
        UPDATE hostel_allocations 
        SET status = 'Released', released_date = date('now') 
        WHERE id = ?
    """, (allocation_id,))

    cursor.execute("""
        UPDATE hostel_rooms 
        SET occupied_beds = MAX(0, occupied_beds - 1),
            status = 'Available'
        WHERE id = ?
    """, (alloc['room_id'],))

    role = get_current_user_role()
    database.log_audit(
        role,
        "HOSTEL_RELEASED",
        alloc['campus_name'],
        f"Released hostel allocation for student {alloc['student_id']} from Room {alloc['room_number']}.",
        conn
    )

    conn.commit()
    conn.close()

    return jsonify({"success": True, "message": "Hostel bed released successfully."})

# --- Spreadsheet Import & Export (Pandas & openpyxl) ---
@app.route('/api/import/preview', methods=['POST'])
def preview_spreadsheet():
    if 'file' not in request.files:
        return jsonify({"success": False, "error": "No file uploaded."}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"success": False, "error": "No file selected."}), 400

    filename = file.filename.lower()
    if not (filename.endswith('.csv') or filename.endswith('.xlsx') or filename.endswith('.xls')):
        return jsonify({"success": False, "error": "Only .csv and .xlsx files are supported."}), 400

    import pandas as pd

    try:
        if filename.endswith('.csv'):
            df = pd.read_csv(file)
        else:
            df = pd.read_excel(file)
    except Exception as e:
        return jsonify({"success": False, "error": f"Error reading spreadsheet: {str(e)}"}), 400

    # Normalize column names
    df.columns = [str(c).strip().lower().replace(' ', '_') for c in df.columns]

    conn = database.get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, code, default_fee FROM campuses")
    campuses_list = [dict_from_row(r) for r in cursor.fetchall()]
    campus_name_map = {c['name'].lower(): c for c in campuses_list}
    campus_code_map = {c['code'].lower(): c for c in campuses_list}

    # Fetch existing emails and phones for duplicate detection
    cursor.execute("SELECT email, phone FROM students WHERE status != 'Archived'")
    existing_records = cursor.fetchall()
    existing_emails = {r['email'].lower() for r in existing_records if r['email']}
    existing_phones = {str(r['phone']).strip() for r in existing_records if r['phone']}

    valid_rows = []
    invalid_rows = []
    seen_in_file_emails = set()
    seen_in_file_phones = set()

    for idx, row in df.iterrows():
        row_num = idx + 2  # Excel 1-based header + 1
        errors = []

        # Extract fields
        fname = str(row.get('first_name', '')).strip()
        lname = str(row.get('last_name', '')).strip()
        if not fname:
            # Maybe combined name column
            combined_name = str(row.get('name', '')).strip()
            if combined_name:
                parts = combined_name.split(' ', 1)
                fname = parts[0]
                lname = parts[1] if len(parts) > 1 else 'Student'
            else:
                errors.append("First Name is missing.")

        campus_val = str(row.get('campus', '')).strip().lower()
        matched_campus = campus_name_map.get(campus_val) or campus_code_map.get(campus_val)
        if not matched_campus:
            errors.append(f"Invalid Campus '{campus_val}'. Must be one of the 6 official campuses.")

        course = str(row.get('course', '')).strip()
        if not course:
            errors.append("Course is missing.")

        email = str(row.get('email', '')).strip().lower()
        if not email or '@' not in email:
            errors.append("Invalid or missing email.")
        elif email in existing_emails:
            errors.append(f"Email '{email}' already exists in database.")
        elif email in seen_in_file_emails:
            errors.append(f"Duplicate email '{email}' within file.")
        else:
            seen_in_file_emails.add(email)

        phone = str(row.get('phone', '')).replace('.0', '').strip()
        if not phone or len(phone) < 8:
            errors.append("Invalid phone number.")
        elif phone in existing_phones:
            errors.append(f"Phone '{phone}' already exists in database.")
        elif phone in seen_in_file_phones:
            errors.append(f"Duplicate phone '{phone}' within file.")
        else:
            seen_in_file_phones.add(phone)

        # Year
        try:
            year = int(float(row.get('admission_year', 2025)))
        except (ValueError, TypeError):
            year = 2025

        # Fees
        try:
            fee = float(row.get('total_fee', matched_campus['default_fee'] if matched_campus else 50000))
            concession = float(row.get('concession', 0))
            if fee < 0 or concession < 0 or concession > fee:
                errors.append("Invalid fee or concession numbers.")
        except (ValueError, TypeError):
            errors.append("Fee or concession must be numerical.")
            fee = 50000
            concession = 0

        clean_data = {
            "row": row_num,
            "first_name": fname,
            "last_name": lname,
            "full_name": f"{fname} {lname}".strip(),
            "campus_name": matched_campus['name'] if matched_campus else campus_val,
            "campus_id": matched_campus['id'] if matched_campus else None,
            "campus_code": matched_campus['code'] if matched_campus else None,
            "course": course,
            "admission_year": year,
            "email": email,
            "phone": phone,
            "total_fee": fee,
            "concession": concession,
            "gender": str(row.get('gender', 'Other')).strip()
        }

        if errors:
            clean_data['errors'] = errors
            invalid_rows.append(clean_data)
        else:
            valid_rows.append(clean_data)

    conn.close()

    return jsonify({
        "success": True,
        "total_rows": len(df),
        "valid_count": len(valid_rows),
        "invalid_count": len(invalid_rows),
        "valid_rows": valid_rows[:50],  # preview up to 50
        "invalid_rows": invalid_rows[:50]
    })

@app.route('/api/import/commit', methods=['POST'])
def commit_spreadsheet():
    data = request.json or {}
    rows = data.get('rows', [])

    if not rows:
        return jsonify({"success": False, "error": "No valid rows to import."}), 400

    conn = database.get_db()
    cursor = conn.cursor()
    role = get_current_user_role()

    imported_count = 0
    assigned_ids = []

    for r in rows:
        campus_id = r.get('campus_id')
        cursor.execute("SELECT code, name FROM campuses WHERE id = ?", (campus_id,))
        camp = cursor.fetchone()
        if not camp:
            continue

        sid = database.get_next_student_id(camp['code'], conn)
        cursor.execute("""
            INSERT INTO students (student_id, first_name, last_name, full_name, email, phone, campus_id, course, admission_year, gender, status, total_fee, concession)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Active', ?, ?)
        """, (
            sid,
            r.get('first_name'),
            r.get('last_name'),
            r.get('full_name'),
            r.get('email'),
            r.get('phone'),
            campus_id,
            r.get('course'),
            r.get('admission_year', 2025),
            r.get('gender', 'Other'),
            r.get('total_fee', 50000),
            r.get('concession', 0)
        ))

        # Default attendance records
        for i in range(10):
            d = (date.today() - timedelta(days=i)).isoformat()
            cursor.execute("""
                INSERT OR IGNORE INTO attendance_records (student_id, campus_id, date, status, marked_by)
                VALUES (?, ?, ?, 'Present', 'Batch Import')
            """, (sid, campus_id, d))

        imported_count += 1
        assigned_ids.append(sid)

    database.log_audit(
        role,
        "DATA_IMPORT",
        "Multiple Campuses",
        f"Batch imported {imported_count} student records with automatically assigned IDs ({', '.join(assigned_ids[:5])}...).",
        conn
    )

    conn.commit()
    conn.close()

    return jsonify({
        "success": True,
        "message": f"Successfully imported {imported_count} students with verified IDs.",
        "imported_count": imported_count
    })

@app.route('/api/import/template', methods=['GET'])
def download_template():
    # Generate downloadable CSV template
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "first_name", "last_name", "campus", "course", "admission_year", 
        "email", "phone", "gender", "total_fee", "concession"
    ])
    # Add 6 exemplary rows, one for each official campus
    samples = [
        ["Rohan", "Gupta", "Medical Campus", "MBBS", 2025, "rohan.g@med.edu", "9811122201", "Male", 150000, 10000],
        ["Simran", "Kaur", "Polytechnic Campus", "Civil Engg", 2025, "simran.k@poly.edu", "9811122202", "Female", 45000, 5000],
        ["Deepak", "Sharma", "Diploma Campus", "Computer Engg", 2025, "deepak.s@dip.edu", "9811122203", "Male", 40000, 0],
        ["Ananya", "Rao", "Engineering Campus", "Computer Science", 2025, "ananya.r@eng.edu", "9811122204", "Female", 85000, 10000],
        ["Manoj", "Tiwari", "B.Tech Campus", "B.Tech AI & Data Science", 2025, "manoj.t@bt.edu", "9811122205", "Male", 95000, 15000],
        ["Kavita", "Jain", "PUC Campus", "PCMB (Science)", 2025, "kavita.j@puc.edu", "9811122206", "Female", 35000, 0],
    ]
    for s in samples:
        writer.writerow(s)

    response = make_response(output.getvalue())
    response.headers['Content-Disposition'] = 'attachment; filename=campus_sync_student_template.csv'
    response.headers['Content-type'] = 'text/csv'
    return response

# --- Export Reports Endpoint ---
@app.route('/api/export/<export_type>', methods=['GET'])
def export_csv_report(export_type):
    campus_id = request.args.get('campus_id', '')
    conn = database.get_db()
    cursor = conn.cursor()

    output = io.StringIO()
    writer = csv.writer(output)

    if export_type == 'students':
        writer.writerow(["Student ID", "Full Name", "Campus", "Course", "Admission Year", "Email", "Phone", "Status", "Total Fee (₹)", "Concession (₹)", "Paid (₹)", "Pending (₹)"])
        query = """
            SELECT s.*, c.name as campus_name,
                   COALESCE((SELECT SUM(amount) FROM fee_payments fp WHERE fp.student_id = s.student_id), 0) as paid
            FROM students s
            JOIN campuses c ON c.id = s.campus_id
            WHERE s.status != 'Archived'
        """
        params = []
        if campus_id.isdigit():
            query += " AND s.campus_id = ?"
            params.append(int(campus_id))
        query += " ORDER BY s.campus_id, s.student_id"
        cursor.execute(query, params)
        for r in cursor.fetchall():
            tot = float(r['total_fee'])
            cnc = float(r['concession'])
            pd = float(r['paid'])
            pnd = max(0.0, tot - cnc - pd)
            writer.writerow([r['student_id'], r['full_name'], r['campus_name'], r['course'], r['admission_year'], r['email'], r['phone'], r['status'], tot, cnc, pd, pnd])

    elif export_type == 'fees':
        writer.writerow(["Receipt No", "Student ID", "Student Name", "Campus", "Amount (₹)", "Payment Date", "Payment Mode", "Type", "Notes"])
        query = """
            SELECT fp.*, s.full_name, c.name as campus_name
            FROM fee_payments fp
            JOIN students s ON s.student_id = fp.student_id
            JOIN campuses c ON c.id = fp.campus_id
            WHERE 1=1
        """
        params = []
        if campus_id.isdigit():
            query += " AND fp.campus_id = ?"
            params.append(int(campus_id))
        query += " ORDER BY fp.id DESC"
        cursor.execute(query, params)
        for r in cursor.fetchall():
            writer.writerow([r['receipt_no'], r['student_id'], r['full_name'], r['campus_name'], r['amount'], r['payment_date'], r['payment_mode'], r['transaction_type'], r['notes']])

    elif export_type == 'attendance':
        writer.writerow(["Student ID", "Student Name", "Campus", "Course", "Total Classes", "Present Classes", "Attendance %", "Threshold Alert"])
        cursor.execute("SELECT value FROM app_settings WHERE key = 'attendance_threshold'")
        thr = float(cursor.fetchone()['value'])
        query = """
            SELECT s.student_id, s.full_name, s.course, c.name as campus_name,
                   COUNT(ar.id) as total_days,
                   SUM(CASE WHEN ar.status = 'Present' THEN 1 ELSE 0 END) as present_days
            FROM students s
            JOIN campuses c ON c.id = s.campus_id
            LEFT JOIN attendance_records ar ON ar.student_id = s.student_id
            WHERE s.status != 'Archived'
        """
        params = []
        if campus_id.isdigit():
            query += " AND s.campus_id = ?"
            params.append(int(campus_id))
        query += " GROUP BY s.student_id ORDER BY s.campus_id, s.student_id"
        cursor.execute(query, params)
        for r in cursor.fetchall():
            tot = r['total_days']
            prs = r['present_days'] or 0
            pct = round(prs * 100.0 / tot, 1) if tot > 0 else 100.0
            alert = "LOW ATTENDANCE" if pct < thr else "Normal"
            writer.writerow([r['student_id'], r['full_name'], r['campus_name'], r['course'], tot, prs, f"{pct}%", alert])

    elif export_type == 'hostel':
        writer.writerow(["Room No", "Campus", "Block", "Capacity", "Occupied Beds", "Available Beds", "Status", "Occupancy %"])
        query = """
            SELECT hr.*, c.name as campus_name
            FROM hostel_rooms hr
            JOIN campuses c ON c.id = hr.campus_id
            WHERE 1=1
        """
        params = []
        if campus_id.isdigit():
            query += " AND hr.campus_id = ?"
            params.append(int(campus_id))
        query += " ORDER BY hr.campus_id, hr.room_number"
        cursor.execute(query, params)
        for r in cursor.fetchall():
            cap = r['capacity']
            occ = r['occupied_beds']
            avail = max(0, cap - occ)
            pct = round(occ * 100.0 / cap, 1) if cap > 0 else 0
            writer.writerow([r['room_number'], r['campus_name'], r['block_name'], cap, occ, avail, r['status'], f"{pct}%"])

    conn.close()

    response = make_response(output.getvalue())
    response.headers['Content-Disposition'] = f'attachment; filename=campus_sync_{export_type}_report.csv'
    response.headers['Content-type'] = 'text/csv'
    return response

# --- Settings & Audit Logs ---
@app.route('/api/settings', methods=['GET', 'POST'])
def manage_settings():
    conn = database.get_db()
    cursor = conn.cursor()

    if request.method == 'POST':
        data = request.json or {}
        thr = data.get('attendance_threshold')
        inst_name = data.get('institution_name')

        if thr is not None:
            try:
                thr_val = float(thr)
                if 0 <= thr_val <= 100:
                    cursor.execute("UPDATE app_settings SET value = ? WHERE key = 'attendance_threshold'", (str(thr_val),))
            except ValueError:
                pass

        if inst_name:
            cursor.execute("UPDATE app_settings SET value = ? WHERE key = 'institution_name'", (inst_name.strip(),))

        role = get_current_user_role()
        database.log_audit(
            role,
            "SETTINGS_UPDATE",
            "All Campuses",
            f"Updated system settings (Attendance threshold: {thr}%).",
            conn
        )

        conn.commit()

    cursor.execute("SELECT * FROM app_settings")
    settings = {r['key']: r['value'] for r in cursor.fetchall()}
    conn.close()

    return jsonify({"success": True, "settings": settings})

@app.route('/api/audit-logs', methods=['GET'])
def get_audit_logs():
    campus = request.args.get('campus', '')
    action = request.args.get('action', '')

    conn = database.get_db()
    cursor = conn.cursor()

    query = "SELECT * FROM audit_logs WHERE 1=1"
    params = []
    if campus:
        query += " AND campus_name = ?"
        params.append(campus)
    if action:
        query += " AND action = ?"
        params.append(action)

    query += " ORDER BY id DESC LIMIT 100"
    cursor.execute(query, params)
    logs = [dict_from_row(r) for r in cursor.fetchall()]
    conn.close()

    return jsonify({"success": True, "logs": logs})

# --- Consolidated Multi-Campus Report ---
@app.route('/api/reports/consolidated', methods=['GET'])
def get_consolidated_report():
    conn = database.get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT 
            c.id, c.name, c.code, c.has_hostel,
            COUNT(DISTINCT s.id) as student_count,
            COALESCE(SUM(s.total_fee), 0) as total_assessed,
            COALESCE(SUM(s.concession), 0) as total_concession,
            COALESCE((
                SELECT SUM(fp.amount) 
                FROM fee_payments fp 
                WHERE fp.campus_id = c.id
            ), 0) as total_collected,
            COALESCE((
                SELECT SUM(hr.capacity) 
                FROM hostel_rooms hr 
                WHERE hr.campus_id = c.id
            ), 0) as hostel_capacity,
            COALESCE((
                SELECT SUM(hr.occupied_beds) 
                FROM hostel_rooms hr 
                WHERE hr.campus_id = c.id
            ), 0) as hostel_occupied,
            (
                SELECT ROUND(SUM(CASE WHEN ar.status = 'Present' THEN 1 ELSE 0 END) * 100.0 / COUNT(ar.id), 1)
                FROM attendance_records ar
                WHERE ar.campus_id = c.id
            ) as campus_avg_attendance
        FROM campuses c
        LEFT JOIN students s ON s.campus_id = c.id AND s.status != 'Archived'
        GROUP BY c.id
        ORDER BY c.id ASC
    """)
    rows = cursor.fetchall()

    campus_reports = []
    grand_students = 0
    grand_assessed = 0.0
    grand_concession = 0.0
    grand_collected = 0.0
    grand_pending = 0.0
    grand_hostel_cap = 0
    grand_hostel_occ = 0

    for r in rows:
        assessed = float(r['total_assessed'])
        concession = float(r['total_concession'])
        collected = float(r['total_collected'])
        pending = max(0.0, assessed - concession - collected)
        cap = r['hostel_capacity']
        occ = r['hostel_occupied']

        campus_reports.append({
            "id": r['id'],
            "name": r['name'],
            "code": r['code'],
            "has_hostel": bool(r['has_hostel']),
            "students": r['student_count'],
            "assessed": assessed,
            "concession": concession,
            "collected": collected,
            "pending": pending,
            "collection_rate": round((collected / (assessed - concession) * 100), 1) if (assessed - concession) > 0 else 0,
            "hostel_capacity": cap,
            "hostel_occupied": occ,
            "avg_attendance": r['campus_avg_attendance'] or 100.0
        })

        grand_students += r['student_count']
        grand_assessed += assessed
        grand_concession += concession
        grand_collected += collected
        grand_pending += pending
        grand_hostel_cap += cap
        grand_hostel_occ += occ

    conn.close()

    return jsonify({
        "success": True,
        "campuses": campus_reports,
        "totals": {
            "students": grand_students,
            "assessed": grand_assessed,
            "concession": grand_concession,
            "collected": grand_collected,
            "pending": grand_pending,
            "collection_rate": round((grand_collected / (grand_assessed - grand_concession) * 100), 1) if (grand_assessed - grand_concession) > 0 else 0,
            "hostel_capacity": grand_hostel_cap,
            "hostel_occupied": grand_hostel_occ,
            "hostel_occupancy_pct": round(grand_hostel_occ * 100.0 / grand_hostel_cap, 1) if grand_hostel_cap > 0 else 0
        }
    })

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000, debug=False)
