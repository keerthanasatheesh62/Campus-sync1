-- Campus Sync Database Schema

CREATE TABLE IF NOT EXISTS campuses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    code TEXT UNIQUE NOT NULL,
    has_hostel INTEGER DEFAULT 1,
    default_fee REAL DEFAULT 65000,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS campus_sequences (
    campus_code TEXT PRIMARY KEY,
    last_number INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS students (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id TEXT UNIQUE NOT NULL,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    full_name TEXT NOT NULL,
    email TEXT NOT NULL,
    phone TEXT NOT NULL,
    campus_id INTEGER NOT NULL REFERENCES campuses(id),
    course TEXT NOT NULL,
    admission_year INTEGER NOT NULL,
    gender TEXT DEFAULT 'Other',
    status TEXT DEFAULT 'Active',
    total_fee REAL NOT NULL DEFAULT 0,
    concession REAL NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS student_transfers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id TEXT NOT NULL,
    from_campus_id INTEGER NOT NULL REFERENCES campuses(id),
    to_campus_id INTEGER NOT NULL REFERENCES campuses(id),
    transfer_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    reason TEXT,
    transferred_by TEXT DEFAULT 'Administrator'
);

CREATE TABLE IF NOT EXISTS fee_payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    receipt_no TEXT UNIQUE NOT NULL,
    student_id TEXT NOT NULL REFERENCES students(student_id),
    campus_id INTEGER NOT NULL REFERENCES campuses(id),
    amount REAL NOT NULL,
    payment_date DATE NOT NULL,
    payment_mode TEXT NOT NULL,
    transaction_type TEXT DEFAULT 'Payment',
    reference_receipt_no TEXT,
    notes TEXT,
    created_by TEXT DEFAULT 'Administrator',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS attendance_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id TEXT NOT NULL REFERENCES students(student_id),
    campus_id INTEGER NOT NULL REFERENCES campuses(id),
    date DATE NOT NULL,
    status TEXT NOT NULL,
    marked_by TEXT DEFAULT 'Faculty',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(student_id, date)
);

CREATE TABLE IF NOT EXISTS hostel_rooms (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    room_number TEXT NOT NULL,
    campus_id INTEGER NOT NULL REFERENCES campuses(id),
    block_name TEXT DEFAULT 'Main Block',
    capacity INTEGER NOT NULL DEFAULT 3,
    occupied_beds INTEGER NOT NULL DEFAULT 0,
    status TEXT DEFAULT 'Available',
    UNIQUE(campus_id, room_number)
);

CREATE TABLE IF NOT EXISTS hostel_allocations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    room_id INTEGER NOT NULL REFERENCES hostel_rooms(id),
    student_id TEXT NOT NULL REFERENCES students(student_id),
    campus_id INTEGER NOT NULL REFERENCES campuses(id),
    bed_number INTEGER,
    allocated_date DATE NOT NULL,
    released_date DATE,
    status TEXT DEFAULT 'Active',
    remarks TEXT
);

CREATE TABLE IF NOT EXISTS app_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    description TEXT
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    user_role TEXT NOT NULL,
    action TEXT NOT NULL,
    campus_name TEXT,
    details TEXT NOT NULL,
    ip_address TEXT DEFAULT '127.0.0.1'
);

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    full_name TEXT NOT NULL,
    role TEXT NOT NULL,
    campus_access TEXT DEFAULT 'ALL'
);

CREATE TABLE IF NOT EXISTS scholarships (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scholarship_name TEXT NOT NULL,
    student_id TEXT NOT NULL REFERENCES students(student_id),
    campus_id INTEGER NOT NULL REFERENCES campuses(id),
    amount REAL NOT NULL DEFAULT 0,
    eligibility TEXT NOT NULL,
    application_status TEXT NOT NULL DEFAULT 'Pending',
    approval_status TEXT NOT NULL DEFAULT 'Pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(student_id, scholarship_name)
);

CREATE TABLE IF NOT EXISTS examinations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campus_id INTEGER NOT NULL REFERENCES campuses(id),
    course TEXT NOT NULL,
    subject_name TEXT NOT NULL,
    subject_code TEXT NOT NULL,
    exam_date DATE NOT NULL,
    start_time TIME NOT NULL,
    end_time TIME NOT NULL,
    exam_type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'Scheduled',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(campus_id, course, subject_code, exam_date, start_time)
);

CREATE INDEX IF NOT EXISTS idx_students_campus ON students(campus_id);
CREATE INDEX IF NOT EXISTS idx_students_status ON students(status);
CREATE INDEX IF NOT EXISTS idx_fee_payments_student ON fee_payments(student_id);
CREATE INDEX IF NOT EXISTS idx_attendance_student ON attendance_records(student_id);
CREATE INDEX IF NOT EXISTS idx_attendance_date ON attendance_records(date);
CREATE INDEX IF NOT EXISTS idx_hostel_alloc_student ON hostel_allocations(student_id);
CREATE INDEX IF NOT EXISTS idx_scholarships_campus ON scholarships(campus_id);
CREATE INDEX IF NOT EXISTS idx_scholarships_student ON scholarships(student_id);
CREATE INDEX IF NOT EXISTS idx_scholarships_status ON scholarships(approval_status, application_status);
CREATE INDEX IF NOT EXISTS idx_examinations_campus_date ON examinations(campus_id, exam_date);
CREATE INDEX IF NOT EXISTS idx_examinations_course ON examinations(course);
