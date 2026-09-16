import { Route, Routes } from "react-router-dom";
import { ProtectedRoute, RoleRoute } from "./auth/guards";
import AppShell from "./components/layout/AppShell";
import HomeRedirect from "./pages/HomeRedirect";
import Login from "./pages/Login";
import NotFound from "./pages/NotFound";
import Register from "./pages/Register";
import AdminHome from "./pages/admin/AdminHome";
import BusinessHome from "./pages/business/BusinessHome";
import StudentHome from "./pages/student/StudentHome";
import JobDiscovery from "./pages/student/JobDiscovery";
import JobDetail from "./pages/student/JobDetail";
import MyApplications from "./pages/student/MyApplications";
import ProfileEditor from "./pages/student/ProfileEditor";

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
            <Route path="/student/applications" element={<MyApplications />} />
            <Route path="/student/profile" element={<ProfileEditor />} />
          </Route>
          <Route element={<RoleRoute allow={["business"]} />}>
            <Route path="/business" element={<BusinessHome />} />
          </Route>
          <Route element={<RoleRoute allow={["admin"]} />}>
            <Route path="/admin" element={<AdminHome />} />
          </Route>
        </Route>
      </Route>

      <Route path="*" element={<NotFound />} />
    </Routes>
  );
}
