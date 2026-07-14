const { createApp, ref } = Vue;

const API = "http://127.0.0.1:5000";

function getToken() {
  return localStorage.getItem("ppa_token") || "";
}

function authHeaders(json = true) {
  const headers = { Authorization: "Bearer " + getToken() };
  if (json) headers["Content-Type"] = "application/json";
  return headers;
}

async function apiFetch(path, options = {}) {
  const opts = { ...options };
  opts.headers = { ...(options.headers || {}), ...authHeaders(!(options.body instanceof FormData)) };
  if (options.body instanceof FormData) {
    delete opts.headers["Content-Type"];
  }
  const res = await fetch(API + path, opts);
  const data = await res.json().catch(() => ({}));
  return { res, data };
}

async function downloadExportFile(filename) {
  const res = await fetch(API + "/api/exports/" + encodeURIComponent(filename), {
    headers: { Authorization: "Bearer " + getToken() }
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.error || "Download failed");
  }
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

// -------------------- Home --------------------
const HomePage = {
  props: ["goTo"],
  template: `
    <div class="row justify-content-center">
      <div class="col-12 text-center mb-4">
        <h1 class="mb-3">Placement Portal Application</h1>
        <p class="text-muted">Campus recruitment portal for Admin, Companies and Students.</p>
      </div>
      <div class="col-md-4 mb-3">
        <div class="card shadow-sm border-0">
          <div class="card-body text-center">
            <h5 class="card-title text-primary">Admin</h5>
            <button class="btn btn-primary" @click="goTo('login', 'admin')">Admin Login</button>
          </div>
        </div>
      </div>
      <div class="col-md-4 mb-3">
        <div class="card shadow-sm border-0">
          <div class="card-body text-center">
            <h5 class="card-title text-success">Company</h5>
            <button class="btn btn-success me-2" @click="goTo('registerCompany')">Register</button>
            <button class="btn btn-outline-success" @click="goTo('login', 'company')">Login</button>
          </div>
        </div>
      </div>
      <div class="col-md-4 mb-3">
        <div class="card shadow-sm border-0">
          <div class="card-body text-center">
            <h5 class="card-title text-info">Student</h5>
            <button class="btn btn-info text-white me-2" @click="goTo('registerStudent')">Register</button>
            <button class="btn btn-outline-info" @click="goTo('login', 'student')">Login</button>
          </div>
        </div>
      </div>
    </div>
  `
};

// -------------------- Login --------------------
const LoginPage = {
  props: ["goTo", "initialRole", "setUser"],
  data() {
    return { role: this.initialRole || "student", email: "", password: "" };
  },
  methods: {
    async performLogin() {
      try {
        const res = await fetch(API + "/api/login", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email: this.email, password: this.password, role: this.role })
        });
        const data = await res.json();
        if (!data.success) {
          alert("Login failed: " + (data.error || "Unknown error"));
          return;
        }
        localStorage.setItem("ppa_token", data.token);
        if (this.setUser) this.setUser(data.user_id, data.role, data.student_name);
        if (data.role === "admin") this.goTo("adminDashboard");
        else if (data.role === "company") this.goTo("companyDashboard");
        else this.goTo("studentDashboard");
      } catch (e) {
        alert("Error calling backend: " + e);
      }
    }
  },
  template: `
    <div class="row justify-content-center">
      <div class="col-md-5">
        <div class="card shadow-sm border-0">
          <div class="card-body">
            <h3 class="mb-3">Login</h3>
            <div class="mb-2">
              <label class="form-label">Role</label>
              <select v-model="role" class="form-select">
                <option value="admin">Admin</option>
                <option value="company">Company</option>
                <option value="student">Student</option>
              </select>
            </div>
            <div class="mb-2">
              <label class="form-label">Email</label>
              <input type="email" class="form-control" v-model="email" required>
            </div>
            <div class="mb-3">
              <label class="form-label">Password</label>
              <input type="password" class="form-control" v-model="password" required>
            </div>
            <button class="btn btn-primary me-2" @click="performLogin">Login</button>
            <button class="btn btn-outline-secondary" @click="goTo('home')">Back</button>
          </div>
        </div>
      </div>
    </div>
  `
};

