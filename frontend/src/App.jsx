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
import DecisionPack from "./pages/DecisionPack";
import { Approvals, WorkPackages, DocumentsLibrary, Analytics } from "./pages/Portfolio";
import Help from "./pages/Help";
import Solutions from "./pages/Solution";
import Industries from "./pages/Industries";
import Security from "./pages/Security";
import Pricing from "./pages/Pricing";
import ProtectedRoute from "./components/ProtectedRoute";
import TendersList from "./pages/TendersList";
import CompanyKnowledge from "./pages/CompanyKnowledge";
import ComingSoon from "./pages/ComingSoon";
import Notifications from "./pages/Notifications";
import QA from "./pages/QA";
import News from "./pages/News";
import Subcontractors from "./pages/Subcontractors";
import Settings from "./pages/Settings";

// Sidebar sections that are planned but not built yet.
const PLANNED_SECTIONS = [];

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
            Previously these routes were reachable with no login at all - ProtectedRoute
            existed in the codebase but was never wired into the router. */}
        <Route element={<ProtectedRoute/>}>
          <Route path="/tenders/new" element={<NewTender/>}/>
          <Route path="/tenders/:tender_id/pack" element={<DecisionPack/>}/>
          <Route element={<Dashboardlayout/>}>
            <Route path="/dashboard" element={<Dashboard/>}/>
            <Route path="/go-no-go" element={<GoNoGo/>}/>
            <Route path="/tenders" element={<TendersList/>}/>
            <Route path="/tenders/:tender_id" element={<TenderWorkspace/>}/>
            <Route path="/company-knowledge" element={<CompanyKnowledge/>}/>
            <Route path="/notifications" element={<Notifications/>}/>
            <Route path="/qa" element={<QA/>}/>
            <Route path="/news" element={<News/>}/>
            <Route path="/subcontractors" element={<Subcontractors/>}/>
            <Route path="/settings" element={<Settings/>}/>
            <Route path="/work-packages" element={<WorkPackages/>}/>
            <Route path="/approvals" element={<Approvals/>}/>
            <Route path="/documents" element={<DocumentsLibrary/>}/>
            <Route path="/analytics" element={<Analytics/>}/>
            <Route path="/help" element={<Help/>}/>
            {PLANNED_SECTIONS.map(([path, title, description]) => (
              <Route key={path} path={path} element={<ComingSoon title={title} description={description}/>}/>
            ))}
          </Route>
        </Route>

        <Route path="*" element={<ComingSoon title="Page not found" description="This address does not exist. Use the menu or go back to the dashboard."/>}/>
      </Routes>
    </BrowserRouter>
  );
}

export default App;
