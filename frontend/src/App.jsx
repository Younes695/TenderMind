import { BrowserRouter, Routes, Route } from "react-router-dom";
import Home from "./pages/Home";
import MainLayout from "./pages/Mainlayout";
import Login from "./pages/Login";
import Dashboardlayout from "./pages/Dashboardlayout";
import Dashboard from "./pages/Dashboard";
import GoNoGo from "./pages/GoNoGo";
import NewTender from "./pages/NewTender";
import TenderWorkspace from "./pages/TenderWorkspace";

function App() {
  return (
    <BrowserRouter>
      <Routes>

        <Route element={<MainLayout/>}>

          <Route path="/" element={<Home />} />

          <Route path="/product" element={<div>Product</div>} />
          <Route path="/solutions" element={<div>Solutions</div>} />
          <Route path="/industries" element={<div>Industries</div>} />
          <Route path="/how-it-works" element={<div>How It Works</div>} />
          <Route path="/security" element={<div>Security</div>} />
          <Route path="/pricing" element={<div>Pricing</div>} />

        </Route>
        <Route path="/login" element={<Login/>}/>
        <Route path="/tenders/new" element={<NewTender/>}/>

        <Route element={<Dashboardlayout/>}>
        <Route path="/dashboard" element={<Dashboard/>}/>
        <Route path="/go-no-go" element={<GoNoGo/>}/>
        <Route path="/tenders/RUH-2026-184" element={<TenderWorkspace/>}/>
        
        
        </Route>

      </Routes>
    </BrowserRouter>
  );
}

export default App;