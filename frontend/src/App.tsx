import { Route, Routes } from "react-router-dom";
import { ProtectedRoute, RoleRoute } from "./auth/guards";
import AppShell from "./components/layout/AppShell";
import HomeRedirect from "./pages/HomeRedirect";
import Login from "./pages/Login";
import NotFound from "./pages/NotFound";
import Register from "./pages/Register";
import AdminHome from "./pages/admin/AdminHome";
import VerificationReview from "./pages/admin/VerificationReview";
import AuditLogs from "./pages/admin/AuditLogs";
import ReportsModeration from "./pages/admin/ReportsModeration";
import StudentHome from "./pages/student/StudentHome";
import JobDiscovery from "./pages/student/JobDiscovery";
import JobDetail from "./pages/student/JobDetail";
import MyApplications from "./pages/student/MyApplications";
import ProfileEditor from "./pages/student/ProfileEditor";
import BusinessHome from "./pages/business/BusinessHome";
import MyJobs from "./pages/business/MyJobs";
import JobEditor from "./pages/business/JobEditor";
import Applicants from "./pages/business/Applicants";
import VerificationWizard from "./pages/business/VerificationWizard";
import BusinessProfileEditor from "./pages/business/BusinessProfileEditor";
import Recommendations from "./pages/student/Recommendations";
import Messages from "./pages/shared/Messages";
import Interviews from "./pages/shared/Interviews";
import Notifications from "./pages/shared/Notifications";

/**
 * Route architecture (F1):
 *   public: /login /register
 *   protected + shell: /student/* (student only), /business/* (business only),
 *                      /admin/* (admin only) — each role subtree gets its own
 *                      nested routes in F2–F5.
 */
export default function App() {
  return (
    <Routes>
      <Route path="/" element={<HomeRedirect />} />
      <Route path="/redirect" element={<HomeRedirect />} />
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />

      <Route element={<ProtectedRoute />}>
        <Route element={<AppShell />}>
          <Route element={<RoleRoute allow={["student"]} />}>
            <Route path="/student" element={<StudentHome />} />
            <Route path="/student/jobs" element={<JobDiscovery />} />
            <Route path="/student/jobs/:id" element={<JobDetail />} />
            <Route path="/student/recommendations" element={<Recommendations />} />
            <Route path="/student/applications" element={<MyApplications />} />
            <Route path="/student/profile" element={<ProfileEditor />} />
          </Route>
          {/* Shared F4 routes: both roles reach the same thread/inbox. */}
          <Route element={<RoleRoute allow={["student", "business"]} />}>
            <Route path="/messages" element={<Messages />} />
            <Route path="/interviews" element={<Interviews />} />
            <Route path="/notifications" element={<Notifications />} />
          </Route>
          <Route element={<RoleRoute allow={["business"]} />}>
            <Route path="/business" element={<BusinessHome />} />
            <Route path="/business/jobs" element={<MyJobs />} />
            <Route path="/business/jobs/new" element={<JobEditor />} />
            <Route path="/business/jobs/:id/edit" element={<JobEditor />} />
            <Route path="/business/jobs/:id/applicants" element={<Applicants />} />
            <Route path="/business/applicants" element={<Applicants />} />
            <Route path="/business/verification" element={<VerificationWizard />} />
            <Route path="/business/profile" element={<BusinessProfileEditor />} />
          </Route>
          <Route element={<RoleRoute allow={["admin"]} />}>
            <Route path="/admin" element={<AdminHome />} />
            <Route path="/admin/verifications" element={<VerificationReview />} />
            <Route path="/admin/audit-logs" element={<AuditLogs />} />
            <Route path="/admin/reports" element={<ReportsModeration />} />
          </Route>
        </Route>
      </Route>

      <Route path="*" element={<NotFound />} />
    </Routes>
  );
}