const RegisterStudent = {
  props: ["goTo"],
  data() {
    return { email: "", password: "", name: "", branch: "", cgpa: "", year: "" };
  },
  methods: {
    async register() {
      try {
        const res = await fetch(API + "/api/register/student", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            email: this.email, password: this.password, name: this.name,
            branch: this.branch, cgpa: parseFloat(this.cgpa || 0), year: parseInt(this.year || 0)
          })
        });
        const data = await res.json();
        if (!data.success) alert(data.error || "Registration failed");
        else { alert("Registered! Please login."); this.goTo("login", "student"); }
      } catch (e) { alert(e); }
    }
  },
  template: `
    <div class="row justify-content-center"><div class="col-md-6">
      <div class="card border-0 shadow-sm"><div class="card-body">
        <h3>Student Register</h3>
        <input class="form-control mb-2" placeholder="Name" v-model="name">
        <input class="form-control mb-2" type="email" placeholder="Email" v-model="email">
        <input class="form-control mb-2" type="password" placeholder="Password" v-model="password">
        <input class="form-control mb-2" placeholder="Branch" v-model="branch">
        <input class="form-control mb-2" type="number" step="0.01" placeholder="CGPA" v-model="cgpa">
        <input class="form-control mb-3" type="number" placeholder="Year (e.g. 3)" v-model="year">
        <button class="btn btn-info text-white me-2" @click="register">Register</button>
        <button class="btn btn-outline-secondary" @click="goTo('home')">Back</button>
      </div></div>
    </div></div>
  `
};

const RegisterCompany = {
  props: ["goTo"],
  data() {
    return { email: "", password: "", company_name: "", hr_contact: "", website: "" };
  },
  methods: {
    async register() {
      try {
        const res = await fetch(API + "/api/register/company", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(this.$data)
        });
        const data = await res.json();
        if (!data.success) alert(data.error || "Registration failed");
        else { alert("Registered! Wait for admin approval, then login."); this.goTo("home"); }
      } catch (e) { alert(e); }
    }
  },
  template: `
    <div class="row justify-content-center"><div class="col-md-6">
      <div class="card border-0 shadow-sm"><div class="card-body">
        <h3>Company Register</h3>
        <input class="form-control mb-2" placeholder="Company Name" v-model="company_name">
        <input class="form-control mb-2" type="email" placeholder="Email" v-model="email">
        <input class="form-control mb-2" type="password" placeholder="Password" v-model="password">
        <input class="form-control mb-2" placeholder="HR Contact" v-model="hr_contact">
        <input class="form-control mb-3" placeholder="Website" v-model="website">
        <button class="btn btn-success me-2" @click="register">Register</button>
        <button class="btn btn-outline-secondary" @click="goTo('home')">Back</button>
      </div></div>
    </div></div>
  `
};

