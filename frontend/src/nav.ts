import { BarChart3, Briefcase, Columns3, FileUp, FlaskConical, Grid3x3, Home, Settings, Trophy, Users } from "lucide-react";

export const NAV = [
  { to: "/", label: "Dashboard", icon: Home },
  { to: "/jobs", label: "Jobs", icon: Briefcase },
  { to: "/upload", label: "Upload resumes", icon: FileUp },
  { to: "/resumes", label: "Resume batches", icon: Users },
  { to: "/ranking", label: "Ranking", icon: Trophy },
  { to: "/pipeline", label: "Pipeline board", icon: Columns3 },
  { to: "/matrix", label: "Talent matrix", icon: Grid3x3 },
  { to: "/analytics", label: "Analytics", icon: BarChart3 },
  { to: "/whatif", label: "What-if", icon: FlaskConical },
  { to: "/settings", label: "Settings & audit", icon: Settings },
];
