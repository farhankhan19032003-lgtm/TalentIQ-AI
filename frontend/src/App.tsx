import { Navigate, Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import Jobs from "./pages/Jobs";
import JobEditor from "./pages/JobEditor";
import Upload from "./pages/Upload";
import Resumes from "./pages/Resumes";
import Ranking from "./pages/Ranking";
import Candidate from "./pages/Candidate";
import Compare from "./pages/Compare";
import Analytics from "./pages/Analytics";
import WhatIf from "./pages/WhatIf";
import SettingsPage from "./pages/SettingsPage";
import Pipeline from "./pages/Pipeline";
import Matrix from "./pages/Matrix";

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route element={<Layout />}>
        <Route path="/" element={<Dashboard />} />
        <Route path="/jobs" element={<Jobs />} />
        <Route path="/jobs/new" element={<JobEditor />} />
        <Route path="/jobs/:id" element={<JobEditor />} />
        <Route path="/upload" element={<Upload />} />
        <Route path="/resumes" element={<Resumes />} />
        <Route path="/ranking" element={<Ranking />} />
        <Route path="/pipeline" element={<Pipeline />} />
        <Route path="/matrix" element={<Matrix />} />
        <Route path="/candidates/:id" element={<Candidate />} />
        <Route path="/compare" element={<Compare />} />
        <Route path="/analytics" element={<Analytics />} />
        <Route path="/whatif" element={<WhatIf />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