// -------------------- Admin --------------------
const AdminDashboard = {
  props: ["goTo"],
  data() {
    return {
      stats: {}, drives: [], companies: [], students: [], applications: [],
      searchStudents: "", searchCompanies: "", searchDrives: "",
      message: "", selectedApplication: null
    };
  },
  mounted() { this.reloadAll(); },
  methods: {
    logout() {
      localStorage.removeItem("ppa_token");
      this.goTo("home");
    },
    async reloadAll() {
      await Promise.all([
        this.loadStats(), this.loadDrives(), this.loadCompanies(),
        this.loadStudents(), this.loadApplications()
      ]);
    },
    async loadStats() {
      const { data } = await apiFetch("/api/admin/stats");
      if (data.success) this.stats = data.stats;
    },
    async loadDrives() {
      const { data } = await apiFetch("/api/admin/drives?search=" + encodeURIComponent(this.searchDrives));
      if (data.success) this.drives = data.drives;
    },
    async loadCompanies() {
      const { data } = await apiFetch("/api/admin/companies?search=" + encodeURIComponent(this.searchCompanies));
      if (data.success) this.companies = data.companies;
    },
    async loadStudents() {
      const { data } = await apiFetch("/api/admin/students?search=" + encodeURIComponent(this.searchStudents));
      if (data.success) this.students = data.students;
    },
    async loadApplications() {
      const { data } = await apiFetch("/api/admin/applications");
      if (data.success) this.applications = data.applications;
    },
    async approveDrive(id) {
      await apiFetch("/api/admin/approve_drive", { method: "POST", body: JSON.stringify({ drive_id: id }) });
      this.loadDrives(); this.loadStats();
    },
    async rejectDrive(id) {
      await apiFetch("/api/admin/reject_drive", { method: "POST", body: JSON.stringify({ drive_id: id }) });
      this.loadDrives(); this.loadStats();
    },
    async approveCompany(id) {
      await apiFetch("/api/admin/approve_company", { method: "POST", body: JSON.stringify({ company_id: id }) });
      this.loadCompanies(); this.loadStats();
    },
    async rejectCompany(id) {
      await apiFetch("/api/admin/reject_company", { method: "POST", body: JSON.stringify({ company_id: id }) });
      this.loadCompanies();
    },
    async blacklistCompany(id) {
      if (!confirm("Blacklist this company?")) return;
      await apiFetch("/api/admin/blacklist_company", { method: "POST", body: JSON.stringify({ company_id: id }) });
      this.loadCompanies(); this.loadDrives();
    },
    async blacklistStudent(id) {
      if (!confirm("Blacklist this student?")) return;
      await apiFetch("/api/admin/blacklist_student", { method: "POST", body: JSON.stringify({ student_profile_id: id }) });
      this.loadStudents();
    },
    async runReminders() {
      const { data } = await apiFetch("/api/jobs/run_daily_reminders", { method: "POST", body: "{}" });
      this.message = data.success
        ? (data.message || "Daily reminders job triggered. Check backend/notifications/")
        : (data.error || "Failed");
    },
    async runMonthly() {
      const { data } = await apiFetch("/api/jobs/run_monthly_report", { method: "POST", body: "{}" });
      this.message = data.success
        ? (data.message || "Monthly report job triggered. Check backend/notifications/")
        : (data.error || "Failed");
    }
  },
  template: `
    <div>
      <div class="d-flex justify-content-between align-items-center mb-3">
        <h2>Admin Dashboard</h2>
        <button class="btn btn-outline-danger btn-sm" @click="logout">Logout</button>
      </div>
      <div v-if="message" class="alert alert-info">{{ message }}</div>

      <div class="row g-3 mb-3">
        <div class="col-md-3"><div class="card border-0 shadow-sm"><div class="card-body text-center">
          <div class="text-muted small">Students</div><h3>{{ stats.students || 0 }}</h3>
        </div></div></div>
        <div class="col-md-3"><div class="card border-0 shadow-sm"><div class="card-body text-center">
          <div class="text-muted small">Companies</div><h3>{{ stats.companies || 0 }}</h3>
        </div></div></div>
        <div class="col-md-3"><div class="card border-0 shadow-sm"><div class="card-body text-center">
          <div class="text-muted small">Drives</div><h3>{{ stats.drives || 0 }}</h3>
        </div></div></div>
        <div class="col-md-3"><div class="card border-0 shadow-sm"><div class="card-body text-center">
          <div class="text-muted small">Applications</div><h3>{{ stats.applications || 0 }}</h3>
        </div></div></div>
      </div>

      <div class="mb-3">
        <button class="btn btn-sm btn-outline-primary me-2" @click="runReminders">Run daily reminders</button>
        <button class="btn btn-sm btn-outline-secondary" @click="runMonthly">Run monthly report</button>
      </div>

      <div class="row g-3">
        <div class="col-md-6">
          <div class="card border-0 shadow-sm mb-3">
            <div class="card-header bg-primary text-white">Placement Drives</div>
            <div class="card-body p-2">
              <div class="input-group input-group-sm mb-2">
                <input class="form-control" v-model="searchDrives" placeholder="Search drives">
                <button class="btn btn-outline-secondary" @click="loadDrives">Search</button>
              </div>
              <table class="table table-sm mb-0">
                <thead><tr><th>ID</th><th>Company</th><th>Title</th><th>Status</th><th></th></tr></thead>
                <tbody>
                  <tr v-for="d in drives" :key="d.drive_id">
                    <td>{{ d.drive_id }}</td><td>{{ d.company_name }}</td><td>{{ d.job_title }}</td>
                    <td>{{ d.status }}</td>
                    <td>
                      <button v-if="d.status==='pending'" class="btn btn-success btn-sm me-1" @click="approveDrive(d.drive_id)">Approve</button>
                      <button v-if="d.status==='pending'" class="btn btn-warning btn-sm" @click="rejectDrive(d.drive_id)">Reject</button>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>

        <div class="col-md-6">
          <div class="card border-0 shadow-sm mb-3">
            <div class="card-header bg-success text-white">Companies</div>
            <div class="card-body p-2">
              <div class="input-group input-group-sm mb-2">
                <input class="form-control" v-model="searchCompanies" placeholder="Search companies">
                <button class="btn btn-outline-secondary" @click="loadCompanies">Search</button>
              </div>
              <div v-for="c in companies" :key="c.company_id" class="d-flex justify-content-between align-items-center border rounded mb-1 px-2 py-1">
                <span>{{ c.company_name }} <span class="badge bg-secondary">{{ c.status }}</span></span>
                <span>
                  <button v-if="c.status==='pending'" class="btn btn-sm btn-success me-1" @click="approveCompany(c.company_id)">Approve</button>
                  <button v-if="c.status==='pending'" class="btn btn-sm btn-warning me-1" @click="rejectCompany(c.company_id)">Reject</button>
                  <button class="btn btn-sm btn-outline-danger" @click="blacklistCompany(c.company_id)">Blacklist</button>
                </span>
              </div>
            </div>
          </div>

          <div class="card border-0 shadow-sm">
            <div class="card-header bg-danger text-white">Students</div>
            <div class="card-body p-2">
              <div class="input-group input-group-sm mb-2">
                <input class="form-control" v-model="searchStudents" placeholder="Search students">
                <button class="btn btn-outline-secondary" @click="loadStudents">Search</button>
              </div>
              <div v-for="s in students" :key="s.student_profile_id" class="d-flex justify-content-between align-items-center border rounded mb-1 px-2 py-1">
                <span>{{ s.name }} ({{ s.branch }}) <span v-if="!s.is_active" class="badge bg-danger">blacklisted</span></span>
                <button class="btn btn-sm btn-outline-danger" :disabled="!s.is_active" @click="blacklistStudent(s.student_profile_id)">Blacklist</button>
              </div>
            </div>
          </div>
        </div>

        <div class="col-12">
          <div class="card border-0 shadow-sm">
            <div class="card-header bg-secondary text-white">Student Applications</div>
            <div class="card-body p-2">
              <table class="table table-sm mb-0">
                <thead><tr><th>#</th><th>Student</th><th>Company</th><th>Drive</th><th>Status</th><th>Date</th></tr></thead>
                <tbody>
                  <tr v-for="a in applications" :key="a.application_id">
                    <td>{{ a.application_id }}</td>
                    <td>{{ a.student_name }}</td>
                    <td>{{ a.company_name }}</td>
                    <td>{{ a.job_title }}</td>
                    <td>{{ a.status }}</td>
                    <td>{{ a.applied_on }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    </div>
  `
};

