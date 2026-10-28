import { lazy, Suspense } from "react";
import { Navigate, Outlet, Route, Routes } from "react-router-dom";
import { Spinner } from "./components/ui";
import { useAuth } from "./contexts/AuthContext";
import AppLayout from "./layouts/AppLayout";
import type { Role } from "./types";

const Login = lazy(() => import("./pages/Login"));
const Register = lazy(() => import("./pages/Register"));
const Dashboard = lazy(() => import("./pages/Dashboard"));
const Inspect = lazy(() => import("./pages/Inspect"));
const Camera = lazy(() => import("./pages/Camera"));
const Batch = lazy(() => import("./pages/Batch"));
const History = lazy(() => import("./pages/History"));
const InspectionDetail = lazy(() => import("./pages/InspectionDetail"));
const Analytics = lazy(() => import("./pages/Analytics"));
const Reviews = lazy(() => import("./pages/Reviews"));
const Reports = lazy(() => import("./pages/Reports"));
const Products = lazy(() => import("./pages/Products"));
const Models = lazy(() => import("./pages/Models"));
const Audit = lazy(() => import("./pages/Audit"));
const SettingsPage = lazy(() => import("./pages/Settings"));

function Protected({ roles }: { roles?: Role[] }) {
  const { user, loading, has } = useAuth();
  if (loading) return <Spinner label="Checking session" />;
  if (!user) return <Navigate to="/login" replace />;
  if (roles && !has(...roles)) return <div className="glass p-8 text-center text-slate-300">Your role ({user.role}) does not have access to this page.</div>;
  return <Outlet />;
}

export default function App() {
  return (
    <Suspense fallback={<Spinner />}>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
        <Route element={<Protected />}>
          <Route element={<AppLayout />}>
            <Route index element={<Dashboard />} />
            <Route element={<Protected roles={["inspector"]} />}>
              <Route path="inspect" element={<Inspect />} />
              <Route path="camera" element={<Camera />} />
              <Route path="batch" element={<Batch />} />
            </Route>
            <Route path="history" element={<History />} />
            <Route path="history/:id" element={<InspectionDetail />} />
            <Route path="analytics" element={<Analytics />} />
            <Route path="reviews" element={<Reviews />} />
            <Route path="reports" element={<Reports />} />
            <Route path="products" element={<Products />} />
            <Route path="models" element={<Models />} />
            <Route path="audit" element={<Audit />} />
            <Route path="settings" element={<SettingsPage />} />
          </Route>
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Suspense>
  );
}
