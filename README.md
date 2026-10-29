# Campus Sync — Smart Multi-Campus Management System

> **“One Institution, Six Campuses, Forty Spreadsheets — Synchronized into One Intelligent System.”**

Campus Sync is a complete, production-ready, three-tier web application built with **Python Flask**, **vanilla HTML5/CSS3/JavaScript**, **SQLite**, and **Pandas**. It replaces scattered spreadsheet workflows across an educational group's six campuses with a centralized, unified platform while preserving campus-specific rules and autonomy.

---

## 🏛 The Six Official Campuses

Every campus possesses dedicated student rosters, fee structures, attendance ledgers, and residential facilities:

| # | Campus Name | Code Prefix | Example Student ID | Default Annual Fee | Residential Hostel |
|---|---|---|---|---|---|
| 1 | **Medical Campus** | `MED` | `MED001`, `MED002` | ₹1,50,000 | Yes (Dhanvantari & Charaka Blocks) |
| 2 | **Polytechnic Campus** | `POLY` | `POLY001`, `POLY002` | ₹45,000 | Yes (Visvesvaraya Block) |
| 3 | **Diploma Campus** | `DIP` | `DIP001`, `DIP002` | ₹40,000 | Yes (Aryabhata Block) |
| 4 | **Engineering Campus** | `ENG` | `ENG001`, `ENG002` | ₹85,000 | Yes (Ramanujan Block) |
| 5 | **B.Tech Campus** | `BT` | `BT001`, `BT002` | ₹95,000 | Yes (Kalam Block) |
| 6 | **PUC Campus** | `PUC` | `PUC001`, `PUC002` | ₹35,000 | Non-Residential (No Hostel) |

---

## 🚀 Key Modules & Capabilities

1. **Centralized Multi-Campus Dashboard**:
   - Live KPI cards calculating total students, assessed fees, concessions, fee recovery rate, outstanding balance, attendance average, low-attendance alerts, and hostel occupancy.
   - Interactive data visualizations powered by Chart.js (Donut chart for student distribution, grouped bar chart for fee recovery vs outstanding balance, and campus comparison charts).
   - Global Campus Selector: Filter any dashboard, report, or student roster to a specific campus, or choose **"All Six Campuses (Consolidated View)"** for consolidated oversight.

2. **Student & Admissions Management**:
   - Atomic sequence ID generation (`MED001`, `POLY001`, etc.) backed by SQLite sequence registers. IDs are never reused even if student records are archived.
   - Idempotent demo data supports 14,000 active student records across the six campuses; the roster is paginated and searchable.
   - Real-time duplicate detection on email, phone number, and student name with duplicate warning alerts.
   - Rich student profile modal displaying overview, payment ledger, attendance log, hostel room allotment, campus transfer history, and course examination schedules.

3. **Admissions & Campus Relocation (Transfer)**:
   - Preserves permanent student identity, original sequence ID, and payment history during inter-campus transfers.
   - Automatically reallocates or releases residential hostel accommodations based on destination campus policies.
   - Comprehensive transfer history logs with administrative reasoning.

4. **Fee Management & Financial Ledgers**:
   - Indian Rupee (`₹`) accounting: `Pending Amount = Total Fee - Concession - Amount Paid`.
   - Installment payments with automatic receipt numbers (`REC-YYYY-XXXX`).
   - Tamper-evident payment reversals: Reversals create offsetting negative transactions (`REV-YYYY-XXXX`) referencing the original receipt without hard-deleting historical records.
   - Filtering for Fully Paid, Partially Paid, and Pending balances.

5. **Attendance Tracking & Early-Warning Alerts**:
   - Daily roll-call logging (Present / Absent) with date pickers.
   - Dynamic calculation of cumulative student attendance percentages from actual database logs.
   - Configurable institutional attendance threshold (default: 75%).
   - Automatic visual warning badges and a dedicated **"Students Requiring Attention"** dashboard widget.