// -------------------- Company --------------------
const CompanyDashboard = {
  props: ["goTo"],
  data() {
    return {
      profile: null, upcomingDrives: [], closedDrives: [], applications: [],
      selectedDriveId: null, message: "",
      jobTitle: "", jobDescription: "", eligibilityBranch: "",
      eligibilityCgpa: "", eligibilityYear: "", applicationDeadline: "",
      interviewDate: {}, interviewNotes: {}
    };
  },
  mounted() { this.reload(); },
  methods: {
    logout() { localStorage.removeItem("ppa_token"); this.goTo("home"); },
    async reload() {
      await Promise.all([this.loadProfile(), this.loadDrives(), this.loadApplications()]);
    },
    async loadProfile() {
      const { data } = await apiFetch("/api/company/profile");
      if (data.success) this.profile = data.profile;
    },
    async loadDrives() {
      const { data } = await apiFetch("/api/company/drives");
      if (data.success) {
        this.upcomingDrives = data.upcoming_drives || [];
        this.closedDrives = data.closed_drives || [];
      } else this.message = data.error || "Failed to load drives";
    },
    async loadApplications(driveId) {
      const q = driveId ? ("?drive_id=" + driveId) : "";
      const { data } = await apiFetch("/api/company/applications" + q);
      if (data.success) this.applications = data.applications || [];
    },
    async createDrive() {
      const { data } = await apiFetch("/api/company/create_drive", {
        method: "POST",
        body: JSON.stringify({
          job_title: this.jobTitle,
          job_description: this.jobDescription,
          eligibility_branch: this.eligibilityBranch,
          eligibility_cgpa: parseFloat(this.eligibilityCgpa || 0),
          eligibility_year: parseInt(this.eligibilityYear || 0),
          application_deadline: this.applicationDeadline
        })
      });
      if (!data.success) { this.message = data.error || "Create failed"; return; }
      this.message = "Drive created (pending admin approval).";
      this.jobTitle = this.jobDescription = this.eligibilityBranch = "";
      this.eligibilityCgpa = this.eligibilityYear = this.applicationDeadline = "";
      this.loadDrives();
    },
    async markAsComplete(driveId) {
      const { data } = await apiFetch("/api/company/close_drive", {
        method: "POST", body: JSON.stringify({ drive_id: driveId })
      });
      if (!data.success) this.message = data.error || "Close failed";
      else { this.message = "Drive closed."; this.loadDrives(); }
    },
    viewDriveDetails(d) {
      this.selectedDriveId = d.id;
      this.loadApplications(d.id);
    },
    async updateApp(appId, status) {
      const { data } = await apiFetch("/api/company/update_application", {
        method: "POST",
        body: JSON.stringify({
          application_id: appId,
          status,
          interview_date: this.interviewDate[appId] || null,
          interview_notes: this.interviewNotes[appId] || null
        })
      });
      if (!data.success) alert(data.error || "Update failed");
      else this.loadApplications(this.selectedDriveId);
    }
  },
  template: `
    <div>
      <div class="d-flex justify-content-between align-items-center mb-3">
        <h2>Company Dashboard</h2>
        <button class="btn btn-outline-danger btn-sm" @click="logout">Logout</button>
      </div>
      <div v-if="message" class="alert alert-info">{{ message }}</div>

      <div class="card border-0 shadow-sm mb-3" v-if="profile">
        <div class="card-body">
          <strong>{{ profile.company_name }}</strong>
          — {{ profile.approval_status }} | HR: {{ profile.hr_contact }} | {{ profile.website }}
        </div>
      </div>

      <div class="row g-3">
        <div class="col-md-6">
          <div class="card border-0 shadow-sm mb-3">
            <div class="card-header bg-primary text-white">Upcoming Drives</div>
            <div class="card-body p-2">
              <table class="table table-sm" v-if="upcomingDrives.length">
                <thead><tr><th>Title</th><th>Status</th><th>Applicants</th><th></th></tr></thead>
                <tbody>
                  <tr v-for="d in upcomingDrives" :key="d.id">
                    <td>{{ d.job_title }}</td><td>{{ d.status }}</td><td>{{ d.applicant_count }}</td>
                    <td>
                      <button class="btn btn-sm btn-outline-primary me-1" @click="viewDriveDetails(d)">Applications</button>
                      <button class="btn btn-sm btn-outline-success" @click="markAsComplete(d.id)">Complete</button>
                    </td>
                  </tr>
                </tbody>
              </table>
              <p class="text-muted small mb-0" v-else>No upcoming drives.</p>
            </div>
          </div>
          <div class="card border-0 shadow-sm">
            <div class="card-header bg-secondary text-white">Closed Drives</div>
            <div class="card-body p-2">
              <div v-for="d in closedDrives" :key="d.id" class="mb-1">
                {{ d.job_title }} ({{ d.applicant_count }} applicants)
                <button class="btn btn-sm btn-outline-secondary ms-2" @click="viewDriveDetails(d)">View</button>
              </div>
              <p class="text-muted small mb-0" v-if="!closedDrives.length">No closed drives.</p>
            </div>
          </div>
        </div>

        <div class="col-md-6">
          <div class="card border-0 shadow-sm mb-3">
            <div class="card-header bg-success text-white">Create Drive</div>
            <div class="card-body">
              <input class="form-control mb-2" placeholder="Job Title" v-model="jobTitle">
              <textarea class="form-control mb-2" rows="2" placeholder="Description" v-model="jobDescription"></textarea>
              <input class="form-control mb-2" placeholder="Branches (CSE, IT)" v-model="eligibilityBranch">
              <input class="form-control mb-2" type="number" step="0.01" placeholder="Min CGPA" v-model="eligibilityCgpa">
              <input class="form-control mb-2" type="number" placeholder="Year" v-model="eligibilityYear">
              <input class="form-control mb-3" type="date" v-model="applicationDeadline">
              <button class="btn btn-success" @click="createDrive">Save Drive</button>
            </div>
          </div>
        </div>

        <div class="col-12">
          <div class="card border-0 shadow-sm">
            <div class="card-header bg-dark text-white">Applications {{ selectedDriveId ? ('for drive #' + selectedDriveId) : '' }}</div>
            <div class="card-body p-2">
              <table class="table table-sm" v-if="applications.length">
                <thead><tr><th>Student</th><th>Branch</th><th>CGPA</th><th>Drive</th><th>Status</th><th>Interview</th><th>Actions</th></tr></thead>
                <tbody>
                  <tr v-for="a in applications" :key="a.application_id">
                    <td>{{ a.student_name }}</td>
                    <td>{{ a.branch }}</td>
                    <td>{{ a.cgpa }}</td>
                    <td>{{ a.job_title }}</td>
                    <td>{{ a.status }}</td>
                    <td>
                      <input type="date" class="form-control form-control-sm mb-1" v-model="interviewDate[a.application_id]">
                      <input class="form-control form-control-sm" placeholder="Notes" v-model="interviewNotes[a.application_id]">
                    </td>
                    <td>
                      <button class="btn btn-sm btn-outline-primary me-1" @click="updateApp(a.application_id, 'shortlisted')">Shortlist</button>
                      <button class="btn btn-sm btn-outline-success me-1" @click="updateApp(a.application_id, 'selected')">Select</button>
                      <button class="btn btn-sm btn-outline-danger" @click="updateApp(a.application_id, 'rejected')">Reject</button>
                    </td>
                  </tr>
                </tbody>
              </table>
              <p class="text-muted small mb-0" v-else>No applications yet. Click Applications on a drive.</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  `
};

