import sys
import io
import os
import json

from app import app
client = app.test_client()

import time
ts = int(time.time())
test_email = f'test.student.{ts}@bt.institution.edu'
test_phone = f'98{ts % 100000000:08d}'

print('--- TEST 1: Student Creation and Sequence ID ---')
res = client.post('/api/students', json={
    'first_name': 'Adarsh', 'last_name': 'Verma',
    'campus_id': 5, 'course': 'B.Tech Robotics',
    'admission_year': 2025, 'email': test_email,
    'phone': test_phone, 'gender': 'Male',
    'total_fee': 95000, 'concession': 10000
})
print('Create student res:', res.status_code, res.json)
assert res.status_code == 200
sid = res.json['student_id']
assert sid.startswith('BT'), f"Expected ID starting with BT, got {sid}"
print(f"Generated sequential ID: {sid}")

print('\n--- TEST 2: Duplicate Detection ---')
res_dup = client.post('/api/students', json={
    'first_name': 'Adarsh', 'last_name': 'Verma',
    'campus_id': 5, 'course': 'B.Tech Robotics',
    'admission_year': 2025, 'email': test_email,
    'phone': test_phone, 'gender': 'Male'
})
print('Duplicate check:', res_dup.status_code, res_dup.json.get('error'))
assert res_dup.status_code == 409
assert res_dup.json.get('is_duplicate_warning') is True

print('\n--- TEST 3: Fee Payment ---')
res_pay = client.post('/api/fees/payments', json={
    'student_id': sid, 'amount': 45000, 'payment_mode': 'UPI', 'notes': 'Semester 1 fee'
})
print('Payment res:', res_pay.status_code, res_pay.json.get('receipt_no'))
assert res_pay.status_code == 200
rec_no = res_pay.json['receipt_no']
assert rec_no.startswith('REC-'), f"Invalid receipt {rec_no}"

print('\n--- TEST 4: Payment Reversal ---')
res_rev = client.post('/api/fees/reversal', json={
    'receipt_no': rec_no, 'reason': 'Audit reconciliation correction'
})
print('Reversal res:', res_rev.status_code, res_rev.json.get('reversal_receipt'))
assert res_rev.status_code == 200
assert res_rev.json['reversal_receipt'].startswith('REV-')

print('\n--- TEST 5: Student Campus Transfer ---')
res_trans = client.post('/api/students/transfer', json={
    'student_id': sid, 'to_campus_id': 4, 'reason': 'Program upgrade to Engineering Campus'
})
print('Transfer res:', res_trans.status_code, res_trans.json)
assert res_trans.status_code == 200

# Verify student profile shows new campus while preserving ID and transfer history
res_prof = client.get(f'/api/students/{sid}')
assert res_prof.status_code == 200
profile = res_prof.json
assert profile['student']['campus_name'] == 'Engineering Campus'
assert len(profile['transfers']) >= 1
print(f"Student transfer verified. Current campus: {profile['student']['campus_name']}, transfers: {len(profile['transfers'])}")

print('\n--- TEST 6: Hostel Allocation ---')
res_rooms = client.get('/api/hostel/rooms?campus_id=4')
rooms = res_rooms.json['rooms']
vacant_room = next(r for r in rooms if r['occupied_beds'] < r['capacity'])
res_alloc = client.post('/api/hostel/allocate', json={
    'student_id': sid, 'room_id': vacant_room['id'], 'remarks': 'Semester residential room allotment'
})
print('Hostel alloc res:', res_alloc.status_code, res_alloc.json)
assert res_alloc.status_code == 200

# Try duplicate active allocation for same student
res_alloc_dup = client.post('/api/hostel/allocate', json={
    'student_id': sid, 'room_id': vacant_room['id']
})
assert res_alloc_dup.status_code == 400
print("Duplicate hostel allocation correctly blocked.")

print('\n--- TEST 7: CSV Template Download ---')
res_tpl = client.get('/api/import/template')
print('Template download status:', res_tpl.status_code, 'bytes:', len(res_tpl.data))
assert res_tpl.status_code == 200
assert b'first_name,last_name,campus' in res_tpl.data

print('\n--- TEST 8: CSV Import Preview and Commit ---')
csv_content = b"""first_name,last_name,campus,course,admission_year,email,phone,gender,total_fee,concession
Tanya,Bose,Engineering Campus,Computer Science,2025,tanya.bose@eng.edu,9811009988,Female,85000,5000
Invalid,Student,Invalid Campus,Test Course,2025,invalid@test.com,9800000000,Other,50000,0
"""
data = {'file': (io.BytesIO(csv_content), 'test_students.csv')}
res_prev = client.post('/api/import/preview', data=data, content_type='multipart/form-data')
print('Import preview:', res_prev.status_code, 'Valid:', res_prev.json['valid_count'], 'Invalid:', res_prev.json['invalid_count'])
assert res_prev.json['valid_count'] == 1
assert res_prev.json['invalid_count'] == 1
assert 'Invalid Campus' in res_prev.json['invalid_rows'][0]['errors'][0]

res_commit = client.post('/api/import/commit', json={'rows': res_prev.json['valid_rows']})
print('Import commit res:', res_commit.status_code, res_commit.json)
assert res_commit.status_code == 200
assert res_commit.json['imported_count'] == 1

print('\n--- TEST 9: Consolidated Reports Verification ---')
res_rep = client.get('/api/reports/consolidated')
print('Consolidated report status:', res_rep.status_code)
assert res_rep.status_code == 200
campuses = res_rep.json['campuses']
assert len(campuses) == 6
for c in campuses:
    print(f"Campus: {c['name']} ({c['code']}) - Students: {c['students']}, Assessed: Rs. {c['assessed']}, Collected: Rs. {c['collected']}")

print('\n========================================')
print('SUCCESS! ALL 9 SYSTEM TESTS PASSED!')
print('========================================')