6. **Hostel & Residential Room Allocation**:
   - Room registry tracking block names, room numbers, bed capacity, and occupied beds.
   - Enforces room capacity limits and prevents duplicate active room allotments.
   - Non-residential policy enforcement for PUC Campus.
   - One-click bed release workflow.

7. **Bulk Excel & CSV Import Engine**:
   - Ingestion powered by Python Pandas and openpyxl supporting both `.csv` and `.xlsx` files.
   - Two-stage import workflow: **Preview & Validate** -> **Commit to SQLite**.
   - Row-level validation checking required fields, campus naming against the 6 official names, email/phone format, and database duplicate checks.
   - Downloadable CSV sample template with pre-filled exemplary records for all 6 campuses.

8. **Institutional Reports & Data Export**:
   - Consolidated 6-campus master matrix with totals and grand totals.
   - Filtered CSV exports for student rosters, payment ledgers, attendance sheets, and hostel logs.

9. **Role-Based Access & Auditability**:
   - Role switching between **Campus Supervisor** (multi-campus oversight, consolidated analytics) and **System Administrator** (full modification rights).
   - Immutable audit trail recording every admission, transfer, fee transaction, reversal, and settings change with timestamps and operator roles.

10. **Scholarship Management**:
    - Add, search, filter, and update student scholarship applications, eligibility, amounts, and application/approval statuses.
    - Summary counts display total applications, approved and pending applications, and scholarship amounts.

11. **Examination Management**:
    - Schedule, search, filter, and update campus/course examinations, subjects, codes, dates, times, types, and statuses.
    - Upcoming and completed exam summaries and student-specific course schedules.

---

## 🛠 Technology Stack

- **Frontend**: Semantic HTML5, Custom CSS3 Design System, Vanilla JavaScript (Fetch API, SPA navigation, Modal system, Toast engine, Chart.js 4). *Zero heavy frontend frameworks (no React, Node, npm, Bootstrap, or Tailwind).*
- **Backend**: Python 3.14 / Flask (RESTful endpoints, parameterized SQL queries, clean route separation).
- **Database**: SQLite3 (`campus_sync.db`) with primary keys, foreign key constraints, indexes, sequential counter registers, scholarship applications, and examinations. Startup migrations preserve existing data and seed missing demo records.
- **Data Processing**: Pandas and openpyxl for spreadsheet analysis and validation.

---

## 📂 Project Structure

```text
CampusSync/
├── app.py                  # Core Flask application and REST endpoints
├── database.py             # SQLite connection, atomic ID sequences, and seed data
├── schema.sql              # Database schema definitions and indexes
├── requirements.txt        # Python dependency manifest (Flask, pandas, openpyxl)
├── test_suite.py           # Comprehensive 9-point integration test suite
├── campus_sync.db          # Auto-generated SQLite database
├── templates/
│   └── index.html          # Single-Page Application interface
├── static/
│   ├── css/
│   │   └── style.css       # Premium custom CSS design system
│   └── js/
│       └── script.js       # Vanilla JavaScript client logic and API integration
├── uploads/                # Temporary spreadsheet processing folder
└── README.md               # System documentation
```

---

## ⚡ How to Run the Application Locally

### 1. Install Dependencies
Open your PowerShell or Command Prompt terminal in the `CampusSync` directory and install the required dependencies:

```powershell
pip install -r requirements.txt
```

*(Or specify the explicit Python executable path if you have multiple versions):*
```powershell
& "C:\Users\Admin\AppData\Local\Programs\Python\Python314\python.exe" -m pip install -r requirements.txt
```

### 2. Run the Flask Web Server
Start the centralized application server:

```powershell
python app.py
```

*(Or using the Python 3.14 path):*
```powershell
& "C:\Users\Admin\AppData\Local\Programs\Python\Python314\python.exe" app.py
```

### 3. Open in Browser
Open your web browser and navigate to:
```
http://127.0.0.1:5000/
```

### 4. Run the Automated Test Suite (Optional)
To verify all 9 core subsystems (ID sequence generation, duplicate detection, fee payments, reversals, campus transfers, hostel allocation, CSV templates, pandas import validation, and consolidated reports):

```powershell
python test_suite.py
```