// -------------------- Student --------------------
const StudentDashboard = {
  props: ["goTo"],
  data() {
    return { drives: [], search: "", loading: false, error: null, message: "" };
  },
  mounted() { this.loadDrives(); },
  methods: {
    logout() { localStorage.removeItem("ppa_token"); this.goTo("home"); },
    async loadDrives() {
      this.loading = true;
      this.error = null;
      try {
        const { data } = await apiFetch("/api/student/drives?search=" + encodeURIComponent(this.search));
        if (!data.success) this.error = data.error || "Failed";
        else this.drives = data.drives || [];
      } catch (e) { this.error = String(e); }
      finally { this.loading = false; }
    },
    async applyToDrive(id) {
      const { data } = await apiFetch("/api/student/apply_drive", {
        method: "POST", body: JSON.stringify({ drive_id: id })
      });
      alert(data.success ? "Applied successfully!" : (data.error || "Failed"));
    },
    async exportCsv() {
      const { data } = await apiFetch("/api/student/export_csv", { method: "POST", body: "{}" });
      if (!data.success) { alert(data.error || "Export failed"); return; }

      let filename = data.filename || null;
      if (!filename && data.task_id) {
        this.message = "Export started. Waiting for completion...";
        for (let i = 0; i < 40; i++) {
          await new Promise((r) => setTimeout(r, 750));
          const st = await apiFetch("/api/student/export_status/" + data.task_id);
          if (st.data.status === "SUCCESS" && st.data.result && st.data.result.filename) {
            filename = st.data.result.filename;
            break;
          }
          if (st.data.status === "FAILURE") {
            alert("Export failed");
            return;
          }
        }
      }

      if (!filename) {
        this.message = "Export is still processing. Check backend/notifications/ for the alert file.";
        alert(this.message);
        return;
      }

      try {
        await downloadExportFile(filename);
        this.message = "CSV ready and downloaded: " + filename + ". Alert also saved under backend/notifications/.";
        alert(this.message);
      } catch (e) {
        this.message = "Export file ready (" + filename + ") but download failed: " + e.message;
        alert(this.message);
      }
    }
  },
  template: `
    <div>
      <div class="d-flex justify-content-between align-items-center mb-3">
        <h2>Student Dashboard</h2>
        <div>
          <button class="btn btn-outline-secondary btn-sm me-2" @click="goTo('studentProfileEdit')">Profile / Resume</button>
          <button class="btn btn-outline-primary btn-sm me-2" @click="goTo('studentHistory')">History</button>
          <button class="btn btn-outline-success btn-sm me-2" @click="exportCsv">Export CSV</button>
          <button class="btn btn-outline-danger btn-sm" @click="logout">Logout</button>
        </div>
      </div>
      <div v-if="message" class="alert alert-info">{{ message }}</div>
      <div class="input-group mb-3">
        <input class="form-control" v-model="search" placeholder="Search drives or companies">
        <button class="btn btn-outline-secondary" @click="loadDrives">Search</button>
      </div>
      <div v-if="loading" class="alert alert-info">Loading...</div>
      <div v-if="error" class="alert alert-danger">{{ error }}</div>
      <div class="card border-0 shadow-sm" v-if="!loading && !error">
        <div class="card-header bg-success text-white">Approved drives (eligibility filtered)</div>
        <div class="card-body p-2">
          <table class="table table-sm mb-0">
            <thead><tr><th>Job</th><th>Company</th><th>Deadline</th><th></th></tr></thead>
            <tbody>
              <tr v-if="!drives.length"><td colspan="4" class="text-center text-muted">No drives</td></tr>
              <tr v-for="d in drives" :key="d.id">
                <td>{{ d.job_title }}</td><td>{{ d.company_name }}</td><td>{{ d.application_deadline }}</td>
                <td><button class="btn btn-sm btn-outline-primary" @click="applyToDrive(d.id)">Apply</button></td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  `
};

