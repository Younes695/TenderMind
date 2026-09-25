import { BrowserRouter, Routes, Route } from "react-router-dom";
import Home from "./pages/Home";
import MainLayout from "./pages/Mainlayout";
import Login from "./pages/Login";
import Dashboardlayout from "./pages/Dashboardlayout";
import Dashboard from "./pages/Dashboard";
import GoNoGo from "./pages/GoNoGo";
import NewTender from "./pages/NewTender";
import TenderWorkspace from "./pages/TenderWorkspace";
import Solutions from "./pages/Solution";
import Industries from "./pages/Industries";
import Security from "./pages/Security";
import Pricing from "./pages/Pricing";

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