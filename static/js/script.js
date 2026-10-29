/**
 * Campus Sync — Smart Multi-Campus Management System
 * Core Client-Side Logic (Vanilla JavaScript)
 */

document.addEventListener('DOMContentLoaded', () => {
    // Application State
    const state = {
        activePage: 'dashboard',
        selectedCampusId: 'ALL',
        currentRole: 'Campus Supervisor',
        campuses: [],
        settings: {
            attendance_threshold: 75,
            institution_name: 'Campus Sync — Central Multi-Campus Institute'
        },
        charts: {},
        currentStudent: null,
        studentPage: 1,
        scholarships: [],
        examinations: []
    };

    // Campus Course Map for the 6 Official Campuses
    const CAMPUS_COURSES = {
        "1": ["MBBS", "BDS", "B.Pharm", "B.Sc Nursing", "M.D. General Medicine"],
        "2": ["Mechanical Engg", "Civil Engg", "Electrical Engg", "Automobile Engg", "Tool & Die Making"],
        "3": ["Computer Engg", "Electronics & Comm", "Mechatronics", "Information Tech"],
        "4": ["Computer Science", "Information Science", "Electronics & Comm", "Civil Engg", "Mechanical Engg"],
        "5": ["B.Tech AI & Data Science", "B.Tech CSE (Cyber Sec)", "B.Tech Robotics", "B.Tech IT"],
        "6": ["PCMB (Science)", "PCMC (Science)", "Commerce with Maths", "Arts & Humanities"]
    };

    // --- DOM Elements ---
    const globalCampusSelect = document.getElementById('globalCampusSelect');
    const sidebarCampusPills = document.getElementById('sidebarCampusPills');
    const sidebarActiveCampusName = document.getElementById('sidebarActiveCampusName');
    const currentCampusBadge = document.getElementById('currentCampusBadge');
    const currentPageTitle = document.getElementById('currentPageTitle');
    const currentPageSubtitle = document.getElementById('currentPageSubtitle');
    const roleSwitchBtn = document.getElementById('roleSwitchBtn');
    const userNameLabel = document.getElementById('userNameLabel');
    const userRoleTag = document.getElementById('userRoleTag');
    const userAvatar = document.getElementById('userAvatar');
    const currentActiveRolePill = document.getElementById('currentActiveRolePill');
    const toastContainer = document.getElementById('toastContainer');

    // ==========================================
    // INITIALIZATION
    // ==========================================
    async function init() {
        setupNavigation();
        setupGlobalCampusSelector();
        setupRoleSwitcher();
        setupModals();
        setupImportFeature();
        setupAttendanceFeature();
        setupSettingsFeature();
        setupSearchFeature();
        setupManagementFeatures();

        await loadCampuses();
        await loadSettings();
        await refreshActiveView();
    }

    // ==========================================
    // API HELPERS
    // ==========================================
    async function apiFetch(url, options = {}) {
        options.headers = options.headers || {};
        options.headers['X-User-Role'] = state.currentRole;
        try {
            const res = await fetch(url, options);
            const data = await res.json();
            return data;
        } catch (err) {
            console.error('API Error:', err);
            showToast('Network error while connecting to server.', 'error');
            return { success: false, error: err.message };
        }
    }

    function formatCurrency(amount) {
        return new Intl.NumberFormat('en-IN', {
            style: 'currency',
            currency: 'INR',
            maximumFractionDigits: 0
        }).format(amount || 0);
    }

    function showToast(message, type = 'info') {
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        const icons = {
            success: 'fa-circle-check text-success',
            error: 'fa-circle-xmark text-danger',
            warning: 'fa-triangle-exclamation text-warning',
            info: 'fa-circle-info text-primary'
        };
        toast.innerHTML = `<i class="fa-solid ${icons[type] || icons.info}"></i> <span>${message}</span>`;
        toastContainer.appendChild(toast);
        setTimeout(() => {
            toast.style.opacity = '0';
            setTimeout(() => toast.remove(), 300);
        }, 4000);
    }

    function escapeHtml(value) {
        return String(value ?? '').replace(/[&<>"']/g, char => ({
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#39;'
        })[char]);
    }

    // ==========================================
    // NAVIGATION & ROUTING
    // ==========================================
    function setupNavigation() {
        const navLinks = document.querySelectorAll('.sidebar-nav .nav-item');
        navLinks.forEach(link => {
            link.addEventListener('click', (e) => {
                e.preventDefault();
                const targetPage = link.getAttribute('data-page');
                navigateTo(targetPage);
            });
        });

        // Mobile sidebar toggle
        const mobileMenuBtn = document.getElementById('mobileMenuBtn');
        const sidebar = document.getElementById('sidebar');
        const sidebarToggle = document.getElementById('sidebarToggle');
        if (mobileMenuBtn) {
            mobileMenuBtn.addEventListener('click', () => sidebar.classList.toggle('open'));
        }
        if (sidebarToggle) {
            sidebarToggle.addEventListener('click', () => sidebar.classList.remove('open'));
        }

        // Refresh Data Button
        document.getElementById('refreshDataBtn')?.addEventListener('click', () => {
            showToast('Refreshed data from SQLite database.', 'success');
            refreshActiveView();
        });

        // Quick Admission Button
        document.getElementById('quickAdmissionBtn')?.addEventListener('click', () => {
            openAdmissionModal();
        });

        // View Detailed Reports Button
        document.getElementById('viewDetailedReportsBtn')?.addEventListener('click', () => {
            navigateTo('reports');
        });
    }

    function navigateTo(pageId) {
        state.activePage = pageId;

        // Update active nav class
        document.querySelectorAll('.sidebar-nav .nav-item').forEach(link => {
            if (link.getAttribute('data-page') === pageId) {
                link.classList.add('active');
            } else {
                link.classList.remove('active');
            }
        });

        // Update page view containers
        document.querySelectorAll('.page-view').forEach(view => {
            view.classList.remove('active');
        });
        const targetView = document.getElementById(`page-${pageId}`);
        if (targetView) targetView.classList.add('active');

        // Close mobile sidebar if open
        document.getElementById('sidebar')?.classList.remove('open');

        // Update banner text
        const titles = {
            dashboard: { title: 'Central Dashboard', sub: 'Real-time institutional metrics, student distribution, fee recovery, and attendance monitoring.' },
            students: { title: 'Students & Admissions', sub: 'Manage verified student records, course enrollments, identity tracking, and campus relocations.' },
            scholarships: { title: 'Scholarship Management', sub: 'Manage student scholarship eligibility, application progress, and approval status.' },
            examinations: { title: 'Examination Management', sub: 'Schedule campus examinations and view subject dates for each student course.' },
            fees: { title: 'Fee Management', sub: 'Campus fee ledgers, concession allocations, installment receipts, and payment reversals.' },
            attendance: { title: 'Attendance & Alerts', sub: 'Daily roll-call logging, threshold analytics, and early-warning alerts for low attendance.' },
            hostel: { title: 'Hostel Allocation', sub: 'Campus residential block registry, bed allocations, vacancy monitoring, and room releases.' },
            import: { title: 'Excel & CSV Import', sub: 'Bulk spreadsheet ingestion powered by Pandas with automatic validation and sequence ID assignment.' },
            reports: { title: 'Consolidated Reports', sub: 'Consolidated six-campus master metrics, financial balances, and automated CSV export.' },
            settings: { title: 'Settings & Audit Trail', sub: 'System attendance thresholds, institution parameters, and tamper-evident audit logs.' }
        };

        if (titles[pageId]) {
            currentPageTitle.textContent = titles[pageId].title;
            currentPageSubtitle.textContent = titles[pageId].sub;
        }

        refreshActiveView();
    }

    async function refreshActiveView() {
        updateCampusContextBadges();
        switch (state.activePage) {
            case 'dashboard':
                await loadDashboardData();
                break;
            case 'students':
                await loadStudentsData();
                break;
            case 'scholarships':
                await loadScholarships();
                break;
            case 'examinations':
                await loadExaminations();
                break;
            case 'fees':
                await loadFeesData();
                break;
            case 'attendance':
                await loadAttendanceData();
                break;
            case 'hostel':
                await loadHostelData();
                break;
            case 'reports':
                await loadReportsData();
                break;
            case 'settings':
                await loadAuditLogs();
                break;
        }
    }

    // ==========================================
    // CAMPUS SELECTOR
    // ==========================================
    async function loadCampuses() {
        const res = await apiFetch('/api/campuses');
        if (res.success) {
            state.campuses = res.campuses;
            renderSidebarCampusPills();
            populateCampusDropdowns();
        }
    }

    function renderSidebarCampusPills() {
        sidebarCampusPills.innerHTML = '';

        // "All Campuses" pill
        const allLi = document.createElement('li');
        allLi.innerHTML = `
            <button class="campus-pill-btn ${state.selectedCampusId === 'ALL' ? 'active' : ''}" data-campus="ALL">
                <span>All 6 Campuses</span>
                <span class="campus-pill-badge">Total</span>
            </button>
        `;
        sidebarCampusPills.appendChild(allLi);

        state.campuses.forEach(c => {
            const li = document.createElement('li');
            li.innerHTML = `
                <button class="campus-pill-btn ${state.selectedCampusId == c.id ? 'active' : ''}" data-campus="${c.id}">
                    <span>${c.name}</span>
                    <span class="campus-pill-badge">${c.code}</span>
                </button>
            `;
            sidebarCampusPills.appendChild(li);
        });

        // Add click listener
        sidebarCampusPills.querySelectorAll('.campus-pill-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const cid = btn.getAttribute('data-campus');
                setCampusScope(cid);
            });
        });
    }

    function setupGlobalCampusSelector() {
        globalCampusSelect.addEventListener('change', (e) => {
            setCampusScope(e.target.value);
        });
    }

    function setCampusScope(campusId) {
        state.selectedCampusId = campusId;
        globalCampusSelect.value = campusId;
        renderSidebarCampusPills();
        updateCampusContextBadges();
        refreshActiveView();
    }

    function updateCampusContextBadges() {
        let name = 'All Campuses (Consolidated)';
        if (state.selectedCampusId !== 'ALL') {
            const found = state.campuses.find(c => c.id == state.selectedCampusId);
            if (found) name = found.name;
        }
        sidebarActiveCampusName.textContent = name;
        currentCampusBadge.textContent = name;
    }

    function populateCampusDropdowns() {
        const admSelect = document.getElementById('admCampusSelect');
        if (admSelect) {
            admSelect.addEventListener('change', (e) => {
                populateCourseDropdown(e.target.value);
            });
        }
    }

    function populateCourseDropdown(campusId) {
        const courseSelect = document.getElementById('admCourseSelect');
        if (!courseSelect) return;
        courseSelect.innerHTML = '<option value="">-- Select Course --</option>';

        const courses = CAMPUS_COURSES[campusId] || [];
        courses.forEach(crs => {
            const opt = document.createElement('option');
            opt.value = crs;
            opt.textContent = crs;
            courseSelect.appendChild(opt);
        });

        // Set default fee if available
        const campus = state.campuses.find(c => c.id == campusId);
        if (campus) {
            document.getElementById('admTotalFee').value = campus.default_fee;
        }
    }

    // ==========================================
    // ROLE SWITCHER
    // ==========================================
    function setupRoleSwitcher() {
        roleSwitchBtn.addEventListener('click', () => {
            if (state.currentRole === 'Campus Supervisor') {
                state.currentRole = 'Administrator';
                userNameLabel.textContent = 'System Administrator';
                userRoleTag.textContent = 'Admin Mode';
                userAvatar.textContent = 'SA';
                userAvatar.style.background = 'linear-gradient(135deg, #4f46e5, #7c3aed)';
                if (currentActiveRolePill) currentActiveRolePill.textContent = 'Administrator';
                showToast('Switched operator profile to Administrator (Full Rights).', 'info');
            } else {
                state.currentRole = 'Campus Supervisor';
                userNameLabel.textContent = 'Campus Supervisor';
                userRoleTag.textContent = 'Supervisor Mode';
                userAvatar.textContent = 'CS';
                userAvatar.style.background = 'linear-gradient(135deg, #0d9488, #059669)';
                if (currentActiveRolePill) currentActiveRolePill.textContent = 'Campus Supervisor';
                showToast('Switched operator profile to Campus Supervisor (Multi-Campus Oversight).', 'info');
            }
            refreshActiveView();
        });
    }

    // ==========================================
    // 1. DASHBOARD MODULE
    // ==========================================
    async function loadDashboardData() {
        const campusParam = state.selectedCampusId !== 'ALL' ? `?campus_id=${state.selectedCampusId}` : '';
        const data = await apiFetch(`/api/dashboard/stats${campusParam}`);
        if (!data.success) return;

        const m = data.metrics;
        document.getElementById('kpiTotalStudents').textContent = m.total_students.toLocaleString();
        document.getElementById('kpiTotalAssessed').textContent = formatCurrency(m.total_assessed);
        document.getElementById('kpiTotalConcession').textContent = formatCurrency(m.total_concession);
        document.getElementById('kpiTotalCollected').textContent = formatCurrency(m.total_collected);
        document.getElementById('kpiTotalOutstanding').textContent = formatCurrency(m.total_outstanding);

        const netPayable = m.total_assessed - m.total_concession;
        const colRate = netPayable > 0 ? Math.round((m.total_collected / netPayable) * 100) : 0;
        document.getElementById('kpiCollectionRate').innerHTML = `<i class="fa-solid fa-percent"></i> ${colRate}%`;

        document.getElementById('kpiAvgAttendance').textContent = `${m.avg_attendance}%`;
        document.getElementById('kpiLowAttCountBadge').innerHTML = `<i class="fa-solid fa-user-xmark"></i> ${m.low_attendance_count} Below ${m.attendance_threshold}%`;

        document.getElementById('kpiHostelOccupancy').textContent = `${m.hostel_occupancy_pct}%`;
        document.getElementById('kpiHostelBedsMeta').textContent = `${m.hostel_occupied} / ${m.hostel_capacity} Beds`;

        // Render Charts
        renderStudentDistributionChart(data.campus_breakdown);
        renderFeeRecoveryChart(data.campus_breakdown);

        // Render Campus Matrix Table
        renderCampusMatrixTable(data.campus_breakdown);

        // Render Attention Needed List
        renderAttentionList(data.attention_list);

        // Render Recent Audit Logs
        renderDashboardAudit(data.recent_activities);
    }

    function renderStudentDistributionChart(campusBreakdown) {
        const ctx = document.getElementById('chartStudentDistribution');
        if (!ctx) return;

        if (state.charts.studentDist) {
            state.charts.studentDist.destroy();
        }

        const labels = campusBreakdown.map(c => c.name);
        const counts = campusBreakdown.map(c => c.students);

        state.charts.studentDist = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: labels,
                datasets: [{
                    data: counts,
                    backgroundColor: [
                        '#4f46e5', // Medical
                        '#06b6d4', // Polytechnic
                        '#8b5cf6', // Diploma
                        '#10b981', // Engineering
                        '#f59e0b', // B.Tech
                        '#ec4899'  // PUC
                    ],
                    borderWidth: 2,
                    borderColor: '#ffffff'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'right',
                        labels: { boxWidth: 12, font: { family: 'Plus Jakarta Sans', size: 11 } }
                    }
                },
                cutout: '65%'
            }
        });
    }

    function renderFeeRecoveryChart(campusBreakdown) {
        const ctx = document.getElementById('chartFeeRecovery');
        if (!ctx) return;

        if (state.charts.feeRecovery) {
            state.charts.feeRecovery.destroy();
        }

        const labels = campusBreakdown.map(c => c.code);
        const collected = campusBreakdown.map(c => c.collected);
        const pending = campusBreakdown.map(c => c.pending);

        state.charts.feeRecovery = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [
                    {
                        label: 'Collected (₹)',
                        data: collected,
                        backgroundColor: '#10b981',
                        borderRadius: 6
                    },
                    {
                        label: 'Pending (₹)',
                        data: pending,
                        backgroundColor: '#f43f5e',
                        borderRadius: 6
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    x: { grid: { display: false } },
                    y: {
                        ticks: {
                            callback: value => '₹' + (value >= 1000 ? (value / 1000) + 'k' : value)
                        }
                    }
                },
                plugins: {
                    legend: { position: 'top', labels: { boxWidth: 12 } }
                }
            }
        });
    }

    function renderCampusMatrixTable(breakdown) {
        const tbody = document.getElementById('campusMatrixTbody');
        if (!tbody) return;
        tbody.innerHTML = '';

        breakdown.forEach(c => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td><strong>${c.name}</strong></td>
                <td><span class="badge-pill badge-primary">${c.code}</span></td>
                <td><strong>${c.students}</strong></td>
                <td>${formatCurrency(c.assessed)}</td>
                <td class="text-success font-weight-bold">${formatCurrency(c.collected)}</td>
                <td class="text-danger font-weight-bold">${formatCurrency(c.pending)}</td>
                <td>${c.hostel_capacity > 0 ? `${c.hostel_occupied}/${c.hostel_capacity} beds` : '<span class="badge-pill badge-light">Non-Residential</span>'}</td>
                <td>
                    <button class="btn btn-sm btn-outline view-campus-btn" data-id="${c.id}">
                        <i class="fa-solid fa-eye"></i> View
                    </button>
                </td>
            `;
            tbody.appendChild(tr);
        });

        tbody.querySelectorAll('.view-campus-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const cid = btn.getAttribute('data-id');
                setCampusScope(cid);
                navigateTo('students');
            });
        });
    }

    function renderAttentionList(attentionList) {
        const container = document.getElementById('dashboardAttentionList');
        if (!container) return;
        container.innerHTML = '';

        if (!attentionList || attentionList.length === 0) {
            container.innerHTML = '<p class="text-muted p-3">No compliance or fee alerts currently active.</p>';
            return;
        }

        attentionList.forEach(item => {
            const div = document.createElement('div');
            div.className = 'attention-item';
            div.innerHTML = `
                <div class="att-info">
                    <h5>${item.name} <span class="badge-pill badge-light">${item.student_id}</span></h5>
                    <span class="att-meta">${item.campus_name} • ${item.course}</span>
                    <div class="att-reason mt-1"><i class="fa-solid fa-triangle-exclamation"></i> ${item.reason}</div>
                </div>
                <button class="btn btn-sm btn-outline view-profile-quick" data-id="${item.student_id}">View Profile</button>
            `;
            container.appendChild(div);
        });

        container.querySelectorAll('.view-profile-quick').forEach(btn => {
            btn.addEventListener('click', () => {
                openStudentProfile(btn.getAttribute('data-id'));
            });
        });
    }

    function renderDashboardAudit(activities) {
        const tbody = document.getElementById('dashboardAuditTbody');
        if (!tbody) return;
        tbody.innerHTML = '';

        if (!activities || activities.length === 0) {
            tbody.innerHTML = '<tr><td colspan="5" class="text-center p-3">No audit records available.</td></tr>';
            return;
        }

        activities.forEach(log => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td><code>${log.timestamp}</code></td>
                <td><span class="badge-pill badge-outline">${log.user_role}</span></td>
                <td><span class="badge-pill badge-primary">${log.action}</span></td>
                <td><strong>${log.campus_name || 'All Campuses'}</strong></td>
                <td>${log.details}</td>
            `;
            tbody.appendChild(tr);
        });
    }

    // ==========================================
    // 2. STUDENTS MODULE
    // ==========================================
    async function loadStudentsData() {
        const search = document.getElementById('studentSearchFilter')?.value || '';
        const campus = document.getElementById('studentCampusFilter')?.value || (state.selectedCampusId !== 'ALL' ? state.selectedCampusId : '');
        const status = document.getElementById('studentStatusFilter')?.value || '';
        const feeStatus = document.getElementById('studentFeeStatusFilter')?.value || '';

        // Sync dropdown with state
        if (state.selectedCampusId !== 'ALL' && document.getElementById('studentCampusFilter')) {
            document.getElementById('studentCampusFilter').value = state.selectedCampusId;
        }

        const params = new URLSearchParams();
        params.append('page', state.studentPage);
        params.append('per_page', '100');
        if (campus) params.append('campus_id', campus);
        if (search) params.append('search', search);
        if (status) params.append('status', status);
        if (feeStatus) params.append('fee_status', feeStatus);

        const res = await apiFetch(`/api/students?${params.toString()}`);
        if (!res.success) return;

        const tbody = document.getElementById('studentsTbody');
        tbody.innerHTML = '';

        const firstRecord = res.total ? ((res.page - 1) * res.per_page) + 1 : 0;
        const lastRecord = (res.page - 1) * res.per_page + res.students.length;
        document.getElementById('studentCountLabel').textContent =
            `Showing ${firstRecord}-${lastRecord} of ${res.total} student records`;
        document.getElementById('studentPreviousPageBtn').disabled = res.page <= 1;
        document.getElementById('studentNextPageBtn').disabled = res.page >= res.pages;

        if (res.students.length === 0) {
            tbody.innerHTML = `<tr><td colspan="10" class="text-center p-4">No student records found matching filters.</td></tr>`;
            return;
        }

        res.students.forEach(s => {
            const tr = document.createElement('tr');
            const attBadgeClass = s.attendance_pct < state.settings.attendance_threshold ? 'badge-red' : 'badge-green';
            const feeBadgeClass = s.fee_status === 'Paid' ? 'badge-green' : (s.fee_status === 'Partially Paid' ? 'badge-amber' : 'badge-red');

            tr.innerHTML = `
                <td><code><strong>${s.student_id}</strong></code></td>
                <td>
                    <strong>${s.full_name}</strong>
                    <div style="font-size:0.75rem; color:#64748b;">${s.email}</div>
                </td>
                <td>${s.campus_name}</td>
                <td>${s.course}</td>
                <td>${formatCurrency(s.total_fee)}</td>
                <td class="${s.pending_amount > 0 ? 'text-danger' : 'text-success'} font-weight-bold">
                    ${formatCurrency(s.pending_amount)}
                </td>
                <td><span class="badge-pill ${attBadgeClass}">${s.attendance_pct || 100}%</span></td>
                <td>${s.hostel_room || '<span class="badge-pill badge-light">None</span>'}</td>
                <td><span class="badge-pill ${feeBadgeClass}">${s.fee_status}</span></td>
                <td class="text-right">
                    <button class="btn btn-sm btn-outline view-student-btn" data-id="${s.student_id}" title="View Details">
                        <i class="fa-solid fa-id-card"></i>
                    </button>
                    <button class="btn btn-sm btn-outline pay-fee-quick-btn" data-id="${s.student_id}" title="Record Payment">
                        <i class="fa-solid fa-receipt"></i>
                    </button>
                    <button class="btn btn-sm btn-outline transfer-quick-btn" data-id="${s.student_id}" title="Transfer Campus">
                        <i class="fa-solid fa-arrow-right-arrow-left"></i>
                    </button>
                    <button class="btn btn-sm btn-outline text-danger delete-student-btn" data-id="${s.student_id}" title="Archive Student">
                        <i class="fa-solid fa-trash"></i>
                    </button>
                </td>
            `;
            tbody.appendChild(tr);
        });

        // Attach action handlers
        tbody.querySelectorAll('.view-student-btn').forEach(btn => {
            btn.addEventListener('click', () => openStudentProfile(btn.getAttribute('data-id')));
        });
        tbody.querySelectorAll('.pay-fee-quick-btn').forEach(btn => {
            btn.addEventListener('click', () => openFeePaymentModal(btn.getAttribute('data-id')));
        });
        tbody.querySelectorAll('.transfer-quick-btn').forEach(btn => {
            btn.addEventListener('click', () => openTransferModal(btn.getAttribute('data-id')));
        });
        tbody.querySelectorAll('.delete-student-btn').forEach(btn => {
            btn.addEventListener('click', () => archiveStudent(btn.getAttribute('data-id')));
        });
    }

    // Student Filter listeners
    const resetStudentPageAndLoad = () => {
        state.studentPage = 1;
        loadStudentsData();
    };
    document.getElementById('studentSearchFilter')?.addEventListener('input', debounce(resetStudentPageAndLoad, 300));
    document.getElementById('studentCampusFilter')?.addEventListener('change', resetStudentPageAndLoad);
    document.getElementById('studentStatusFilter')?.addEventListener('change', resetStudentPageAndLoad);
    document.getElementById('studentFeeStatusFilter')?.addEventListener('change', resetStudentPageAndLoad);
    document.getElementById('studentPreviousPageBtn')?.addEventListener('click', () => {
        if (state.studentPage > 1) {
            state.studentPage -= 1;
            loadStudentsData();
        }
    });
    document.getElementById('studentNextPageBtn')?.addEventListener('click', () => {
        state.studentPage += 1;
        loadStudentsData();
    });
    document.getElementById('resetStudentFiltersBtn')?.addEventListener('click', () => {
        document.getElementById('studentSearchFilter').value = '';
        document.getElementById('studentCampusFilter').value = '';
        document.getElementById('studentStatusFilter').value = '';
        document.getElementById('studentFeeStatusFilter').value = '';
        resetStudentPageAndLoad();
    });

    document.getElementById('openNewStudentModalBtn')?.addEventListener('click', () => openAdmissionModal());
    document.getElementById('exportStudentsCsvBtn')?.addEventListener('click', () => {
        const cid = state.selectedCampusId !== 'ALL' ? state.selectedCampusId : '';
        window.location.href = `/api/export/students?campus_id=${cid}`;
    });

    // ==========================================
    // SCHOLARSHIP & EXAMINATION MANAGEMENT
    // ==========================================
    function setupManagementFeatures() {
        const scholarshipForm = document.getElementById('scholarshipForm');
        scholarshipForm.addEventListener('submit', async event => {
            event.preventDefault();
            const recordId = document.getElementById('scholarshipRecordId').value;
            const payload = {
                scholarship_name: document.getElementById('scholarshipName').value.trim(),
                student_id: document.getElementById('scholarshipStudentId').value.trim(),
                campus_id: document.getElementById('scholarshipCampus').value,
                amount: document.getElementById('scholarshipAmount').value,
                eligibility: document.getElementById('scholarshipEligibility').value.trim(),
                application_status: document.getElementById('scholarshipApplicationStatus').value,
                approval_status: document.getElementById('scholarshipApprovalStatus').value
            };
            const result = await apiFetch(recordId ? `/api/scholarships/${recordId}` : '/api/scholarships', {
                method: recordId ? 'PUT' : 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            if (!result.success) {
                showToast(result.error || 'Unable to save scholarship application.', 'error');
                return;
            }
            showToast(result.message, 'success');
            resetScholarshipForm();
            await loadScholarships();
        });

        document.getElementById('cancelScholarshipEditBtn').addEventListener('click', resetScholarshipForm);
        document.getElementById('scholarshipSearch').addEventListener('input', debounce(loadScholarships, 300));
        document.getElementById('scholarshipCampusFilter').addEventListener('change', loadScholarships);
        document.getElementById('scholarshipApplicationFilter').addEventListener('change', loadScholarships);
        document.getElementById('scholarshipApprovalFilter').addEventListener('change', loadScholarships);

        const examForm = document.getElementById('examinationForm');
        examForm.addEventListener('submit', async event => {
            event.preventDefault();
            const recordId = document.getElementById('examRecordId').value;
            const payload = {
                campus_id: document.getElementById('examCampus').value,
                course: document.getElementById('examCourse').value.trim(),
                subject_name: document.getElementById('examSubjectName').value.trim(),
                subject_code: document.getElementById('examSubjectCode').value.trim(),
                exam_date: document.getElementById('examDate').value,
                start_time: document.getElementById('examStartTime').value,
                end_time: document.getElementById('examEndTime').value,
                exam_type: document.getElementById('examType').value.trim(),
                status: document.getElementById('examStatus').value
            };
            const result = await apiFetch(recordId ? `/api/examinations/${recordId}` : '/api/examinations', {
                method: recordId ? 'PUT' : 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            if (!result.success) {
                showToast(result.error || 'Unable to save examination.', 'error');
                return;
            }
            showToast(result.message, 'success');
            resetExamForm();
            await loadExaminations();
        });

        document.getElementById('cancelExamEditBtn').addEventListener('click', resetExamForm);
        document.getElementById('examSearch').addEventListener('input', debounce(loadExaminations, 300));
        document.getElementById('examCampusFilter').addEventListener('change', loadExaminations);
        document.getElementById('examStatusFilter').addEventListener('change', loadExaminations);
    }

    function resetScholarshipForm() {
        document.getElementById('scholarshipForm').reset();
        document.getElementById('scholarshipRecordId').value = '';
        document.getElementById('scholarshipFormTitle').textContent = 'Add Scholarship Application';
        document.getElementById('saveScholarshipBtn').textContent = 'Save Scholarship';
        document.getElementById('cancelScholarshipEditBtn').style.display = 'none';
    }

    async function loadScholarships() {
        const campusFilter = document.getElementById('scholarshipCampusFilter');
        if (state.selectedCampusId !== 'ALL') campusFilter.value = state.selectedCampusId;
        const params = new URLSearchParams();
        const campus = campusFilter.value;
        const search = document.getElementById('scholarshipSearch').value.trim();
        const applicationStatus = document.getElementById('scholarshipApplicationFilter').value;
        const approvalStatus = document.getElementById('scholarshipApprovalFilter').value;
        if (campus) params.set('campus_id', campus);
        if (search) params.set('search', search);
        if (applicationStatus) params.set('application_status', applicationStatus);
        if (approvalStatus) params.set('approval_status', approvalStatus);
        const result = await apiFetch(`/api/scholarships?${params}`);
        if (!result.success) {
            showToast(result.error || 'Unable to load scholarships.', 'error');
            return;
        }
        state.scholarships = result.scholarships;
        document.getElementById('scholarshipTotalCount').textContent = result.stats.total_scholarships;
        document.getElementById('scholarshipApprovedCount').textContent = result.stats.approved_applications;
        document.getElementById('scholarshipPendingCount').textContent = result.stats.pending_applications;
        document.getElementById('scholarshipAmountTotal').textContent = formatCurrency(result.stats.scholarship_amounts);
        const tbody = document.getElementById('scholarshipTbody');
        tbody.innerHTML = '';
        if (!state.scholarships.length) {
            tbody.innerHTML = '<tr><td colspan="8" class="text-center p-4">No scholarship applications found.</td></tr>';
            return;
        }
        state.scholarships.forEach(record => {
            const tr = document.createElement('tr');
            const approvalClass = record.approval_status === 'Approved' ? 'badge-green' :
                (record.approval_status === 'Rejected' ? 'badge-red' : 'badge-amber');
            tr.innerHTML = `
                <td><strong>${escapeHtml(record.scholarship_name)}</strong></td>
                <td><code>${escapeHtml(record.student_id)}</code><div>${escapeHtml(record.student_name)}</div></td>
                <td>${escapeHtml(record.campus_name)}</td>
                <td>${formatCurrency(record.amount)}</td>
                <td>${escapeHtml(record.eligibility)}</td>
                <td>${escapeHtml(record.application_status)}</td>
                <td><span class="badge-pill ${approvalClass}">${escapeHtml(record.approval_status)}</span></td>
                <td><button class="btn btn-sm btn-outline scholarship-edit-btn" data-id="${record.id}">Edit</button></td>
            `;
            tbody.appendChild(tr);
        });
        tbody.querySelectorAll('.scholarship-edit-btn').forEach(button => {
            button.addEventListener('click', () => {
                const record = state.scholarships.find(item => item.id === Number(button.dataset.id));
                if (!record) return;
                document.getElementById('scholarshipRecordId').value = record.id;
                document.getElementById('scholarshipName').value = record.scholarship_name;
                document.getElementById('scholarshipStudentId').value = record.student_id;
                document.getElementById('scholarshipCampus').value = record.campus_id;
                document.getElementById('scholarshipAmount').value = record.amount;
                document.getElementById('scholarshipEligibility').value = record.eligibility;
                document.getElementById('scholarshipApplicationStatus').value = record.application_status;
                document.getElementById('scholarshipApprovalStatus').value = record.approval_status;
                document.getElementById('scholarshipFormTitle').textContent = 'Update Scholarship Application';
                document.getElementById('saveScholarshipBtn').textContent = 'Update Scholarship';
                document.getElementById('cancelScholarshipEditBtn').style.display = '';
                document.getElementById('scholarshipForm').scrollIntoView({ behavior: 'smooth', block: 'start' });
            });
        });
    }

    function resetExamForm() {
        document.getElementById('examinationForm').reset();
        document.getElementById('examRecordId').value = '';
        document.getElementById('examFormTitle').textContent = 'Schedule Examination';
        document.getElementById('saveExamBtn').textContent = 'Schedule Examination';
        document.getElementById('cancelExamEditBtn').style.display = 'none';
    }

    async function loadExaminations() {
        const campusFilter = document.getElementById('examCampusFilter');
        if (state.selectedCampusId !== 'ALL') campusFilter.value = state.selectedCampusId;
        const params = new URLSearchParams();
        const campus = campusFilter.value;
        const search = document.getElementById('examSearch').value.trim();
        const status = document.getElementById('examStatusFilter').value;
        if (campus) params.set('campus_id', campus);
        if (search) params.set('search', search);
        if (status) params.set('status', status);
        const result = await apiFetch(`/api/examinations?${params}`);
        if (!result.success) {
            showToast(result.error || 'Unable to load examinations.', 'error');
            return;
        }
        state.examinations = result.examinations;
        document.getElementById('upcomingExamCount').textContent = result.stats.upcoming_examinations;
        document.getElementById('completedExamCount').textContent = result.stats.completed_examinations;
        const tbody = document.getElementById('examinationTbody');
        tbody.innerHTML = '';
        if (!state.examinations.length) {
            tbody.innerHTML = '<tr><td colspan="10" class="text-center p-4">No examinations found.</td></tr>';
            return;
        }
        state.examinations.forEach(record => {
            const tr = document.createElement('tr');
            const statusClass = record.status === 'Completed' ? 'badge-green' :
                (record.status === 'Cancelled' ? 'badge-red' : 'badge-amber');
            tr.innerHTML = `
                <td>${escapeHtml(record.campus_name)}</td>
                <td>${escapeHtml(record.course)}</td>
                <td>${escapeHtml(record.subject_name)}</td>
                <td><code>${escapeHtml(record.subject_code)}</code></td>
                <td>${escapeHtml(record.exam_date)}</td>
                <td>${escapeHtml(record.start_time)}</td>
                <td>${escapeHtml(record.end_time)}</td>
                <td>${escapeHtml(record.exam_type)}</td>
                <td><span class="badge-pill ${statusClass}">${escapeHtml(record.status)}</span></td>
                <td><button class="btn btn-sm btn-outline exam-edit-btn" data-id="${record.id}">Edit</button></td>
            `;
            tbody.appendChild(tr);
        });
        tbody.querySelectorAll('.exam-edit-btn').forEach(button => {
            button.addEventListener('click', () => {
                const record = state.examinations.find(item => item.id === Number(button.dataset.id));
                if (!record) return;
                document.getElementById('examRecordId').value = record.id;
                document.getElementById('examCampus').value = record.campus_id;
                document.getElementById('examCourse').value = record.course;
                document.getElementById('examSubjectName').value = record.subject_name;
                document.getElementById('examSubjectCode').value = record.subject_code;
                document.getElementById('examDate').value = record.exam_date;
                document.getElementById('examStartTime').value = record.start_time;
                document.getElementById('examEndTime').value = record.end_time;
                document.getElementById('examType').value = record.exam_type;
                document.getElementById('examStatus').value = record.status;
                document.getElementById('examFormTitle').textContent = 'Update Examination';
                document.getElementById('saveExamBtn').textContent = 'Update Examination';
                document.getElementById('cancelExamEditBtn').style.display = '';
                document.getElementById('examinationForm').scrollIntoView({ behavior: 'smooth', block: 'start' });
            });
        });
    }

    // ==========================================
    // ADMISSION & DUPLICATE CHECK MODAL
    // ==========================================
    function openAdmissionModal() {
        const form = document.getElementById('studentAdmissionForm');
        form.reset();
        document.getElementById('duplicateWarningBox').style.display = 'none';

        if (state.selectedCampusId !== 'ALL') {
            document.getElementById('admCampusSelect').value = state.selectedCampusId;
            populateCourseDropdown(state.selectedCampusId);
        }

        openModal('modalStudentAdmission');
    }

    // Real-time duplicate check when email or phone loses focus
    ['admEmail', 'admPhone'].forEach(id => {
        document.getElementById(id)?.addEventListener('blur', async () => {
            const email = document.getElementById('admEmail').value.trim();
            const phone = document.getElementById('admPhone').value.trim();
            if (!email && !phone) return;

            const res = await apiFetch('/api/students/check-duplicate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email, phone })
            });

            const warningBox = document.getElementById('duplicateWarningBox');
            if (res.is_duplicate) {
                document.getElementById('dupAlertTitle').textContent = 'Possible Duplicate Record Detected';
                document.getElementById('dupAlertMsg').textContent = res.message;
                warningBox.style.display = 'flex';
            } else {
                warningBox.style.display = 'none';
            }
        });
    });

    document.getElementById('studentAdmissionForm')?.addEventListener('submit', async (e) => {
        e.preventDefault();
        const force = document.getElementById('forceDuplicateCheck')?.checked || false;

        const payload = {
            first_name: document.getElementById('admFirstName').value.trim(),
            last_name: document.getElementById('admLastName').value.trim(),
            campus_id: document.getElementById('admCampusSelect').value,
            course: document.getElementById('admCourseSelect').value,
            email: document.getElementById('admEmail').value.trim(),
            phone: document.getElementById('admPhone').value.trim(),
            admission_year: document.getElementById('admYear').value,
            gender: document.getElementById('admGender').value,
            total_fee: document.getElementById('admTotalFee').value,
            concession: document.getElementById('admConcession').value,
            force_duplicate: force
        };

        const res = await apiFetch('/api/students', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (res.success) {
            closeModal('modalStudentAdmission');
            showToast(res.message, 'success');
            await loadStudentsData();
            await loadDashboardData();
        } else if (res.is_duplicate_warning) {
            document.getElementById('dupAlertTitle').textContent = 'Admission Warning';
            document.getElementById('dupAlertMsg').textContent = res.error;
            document.getElementById('duplicateWarningBox').style.display = 'flex';
            showToast(res.error, 'warning');
        } else {
            showToast(res.error || 'Failed to submit admission.', 'error');
        }
    });

    // ==========================================
    // STUDENT PROFILE MODAL
    // ==========================================
    async function openStudentProfile(studentId) {
        const res = await apiFetch(`/api/students/${studentId}`);
        if (!res.success) {
            showToast(res.error || 'Student not found.', 'error');
            return;
        }

        const s = res.student;
        state.currentStudent = s;

        // Meta headers
        document.getElementById('profStudentName').textContent = s.full_name;
        document.getElementById('profStudentID').textContent = s.student_id;
        document.getElementById('profCampusName').textContent = s.campus_name;
        document.getElementById('profCourse').textContent = s.course;
        document.getElementById('profStatus').textContent = s.status;

        // Avatar Initials
        const initials = `${s.first_name[0] || ''}${s.last_name[0] || ''}`.toUpperCase();
        document.getElementById('profAvatar').textContent = initials;

        // Overview
        document.getElementById('profEmail').textContent = s.email;
        document.getElementById('profPhone').textContent = s.phone;
        document.getElementById('profGender').textContent = s.gender;
        document.getElementById('profYear').textContent = s.admission_year;

        // Hostel
        if (res.hostel) {
            document.getElementById('profHostelStatus').innerHTML = '<span class="badge-pill badge-green">Allotted</span>';
            document.getElementById('profHostelRoom').textContent = `Room ${res.hostel.room_number} (${res.hostel.block_name})`;
            document.getElementById('profHostelDate').textContent = res.hostel.allocated_date;
        } else {
            document.getElementById('profHostelStatus').innerHTML = '<span class="badge-pill badge-light">Not Allotted</span>';
            document.getElementById('profHostelRoom').textContent = s.has_hostel ? 'Eligible for Allocation' : 'Non-Residential Campus';
            document.getElementById('profHostelDate').textContent = '--';
        }

        // Finance
        document.getElementById('profTotalFee').textContent = formatCurrency(s.total_fee);
        document.getElementById('profConcession').textContent = formatCurrency(s.concession);
        document.getElementById('profPaid').textContent = formatCurrency(s.paid_amount);
        document.getElementById('profPending').textContent = formatCurrency(s.pending_amount);

        // Payments Tab
        const payTbody = document.getElementById('profPaymentsTbody');
        payTbody.innerHTML = '';
        if (res.payments && res.payments.length > 0) {
            res.payments.forEach(p => {
                const tr = document.createElement('tr');
                const isRev = p.transaction_type === 'Reversal';
                tr.innerHTML = `
                    <td><code>${p.receipt_no}</code></td>
                    <td class="${isRev ? 'text-danger' : 'text-success'} font-weight-bold">${formatCurrency(p.amount)}</td>
                    <td>${p.payment_date}</td>
                    <td>${p.payment_mode}</td>
                    <td><span class="badge-pill ${isRev ? 'badge-red' : 'badge-green'}">${p.transaction_type}</span></td>
                    <td>${p.notes || '--'}</td>
                    <td>
                        ${!isRev && p.amount > 0 ? `<button class="btn btn-sm btn-outline text-danger reverse-fee-btn" data-receipt="${p.receipt_no}" data-amt="${p.amount}">Reverse</button>` : '--'}
                    </td>
                `;
                payTbody.appendChild(tr);
            });

            payTbody.querySelectorAll('.reverse-fee-btn').forEach(btn => {
                btn.addEventListener('click', () => {
                    openReversalModal(btn.getAttribute('data-receipt'), btn.getAttribute('data-amt'));
                });
            });
        } else {
            payTbody.innerHTML = '<tr><td colspan="7" class="text-center p-3">No payments recorded yet.</td></tr>';
        }

        // Attendance Tab
        document.getElementById('profAttTotal').textContent = res.attendance.total_days;
        document.getElementById('profAttPresent').textContent = res.attendance.present_days;
        document.getElementById('profAttRate').textContent = `${res.attendance.percentage}%`;

        const attTbody = document.getElementById('profAttendanceTbody');
        attTbody.innerHTML = '';
        if (res.attendance.records && res.attendance.records.length > 0) {
            res.attendance.records.forEach(a => {
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td>${a.date}</td>
                    <td><span class="badge-pill ${a.status === 'Present' ? 'badge-green' : 'badge-red'}">${a.status}</span></td>
                    <td>${a.marked_by}</td>
                `;
                attTbody.appendChild(tr);
            });
        } else {
            attTbody.innerHTML = '<tr><td colspan="3" class="text-center p-3">No attendance records found.</td></tr>';
        }

        const examTbody = document.getElementById('profExaminationsTbody');
        const examResult = await apiFetch(`/api/students/${encodeURIComponent(studentId)}/examinations`);
        examTbody.innerHTML = '';
        if (examResult.success && examResult.examinations.length) {
            examResult.examinations.forEach(exam => {
                const tr = document.createElement('tr');
                const statusClass = exam.status === 'Completed' ? 'badge-green' :
                    (exam.status === 'Cancelled' ? 'badge-red' : 'badge-amber');
                tr.innerHTML = `
                    <td>${escapeHtml(exam.subject_name)}</td>
                    <td><code>${escapeHtml(exam.subject_code)}</code></td>
                    <td>${escapeHtml(exam.exam_date)}</td>
                    <td>${escapeHtml(exam.start_time)}</td>
                    <td>${escapeHtml(exam.end_time)}</td>
                    <td>${escapeHtml(exam.exam_type)}</td>
                    <td><span class="badge-pill ${statusClass}">${escapeHtml(exam.status)}</span></td>
                `;
                examTbody.appendChild(tr);
            });
        } else {
            examTbody.innerHTML = '<tr><td colspan="7" class="text-center p-3">No examinations are scheduled for this student\'s course.</td></tr>';
        }

        // Transfers Tab
        const transTbody = document.getElementById('profTransfersTbody');
        transTbody.innerHTML = '';
        if (res.transfers && res.transfers.length > 0) {
            res.transfers.forEach(t => {
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td>${t.transfer_date}</td>
                    <td>${t.from_campus_name}</td>
                    <td><strong>${t.to_campus_name}</strong></td>
                    <td>${t.reason}</td>
                    <td>${t.transferred_by}</td>
                `;
                transTbody.appendChild(tr);
            });
        } else {
            transTbody.innerHTML = '<tr><td colspan="5" class="text-center p-3">No transfer history (Enrolled in original campus).</td></tr>';
        }

        openModal('modalStudentProfile');
    }

    // Profile Modal Tabs
    document.querySelectorAll('.prof-tab-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.prof-tab-btn').forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.prof-tab-content').forEach(c => c.classList.remove('active'));
            btn.classList.add('active');
            const target = btn.getAttribute('data-tab');
            document.getElementById(target)?.classList.add('active');
        });
    });

    // Profile Footer Buttons
    document.getElementById('profPayFeeBtn')?.addEventListener('click', () => {
        if (state.currentStudent) {
            closeModal('modalStudentProfile');
            openFeePaymentModal(state.currentStudent.student_id);
        }
    });

    document.getElementById('profTransferBtn')?.addEventListener('click', () => {
        if (state.currentStudent) {
            closeModal('modalStudentProfile');
            openTransferModal(state.currentStudent.student_id);
        }
    });

    // Archive / Soft Delete Student
    async function archiveStudent(studentId) {
        if (!confirm(`Are you sure you want to archive student ${studentId}? The ID will remain permanently reserved in the sequential sequence.`)) {
            return;
        }

        const res = await apiFetch(`/api/students/${studentId}`, { method: 'DELETE' });
        if (res.success) {
            showToast(res.message, 'success');
            await loadStudentsData();
            await loadDashboardData();
        } else {
            showToast(res.error || 'Failed to archive student.', 'error');
        }
    }

    // ==========================================
    // CAMPUS TRANSFER WORKFLOW
    // ==========================================
    function openTransferModal(studentId) {
        document.getElementById('campusTransferForm').reset();
        document.getElementById('transStudentId').value = studentId;

        // Find student info
        apiFetch(`/api/students/${studentId}`).then(res => {
            if (res.success) {
                document.getElementById('transStudentName').textContent = `${res.student.full_name} (${res.student.student_id})`;
                document.getElementById('transCurrentCampus').textContent = `Current: ${res.student.campus_name}`;
                openModal('modalCampusTransfer');
            }
        });
    }

    document.getElementById('campusTransferForm')?.addEventListener('submit', async (e) => {
        e.preventDefault();
        const payload = {
            student_id: document.getElementById('transStudentId').value,
            to_campus_id: document.getElementById('transToCampusSelect').value,
            reason: document.getElementById('transReason').value.trim()
        };

        const res = await apiFetch('/api/students/transfer', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (res.success) {
            closeModal('modalCampusTransfer');
            showToast(res.message, 'success');
            await loadStudentsData();
            await loadDashboardData();
        } else {
            showToast(res.error || 'Transfer failed.', 'error');
        }
    });

    // ==========================================
    // 3. FEE MANAGEMENT MODULE
    // ==========================================
    async function loadFeesData() {
        const campus = document.getElementById('feeCampusFilter')?.value || (state.selectedCampusId !== 'ALL' ? state.selectedCampusId : '');
        const search = document.getElementById('feeStudentSearch')?.value || '';
        const feeStatus = document.getElementById('feeStatusQuickFilter')?.value || '';

        // Update fee metrics in banner
        const campusParam = campus ? `?campus_id=${campus}` : (state.selectedCampusId !== 'ALL' ? `?campus_id=${state.selectedCampusId}` : '');
        const dashStats = await apiFetch(`/api/dashboard/stats${campusParam}`);
        if (dashStats.success) {
            document.getElementById('feePageAssessed').textContent = formatCurrency(dashStats.metrics.total_assessed);
            document.getElementById('feePageConcessions').textContent = formatCurrency(dashStats.metrics.total_concession);
            document.getElementById('feePageCollected').textContent = formatCurrency(dashStats.metrics.total_collected);
            document.getElementById('feePagePending').textContent = formatCurrency(dashStats.metrics.total_outstanding);
        }

        // Load student fee list
        const params = new URLSearchParams();
        if (campus) params.append('campus_id', campus);
        if (search) params.append('search', search);
        if (feeStatus) params.append('fee_status', feeStatus);

        const res = await apiFetch(`/api/students?${params.toString()}`);
        if (!res.success) return;

        const tbody = document.getElementById('feeManagementTbody');
        tbody.innerHTML = '';

        if (res.students.length === 0) {
            tbody.innerHTML = '<tr><td colspan="10" class="text-center p-4">No records found.</td></tr>';
            return;
        }

        res.students.forEach(s => {
            const tr = document.createElement('tr');
            const netPayable = s.total_fee - s.concession;
            const feeBadgeClass = s.fee_status === 'Paid' ? 'badge-green' : (s.fee_status === 'Partially Paid' ? 'badge-amber' : 'badge-red');

            tr.innerHTML = `
                <td><code><strong>${s.student_id}</strong></code></td>
                <td><strong>${s.full_name}</strong></td>
                <td>${s.campus_name}</td>
                <td>${formatCurrency(s.total_fee)}</td>
                <td class="text-purple">${formatCurrency(s.concession)}</td>
                <td><strong>${formatCurrency(netPayable)}</strong></td>
                <td class="text-success font-weight-bold">${formatCurrency(s.paid_amount)}</td>
                <td class="${s.pending_amount > 0 ? 'text-danger font-weight-bold' : 'text-success'}">
                    ${formatCurrency(s.pending_amount)}
                </td>
                <td><span class="badge-pill ${feeBadgeClass}">${s.fee_status}</span></td>
                <td class="text-right">
                    <button class="btn btn-sm btn-primary record-fee-btn" data-id="${s.student_id}">
                        <i class="fa-solid fa-receipt"></i> Pay
                    </button>
                    <button class="btn btn-sm btn-outline view-ledger-btn" data-id="${s.student_id}">
                        <i class="fa-solid fa-list"></i> History
                    </button>
                </td>
            `;
            tbody.appendChild(tr);
        });

        tbody.querySelectorAll('.record-fee-btn').forEach(btn => {
            btn.addEventListener('click', () => openFeePaymentModal(btn.getAttribute('data-id')));
        });
        tbody.querySelectorAll('.view-ledger-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                openStudentProfile(btn.getAttribute('data-id'));
            });
        });
    }

    document.getElementById('feeStudentSearch')?.addEventListener('input', debounce(loadFeesData, 300));
    document.getElementById('feeCampusFilter')?.addEventListener('change', loadFeesData);
    document.getElementById('feeStatusQuickFilter')?.addEventListener('change', loadFeesData);
    document.getElementById('openPaymentModalBtn')?.addEventListener('click', () => openFeePaymentModal());
    document.getElementById('exportFeesReportBtn')?.addEventListener('click', () => {
        const cid = state.selectedCampusId !== 'ALL' ? state.selectedCampusId : '';
        window.location.href = `/api/export/fees?campus_id=${cid}`;
    });

    // Record Payment Modal
    function openFeePaymentModal(studentId = '') {
        const form = document.getElementById('recordPaymentForm');
        form.reset();
        document.getElementById('payDate').value = new Date().toISOString().split('T')[0];
        document.getElementById('payBalanceBox').style.display = 'none';

        if (studentId) {
            document.getElementById('payStudentId').value = studentId;
            fetchStudentBalanceForPayment(studentId);
        }

        openModal('modalRecordPayment');
    }

    document.getElementById('payStudentId')?.addEventListener('blur', (e) => {
        const sid = e.target.value.trim();
        if (sid) fetchStudentBalanceForPayment(sid);
    });

    async function fetchStudentBalanceForPayment(studentId) {
        const res = await apiFetch(`/api/students/${studentId}`);
        const box = document.getElementById('payBalanceBox');
        if (res.success) {
            document.getElementById('payOutstandingLabel').textContent = formatCurrency(res.student.pending_amount);
            document.getElementById('payAmount').max = res.student.pending_amount;
            document.getElementById('payAmount').value = res.student.pending_amount > 0 ? res.student.pending_amount : 0;
            box.style.display = 'flex';
        } else {
            box.style.display = 'none';
        }
    }

    document.getElementById('recordPaymentForm')?.addEventListener('submit', async (e) => {
        e.preventDefault();
        const payload = {
            student_id: document.getElementById('payStudentId').value.trim(),
            amount: parseFloat(document.getElementById('payAmount').value),
            payment_mode: document.getElementById('payMode').value,
            payment_date: document.getElementById('payDate').value,
            notes: document.getElementById('payNotes').value.trim()
        };

        const res = await apiFetch('/api/fees/payments', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (res.success) {
            closeModal('modalRecordPayment');
            showToast(`${res.message} (Receipt: ${res.receipt_no})`, 'success');
            await loadFeesData();
            await loadDashboardData();
        } else {
            showToast(res.error || 'Payment failed.', 'error');
        }
    });

    // Payment Reversal Modal
    function openReversalModal(receiptNo, amount) {
        document.getElementById('feeReversalForm').reset();
        document.getElementById('revReceiptNo').value = receiptNo;
        document.getElementById('revReceiptDisplay').textContent = receiptNo;
        document.getElementById('revAmountDisplay').textContent = formatCurrency(amount);
        openModal('modalFeeReversal');
    }

    document.getElementById('feeReversalForm')?.addEventListener('submit', async (e) => {
        e.preventDefault();
        const payload = {
            receipt_no: document.getElementById('revReceiptNo').value,
            reason: document.getElementById('revReason').value.trim()
        };

        const res = await apiFetch('/api/fees/reversal', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (res.success) {
            closeModal('modalFeeReversal');
            closeModal('modalStudentProfile');
            showToast(res.message, 'success');
            await loadFeesData();
            await loadDashboardData();
        } else {
            showToast(res.error || 'Reversal failed.', 'error');
        }
    });

    // ==========================================
    // 4. ATTENDANCE & ALERTS MODULE
    // ==========================================
    function setupAttendanceFeature() {
        const dateInput = document.getElementById('attendanceDatePicker');
        if (dateInput) {
            dateInput.value = new Date().toISOString().split('T')[0];
            dateInput.addEventListener('change', loadAttendanceData);
        }

        document.getElementById('attendanceCampusFilter')?.addEventListener('change', loadAttendanceData);

        document.getElementById('markAllPresentBtn')?.addEventListener('click', () => {
            document.querySelectorAll('.att-toggle-btn').forEach(btn => {
                btn.classList.remove('btn-danger');
                btn.classList.add('btn-success');
                btn.innerHTML = '<i class="fa-solid fa-check"></i> Present';
                btn.setAttribute('data-status', 'Present');
            });
            updateAttendanceSummaryBar();
        });

        document.getElementById('saveBulkAttendanceBtn')?.addEventListener('click', saveAttendanceBatch);
        document.getElementById('exportAttendanceCsvBtn')?.addEventListener('click', () => {
            const cid = state.selectedCampusId !== 'ALL' ? state.selectedCampusId : '';
            window.location.href = `/api/export/attendance?campus_id=${cid}`;
        });
    }

    async function loadAttendanceData() {
        const date = document.getElementById('attendanceDatePicker')?.value || new Date().toISOString().split('T')[0];
        const campus = document.getElementById('attendanceCampusFilter')?.value || (state.selectedCampusId !== 'ALL' ? state.selectedCampusId : '');

        const params = new URLSearchParams({ date });
        if (campus) params.append('campus_id', campus);

        const res = await apiFetch(`/api/attendance?${params.toString()}`);
        if (!res.success) return;

        // Summary bar
        document.getElementById('attStatTotal').textContent = res.summary.total;
        document.getElementById('attStatPresent').textContent = res.summary.present;
        document.getElementById('attStatAbsent').textContent = res.summary.absent;
        document.getElementById('attStatNotMarked').textContent = res.summary.not_marked;
        document.getElementById('attThresholdDisplay').textContent = `${state.settings.attendance_threshold}%`;

        const tbody = document.getElementById('attendanceGridTbody');
        tbody.innerHTML = '';

        if (res.records.length === 0) {
            tbody.innerHTML = '<tr><td colspan="7" class="text-center p-4">No enrolled students found.</td></tr>';
            return;
        }

        res.records.forEach(r => {
            const tr = document.createElement('tr');
            const pct = r.overall_pct || 100;
            const isLow = pct < state.settings.attendance_threshold;

            const isPresent = r.status === 'Present';
            const isAbsent = r.status === 'Absent';
            const btnClass = isPresent ? 'btn-success' : (isAbsent ? 'btn-danger' : 'btn-outline');
            const btnText = isPresent ? '<i class="fa-solid fa-check"></i> Present' : (isAbsent ? '<i class="fa-solid fa-xmark"></i> Absent' : 'Mark Status');

            tr.innerHTML = `
                <td><code><strong>${r.student_id}</strong></code></td>
                <td><strong>${r.full_name}</strong></td>
                <td>${r.campus_name}</td>
                <td>${r.course}</td>
                <td><strong>${pct}%</strong></td>
                <td>
                    <span class="badge-pill ${isLow ? 'badge-red' : 'badge-green'}">
                        ${isLow ? '<i class="fa-solid fa-triangle-exclamation"></i> Low Alert' : 'Normal'}
                    </span>
                </td>
                <td>
                    <button class="btn btn-sm ${btnClass} att-toggle-btn" data-id="${r.student_id}" data-status="${r.status}">
                        ${btnText}
                    </button>
                </td>
            `;
            tbody.appendChild(tr);
        });

        // Toggle button click listener
        tbody.querySelectorAll('.att-toggle-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const cur = btn.getAttribute('data-status');
                if (cur === 'Present') {
                    btn.setAttribute('data-status', 'Absent');
                    btn.className = 'btn btn-sm btn-danger att-toggle-btn';
                    btn.innerHTML = '<i class="fa-solid fa-xmark"></i> Absent';
                } else {
                    btn.setAttribute('data-status', 'Present');
                    btn.className = 'btn btn-sm btn-success att-toggle-btn';
                    btn.innerHTML = '<i class="fa-solid fa-check"></i> Present';
                }
                updateAttendanceSummaryBar();
            });
        });
    }

    function updateAttendanceSummaryBar() {
        const buttons = document.querySelectorAll('.att-toggle-btn');
        let prs = 0, abs = 0, notM = 0;
        buttons.forEach(b => {
            const st = b.getAttribute('data-status');
            if (st === 'Present') prs++;
            else if (st === 'Absent') abs++;
            else notM++;
        });
        document.getElementById('attStatPresent').textContent = prs;
        document.getElementById('attStatAbsent').textContent = abs;
        document.getElementById('attStatNotMarked').textContent = notM;
    }

    async function saveAttendanceBatch() {
        const date = document.getElementById('attendanceDatePicker')?.value;
        const records = [];

        document.querySelectorAll('.att-toggle-btn').forEach(btn => {
            const st = btn.getAttribute('data-status');
            if (st === 'Present' || st === 'Absent') {
                records.push({
                    student_id: btn.getAttribute('data-id'),
                    status: st
                });
            }
        });

        if (records.length === 0) {
            showToast('No students marked for attendance.', 'warning');
            return;
        }

        const res = await apiFetch('/api/attendance/mark', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ date, records })
        });

        if (res.success) {
            showToast(res.message, 'success');
            await loadAttendanceData();
            await loadDashboardData();
        } else {
            showToast(res.error || 'Failed to save attendance.', 'error');
        }
    }

    // ==========================================
    // 5. HOSTEL MANAGEMENT MODULE
    // ==========================================
    async function loadHostelData() {
        const campus = document.getElementById('hostelCampusFilter')?.value || (state.selectedCampusId !== 'ALL' && state.selectedCampusId !== '6' ? state.selectedCampusId : '');

        const params = campus ? `?campus_id=${campus}` : '';
        const res = await apiFetch(`/api/hostel/rooms${params}`);
        if (!res.success) return;

        let totalRooms = res.rooms.length;
        let totalBeds = 0;
        let occBeds = 0;

        res.rooms.forEach(r => {
            totalBeds += r.capacity;
            occBeds += r.occupied_beds;
        });

        document.getElementById('hostelTotalRooms').textContent = totalRooms;
        document.getElementById('hostelTotalBeds').textContent = `${totalBeds} Beds`;
        document.getElementById('hostelOccupiedBeds').textContent = occBeds;
        document.getElementById('hostelAvailableBeds').textContent = Math.max(0, totalBeds - occBeds);

        const container = document.getElementById('hostelRoomsContainer');
        container.innerHTML = '';

        if (res.rooms.length === 0) {
            container.innerHTML = '<p class="text-muted p-4">No hostel rooms registered for this campus selection.</p>';
            return;
        }

        res.rooms.forEach(rm => {
            const card = document.createElement('div');
            card.className = 'room-card';
            const isFull = rm.occupied_beds >= rm.capacity;
            const statusBadgeClass = isFull ? 'badge-red' : 'badge-green';

            let studentsHtml = '';
            if (rm.allocated_students && rm.allocated_students.length > 0) {
                rm.allocated_students.forEach(st => {
                    studentsHtml += `
                        <div class="room-allocated-student-tag">
                            <span><strong>${st.student_id}</strong>: ${st.full_name}</span>
                            <button class="btn btn-sm btn-outline text-danger release-hostel-btn" data-alloc-id="${st.id}" title="Release Allocation">
                                <i class="fa-solid fa-right-from-bracket"></i>
                            </button>
                        </div>
                    `;
                });
            } else {
                studentsHtml = '<p class="text-muted" style="font-size:0.75rem;">All beds currently vacant</p>';
            }

            card.innerHTML = `
                <div class="room-card-header">
                    <div>
                        <span class="room-number-badge">Room ${rm.room_number}</span>
                        <div class="room-campus-name">${rm.campus_name} • ${rm.block_name}</div>
                    </div>
                    <span class="badge-pill ${statusBadgeClass}">${rm.status}</span>
                </div>
                <div class="room-occupancy-bar-wrapper">
                    <div style="display:flex; justify-content:space-between; font-size:0.75rem; margin-bottom:4px;">
                        <span>Occupancy: <strong>${rm.occupied_beds}/${rm.capacity}</strong></span>
                        <span>${rm.occupancy_pct}%</span>
                    </div>
                    <div class="room-bar-track">
                        <div class="room-bar-fill" style="width: ${Math.min(100, rm.occupancy_pct)}%;"></div>
                    </div>
                </div>
                <div class="room-card-students-list">
                    <strong style="display:block; margin-bottom:6px; font-size:0.75rem; color:#475569;">Resident Students:</strong>
                    ${studentsHtml}
                </div>
            `;
            container.appendChild(card);
        });

        // Release allocation listeners
        container.querySelectorAll('.release-hostel-btn').forEach(btn => {
            btn.addEventListener('click', async () => {
                const allocId = btn.getAttribute('data-alloc-id');
                if (!confirm('Are you sure you want to release this bed accommodation?')) return;

                const releaseRes = await apiFetch('/api/hostel/release', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ allocation_id: allocId })
                });

                if (releaseRes.success) {
                    showToast(releaseRes.message, 'success');
                    await loadHostelData();
                    await loadDashboardData();
                } else {
                    showToast(releaseRes.error || 'Failed to release bed.', 'error');
                }
            });
        });
    }

    document.getElementById('hostelCampusFilter')?.addEventListener('change', loadHostelData);
    document.getElementById('openAddRoomModalBtn')?.addEventListener('click', () => openModal('modalAddHostelRoom'));
    document.getElementById('openAllocateHostelModalBtn')?.addEventListener('click', openHostelAllocationModal);
    document.getElementById('exportHostelReportBtn')?.addEventListener('click', () => {
        const cid = state.selectedCampusId !== 'ALL' ? state.selectedCampusId : '';
        window.location.href = `/api/export/hostel?campus_id=${cid}`;
    });

    // Add Hostel Room
    document.getElementById('addHostelRoomForm')?.addEventListener('submit', async (e) => {
        e.preventDefault();
        const payload = {
            campus_id: document.getElementById('newRoomCampus').value,
            room_number: document.getElementById('newRoomNumber').value.trim(),
            block_name: document.getElementById('newRoomBlock').value.trim(),
            capacity: document.getElementById('newRoomCapacity').value
        };

        const res = await apiFetch('/api/hostel/rooms', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (res.success) {
            closeModal('modalAddHostelRoom');
            showToast(res.message, 'success');
            await loadHostelData();
        } else {
            showToast(res.error || 'Failed to add room.', 'error');
        }
    });

    // Allocate Hostel Room
    async function openHostelAllocationModal() {
        document.getElementById('hostelAllocateForm').reset();
        document.getElementById('hostelRoomSelect').innerHTML = '<option value="">-- Select Available Room --</option>';

        // Load all available rooms
        const roomsRes = await apiFetch('/api/hostel/rooms');
        if (roomsRes.success) {
            const select = document.getElementById('hostelRoomSelect');
            roomsRes.rooms.filter(r => r.occupied_beds < r.capacity).forEach(r => {
                const opt = document.createElement('option');
                opt.value = r.id;
                opt.textContent = `${r.room_number} (${r.campus_name} - ${r.block_name}) [${r.capacity - r.occupied_beds} vacant]`;
                select.appendChild(opt);
            });
        }

        openModal('modalHostelAllocate');
    }

    document.getElementById('hostelAllocateForm')?.addEventListener('submit', async (e) => {
        e.preventDefault();
        const payload = {
            student_id: document.getElementById('hostelStudentId').value.trim(),
            room_id: document.getElementById('hostelRoomSelect').value,
            remarks: document.getElementById('hostelRemarks').value.trim()
        };

        const res = await apiFetch('/api/hostel/allocate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (res.success) {
            closeModal('modalHostelAllocate');
            showToast(res.message, 'success');
            await loadHostelData();
            await loadDashboardData();
        } else {
            showToast(res.error || 'Hostel allocation failed.', 'error');
        }
    });

    // ==========================================
    // 6. SPREADSHEET IMPORT MODULE (Pandas)
    // ==========================================
    let pendingImportValidRows = [];

    function setupImportFeature() {
        const dropzone = document.getElementById('uploadDropzone');
        const fileInput = document.getElementById('spreadsheetFileInput');
        const clickArea = document.getElementById('dropzoneClickArea');
        const filenamePill = document.getElementById('selectedFilenamePill');
        const dropzoneActions = document.getElementById('dropzoneActions');

        clickArea.addEventListener('click', () => fileInput.click());

        dropzone.addEventListener('dragover', (e) => {
            e.preventDefault();
            dropzone.classList.add('dragover');
        });
        dropzone.addEventListener('dragleave', () => dropzone.classList.remove('dragover'));
        dropzone.addEventListener('drop', (e) => {
            e.preventDefault();
            dropzone.classList.remove('dragover');
            if (e.dataTransfer.files.length > 0) {
                fileInput.files = e.dataTransfer.files;
                handleSelectedFile(fileInput.files[0]);
            }
        });

        fileInput.addEventListener('change', () => {
            if (fileInput.files.length > 0) {
                handleSelectedFile(fileInput.files[0]);
            }
        });

        function handleSelectedFile(file) {
            filenamePill.textContent = `${file.name} (${Math.round(file.size / 1024)} KB)`;
            filenamePill.style.display = 'inline-block';
            dropzoneActions.style.display = 'flex';
        }

        document.getElementById('clearFileBtn')?.addEventListener('click', () => {
            fileInput.value = '';
            filenamePill.style.display = 'none';
            dropzoneActions.style.display = 'none';
            document.getElementById('importPreviewPanel').style.display = 'none';
        });

        document.getElementById('startValidationBtn')?.addEventListener('click', async () => {
            if (!fileInput.files.length) return;
            const formData = new FormData();
            formData.append('file', fileInput.files[0]);

            showToast('Parsing spreadsheet with Python Pandas and running validation...', 'info');

            const res = await apiFetch('/api/import/preview', {
                method: 'POST',
                body: formData
            });

            if (res.success) {
                renderImportPreview(res);
            } else {
                showToast(res.error || 'Failed to parse file.', 'error');
            }
        });

        document.getElementById('commitImportBtn')?.addEventListener('click', async () => {
            if (!pendingImportValidRows.length) return;

            const res = await apiFetch('/api/import/commit', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ rows: pendingImportValidRows })
            });

            if (res.success) {
                showToast(res.message, 'success');
                document.getElementById('importPreviewPanel').style.display = 'none';
                fileInput.value = '';
                filenamePill.style.display = 'none';
                dropzoneActions.style.display = 'none';
                await loadStudentsData();
                await loadDashboardData();
            } else {
                showToast(res.error || 'Import commit failed.', 'error');
            }
        });
    }

    function renderImportPreview(data) {
        const panel = document.getElementById('importPreviewPanel');
        panel.style.display = 'block';

        pendingImportValidRows = data.valid_rows;

        document.getElementById('validCountBadge').textContent = `${data.valid_count} Valid Rows`;
        document.getElementById('invalidCountBadge').textContent = `${data.invalid_count} Invalid Rows`;

        const commitBtn = document.getElementById('commitImportBtn');
        commitBtn.disabled = data.valid_count === 0;

        // Render Invalid rows table
        const invContainer = document.getElementById('invalidRowsContainer');
        const invTbody = document.getElementById('invalidRowsTbody');
        invTbody.innerHTML = '';
        if (data.invalid_rows && data.invalid_rows.length > 0) {
            invContainer.style.display = 'block';
            data.invalid_rows.forEach(r => {
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td><strong>#${r.row}</strong></td>
                    <td>${r.full_name}</td>
                    <td>${r.campus_name}</td>
                    <td>${r.email}</td>
                    <td class="text-danger"><strong>${r.errors.join('; ')}</strong></td>
                `;
                invTbody.appendChild(tr);
            });
        } else {
            invContainer.style.display = 'none';
        }

        // Render Valid rows table
        const valTbody = document.getElementById('validRowsTbody');
        valTbody.innerHTML = '';
        if (data.valid_rows && data.valid_rows.length > 0) {
            data.valid_rows.forEach(r => {
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td>#${r.row}</td>
                    <td><strong>${r.full_name}</strong></td>
                    <td>${r.campus_name}</td>
                    <td>${r.course}</td>
                    <td>${r.admission_year}</td>
                    <td>${r.email}</td>
                    <td>${r.phone}</td>
                    <td>${formatCurrency(r.total_fee)}</td>
                    <td class="text-purple">${formatCurrency(r.concession)}</td>
                `;
                valTbody.appendChild(tr);
            });
        } else {
            valTbody.innerHTML = '<tr><td colspan="9" class="text-center p-3">No valid records to display.</td></tr>';
        }

        // Scroll to preview
        panel.scrollIntoView({ behavior: 'smooth' });
    }

    // ==========================================
    // 7. CONSOLIDATED REPORTS MODULE
    // ==========================================
    async function loadReportsData() {
        const res = await apiFetch('/api/reports/consolidated');
        if (!res.success) return;

        const tbody = document.getElementById('consolidatedSummaryTbody');
        const tfoot = document.getElementById('consolidatedSummaryTfoot');
        tbody.innerHTML = '';
        tfoot.innerHTML = '';

        res.campuses.forEach(c => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td><strong>${c.name}</strong></td>
                <td><span class="badge-pill badge-primary">${c.code}</span></td>
                <td><strong>${c.students}</strong></td>
                <td>${formatCurrency(c.assessed)}</td>
                <td class="text-purple">${formatCurrency(c.concession)}</td>
                <td class="text-success font-weight-bold">${formatCurrency(c.collected)}</td>
                <td class="text-danger font-weight-bold">${formatCurrency(c.pending)}</td>
                <td><span class="badge-pill badge-green">${c.collection_rate}%</span></td>
                <td>${c.has_hostel ? `${c.hostel_occupied}/${c.hostel_capacity}` : '<span class="badge-pill badge-light">N/A</span>'}</td>
                <td><strong>${c.avg_attendance}%</strong></td>
            `;
            tbody.appendChild(tr);
        });

        // Totals row
        const tot = res.totals;
        tfoot.innerHTML = `
            <tr>
                <td colspan="2"><strong>INSTITUTIONAL GRAND TOTAL:</strong></td>
                <td><strong>${tot.students}</strong></td>
                <td><strong>${formatCurrency(tot.assessed)}</strong></td>
                <td class="text-purple"><strong>${formatCurrency(tot.concession)}</strong></td>
                <td class="text-success"><strong>${formatCurrency(tot.collected)}</strong></td>
                <td class="text-danger"><strong>${formatCurrency(tot.pending)}</strong></td>
                <td><span class="badge-pill badge-green">${tot.collection_rate}%</span></td>
                <td><strong>${tot.hostel_occupied}/${tot.hostel_capacity}</strong></td>
                <td>--</td>
            </tr>
        `;

        // Render Reports Chart
        renderReportsChart(res.campuses);
    }

    function renderReportsChart(campuses) {
        const ctx = document.getElementById('chartReportsComparison');
        if (!ctx) return;

        if (state.charts.reportsComparison) {
            state.charts.reportsComparison.destroy();
        }

        state.charts.reportsComparison = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: campuses.map(c => c.name),
                datasets: [
                    {
                        label: 'Total Assessed (₹)',
                        data: campuses.map(c => c.assessed),
                        backgroundColor: '#6366f1'
                    },
                    {
                        label: 'Fees Collected (₹)',
                        data: campuses.map(c => c.collected),
                        backgroundColor: '#10b981'
                    },
                    {
                        label: 'Pending Balance (₹)',
                        data: campuses.map(c => c.pending),
                        backgroundColor: '#f43f5e'
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { position: 'top' }
                },
                scales: {
                    y: {
                        ticks: {
                            callback: value => '₹' + (value >= 1000 ? (value / 1000) + 'k' : value)
                        }
                    }
                }
            }
        });
    }

    document.getElementById('exportAllStudentsBtn')?.addEventListener('click', () => {
        window.location.href = '/api/export/students';
    });
    document.getElementById('exportAllFeesBtn')?.addEventListener('click', () => {
        window.location.href = '/api/export/fees';
    });
    document.getElementById('exportAllAttendanceBtn')?.addEventListener('click', () => {
        window.location.href = '/api/export/attendance';
    });
    document.getElementById('printReportBtn')?.addEventListener('click', () => window.print());
    document.getElementById('exportConsolidatedReportBtn')?.addEventListener('click', () => {
        window.location.href = '/api/export/students';
    });

    // ==========================================
    // 8. SETTINGS & AUDIT LOGS MODULE
    // ==========================================
    async function loadSettings() {
        const res = await apiFetch('/api/settings');
        if (res.success && res.settings) {
            state.settings = { ...state.settings, ...res.settings };
            if (document.getElementById('settingInstName')) {
                document.getElementById('settingInstName').value = res.settings.institution_name || '';
            }
            if (document.getElementById('settingAttendanceThreshold')) {
                document.getElementById('settingAttendanceThreshold').value = res.settings.attendance_threshold || 75;
            }
        }
    }

    function setupSettingsFeature() {
        document.getElementById('saveSettingsBtn')?.addEventListener('click', async () => {
            const instName = document.getElementById('settingInstName').value.trim();
            const threshold = document.getElementById('settingAttendanceThreshold').value;

            const res = await apiFetch('/api/settings', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    institution_name: instName,
                    attendance_threshold: threshold
                })
            });

            if (res.success) {
                showToast('Settings saved successfully.', 'success');
                state.settings.attendance_threshold = parseFloat(threshold);
                state.settings.institution_name = instName;
                await loadAuditLogs();
            }
        });

        document.getElementById('auditCampusFilter')?.addEventListener('change', loadAuditLogs);
    }

    async function loadAuditLogs() {
        const campus = document.getElementById('auditCampusFilter')?.value || '';
        const params = campus ? `?campus=${encodeURIComponent(campus)}` : '';
        const res = await apiFetch(`/api/audit-logs${params}`);
        if (!res.success) return;

        const tbody = document.getElementById('auditTrailTbody');
        if (!tbody) return;
        tbody.innerHTML = '';

        if (res.logs.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" class="text-center p-4">No audit logs recorded.</td></tr>';
            return;
        }

        res.logs.forEach(l => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td><code>#${l.id}</code></td>
                <td><code>${l.timestamp}</code></td>
                <td><span class="badge-pill badge-outline">${l.user_role}</span></td>
                <td><span class="badge-pill badge-primary">${l.action}</span></td>
                <td><strong>${l.campus_name || 'All Campuses'}</strong></td>
                <td>${l.details}</td>
            `;
            tbody.appendChild(tr);
        });
    }

    // ==========================================
    // GLOBAL SEARCH
    // ==========================================
    function setupSearchFeature() {
        const searchInput = document.getElementById('globalSearchInput');
        const clearBtn = document.getElementById('globalSearchClear');

        searchInput.addEventListener('input', debounce(async (e) => {
            const val = e.target.value.trim();
            if (val) {
                clearBtn.style.display = 'block';
                // Switch to students tab and filter
                if (state.activePage !== 'students') {
                    navigateTo('students');
                }
                const filterInput = document.getElementById('studentSearchFilter');
                if (filterInput) {
                    filterInput.value = val;
                    state.studentPage = 1;
                    loadStudentsData();
                }
            } else {
                clearBtn.style.display = 'none';
            }
        }, 300));

        clearBtn.addEventListener('click', () => {
            searchInput.value = '';
            clearBtn.style.display = 'none';
            const filterInput = document.getElementById('studentSearchFilter');
            if (filterInput) {
                filterInput.value = '';
                state.studentPage = 1;
                loadStudentsData();
            }
        });
    }

    // ==========================================
    // MODAL HELPERS
    // ==========================================
    function setupModals() {
        document.querySelectorAll('[data-close]').forEach(btn => {
            btn.addEventListener('click', () => {
                const modalId = btn.getAttribute('data-close');
                closeModal(modalId);
            });
        });

        // Close on outside overlay click
        document.querySelectorAll('.modal-overlay').forEach(modal => {
            modal.addEventListener('click', (e) => {
                if (e.target === modal) {
                    modal.classList.remove('show');
                }
            });
        });
    }

    function openModal(modalId) {
        const modal = document.getElementById(modalId);
        if (modal) modal.classList.add('show');
    }

    function closeModal(modalId) {
        const modal = document.getElementById(modalId);
        if (modal) modal.classList.remove('show');
    }

    // Debounce Utility
    function debounce(func, wait) {
        let timeout;
        return function (...args) {
            clearTimeout(timeout);
            timeout = setTimeout(() => func.apply(this, args), wait);
        };
    }

    // Start App
    init();
});