const StudentHistory = {
  props: ["goTo"],
  data() { return { applications: [], error: null }; },
  async mounted() {
    const { data } = await apiFetch("/api/student/applications");
    if (!data.success) this.error = data.error;
    else this.applications = data.applications || [];
  },
  template: `
    <div>
      <div class="d-flex justify-content-between mb-3">
        <h2>Application History</h2>
        <button class="btn btn-outline-secondary btn-sm" @click="goTo('studentDashboard')">Back</button>
      </div>
      <div v-if="error" class="alert alert-danger">{{ error }}</div>
      <table class="table table-sm">
        <thead><tr><th>Job</th><th>Company</th><th>Status</th><th>Applied</th><th>Interview</th></tr></thead>
        <tbody>
          <tr v-for="a in applications" :key="a.application_id">
            <td>{{ a.job_title }}</td><td>{{ a.company_name }}</td>
            <td>{{ a.status }}</td><td>{{ a.applied_on }}</td><td>{{ a.interview_date || '-' }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  `
};

const StudentProfileEdit = {
  props: ["goTo"],
  data() {
    return { full_name: "", branch: "", cgpa: "", year: "", resume_path: "", message: "", file: null };
  },
  async mounted() {
    const { data } = await apiFetch("/api/student/profile");
    if (data.success) {
      this.full_name = data.profile.full_name || "";
      this.branch = data.profile.branch || "";
      this.cgpa = data.profile.cgpa || "";
      this.year = data.profile.year || "";
      this.resume_path = data.profile.resume_path || "";
    }
  },
  methods: {
    onFile(e) { this.file = e.target.files[0]; },
    async save() {
      const { data } = await apiFetch("/api/student/profile/update", {
        method: "POST",
        body: JSON.stringify({
          full_name: this.full_name, branch: this.branch,
          cgpa: parseFloat(this.cgpa || 0), year: parseInt(this.year || 0)
        })
      });
      this.message = data.success ? "Profile saved." : (data.error || "Failed");
    },
    async uploadResume() {
      if (!this.file) { alert("Choose a file"); return; }
      const fd = new FormData();
      fd.append("resume", this.file);
      const { data } = await apiFetch("/api/student/resume", { method: "POST", body: fd });
      if (data.success) {
        this.resume_path = data.resume_path;
        this.message = "Resume uploaded.";
      } else this.message = data.error || "Upload failed";
    }
  },
  template: `
    <div class="row justify-content-center"><div class="col-md-6">
      <div class="card border-0 shadow-sm"><div class="card-body">
        <h3>Edit Profile</h3>
        <div v-if="message" class="alert alert-info">{{ message }}</div>
        <input class="form-control mb-2" v-model="full_name" placeholder="Full name">
        <input class="form-control mb-2" v-model="branch" placeholder="Branch">
        <input class="form-control mb-2" v-model="cgpa" placeholder="CGPA">
        <input class="form-control mb-3" v-model="year" placeholder="Year">
        <button class="btn btn-primary mb-3" @click="save">Save</button>
        <hr>
        <p class="small text-muted">Current resume: {{ resume_path || 'None' }}</p>
        <input type="file" class="form-control mb-2" @change="onFile">
        <button class="btn btn-success me-2" @click="uploadResume">Upload Resume</button>
        <button class="btn btn-outline-secondary" @click="goTo('studentDashboard')">Back</button>
      </div></div>
    </div></div>
  `
};

