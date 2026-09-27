import { BrowserRouter, Routes, Route } from "react-router-dom";
import Home from "./pages/Home";
import MainLayout from "./pages/Mainlayout";
import Login from "./pages/Login";
import Signup from "./pages/Signup";
import Dashboardlayout from "./pages/Dashboardlayout";
import Dashboard from "./pages/Dashboard";
import GoNoGo from "./pages/GoNoGo";
import NewTender from "./pages/NewTender";
import TenderWorkspace from "./pages/TenderWorkspace";
import Solutions from "./pages/Solution";
import Industries from "./pages/Industries";
import Security from "./pages/Security";
import Pricing from "./pages/Pricing";
import ProtectedRoute from "./components/ProtectedRoute";
import TendersList from "./pages/TendersList";
import CompanyKnowledge from "./pages/CompanyKnowledge";
import ComingSoon from "./pages/ComingSoon";

// Sidebar sections that are planned but not built yet.
const PLANNED_SECTIONS = [
  ["/work-packages", "Work Packages", "Split a tender into packages of work with owners and due dates."],
  ["/qa", "Q&A", "Track clarification questions sent to the client and their answers."],
  ["/approvals", "Approvals", "Route the bid decision through management approval with an audit trail."],
  ["/documents", "Documents", "One library of every tender document across all tenders."],
  ["/subcontractors", "Subcontractors", "Manage subcontractor RFQs and their quotes per work package."],
  ["/analytics", "Analytics", "Win rate, bid pipeline and effort per tender over time."],
  ["/notifications", "Notifications", "Deadlines, finished processing jobs and approval requests in one place."],
  ["/help", "Help", "Guides for uploading tenders, company evidence and reading the bid decision."],
  ["/settings", "Settings", "Account, team members, subscription plan and upload limits."],
];

function App() {
  return (
    <BrowserRouter>
      <Routes>

        <Route element={<MainLayout/>}>

          <Route path="/" element={<Home />} />

          <Route path="/product" element={<div>Product</div>} />
          <Route path="/solutions" element={<Solutions />} />
          <Route path="/industries" element={<Industries />} />
          <Route path="/how-it-works" element={<div>How It Works</div>} />
          <Route path="/security" element={<Security/>} />
          <Route path="/pricing" element={<Pricing/>} />

        </Route>
        <Route path="/login" element={<Login/>}/>
        <Route path="/signup" element={<Signup/>}/>

        {/* Everything below requires a valid session (checked via GET /api/auth/me).
            Previously these routes were reachable with no login at all — ProtectedRoute
            existed in the codebase but was never wired into the router. */}
        <Route element={<ProtectedRoute/>}>
          <Route path="/tenders/new" element={<NewTender/>}/>
          <Route element={<Dashboardlayout/>}>
            <Route path="/dashboard" element={<Dashboard/>}/>
            <Route path="/go-no-go" element={<GoNoGo/>}/>
            <Route path="/tenders" element={<TendersList/>}/>
            <Route path="/tenders/:tender_id" element={<TenderWorkspace/>}/>
            <Route path="/company-knowledge" element={<CompanyKnowledge/>}/>
            {PLANNED_SECTIONS.map(([path, title, description]) => (
              <Route key={path} path={path} element={<ComingSoon title={title} description={description}/>}/>
            ))}
          </Route>
        </Route>

      </Routes>
    </BrowserRouter>
  );
}

export default App;