const app = createApp({
  setup() {
    const currentView = ref("HomePage");
    const initialRole = ref(null);
    const currentUserId = ref(null);
    const currentUserRole = ref(null);

    function goTo(page, role) {
      const map = {
        home: "HomePage",
        login: "LoginPage",
        registerStudent: "RegisterStudent",
        registerCompany: "RegisterCompany",
        adminDashboard: "AdminDashboard",
        companyDashboard: "CompanyDashboard",
        studentDashboard: "StudentDashboard",
        studentHistory: "StudentHistory",
        studentProfileEdit: "StudentProfileEdit"
      };
      if (page === "home") {
        localStorage.removeItem("ppa_token");
        currentUserId.value = null;
        currentUserRole.value = null;
      }
      currentView.value = map[page] || "HomePage";
      initialRole.value = role || null;
    }

    function setUser(id, role) {
      currentUserId.value = id;
      currentUserRole.value = role;
    }

    return { currentView, initialRole, currentUserId, currentUserRole, goTo, setUser };
  },
  components: {
    HomePage, LoginPage, RegisterStudent, RegisterCompany,
    AdminDashboard, CompanyDashboard, StudentDashboard, StudentHistory, StudentProfileEdit
  },
  template: `
    <component
      :is="currentView"
      :goTo="goTo"
      :initialRole="initialRole"
      :setUser="setUser"
      :currentUserId="currentUserId"
    />
  `
});

app.mount("#app");
