import { BrowserRouter, Routes, Route } from "react-router-dom";
import Landing from "./Landing";
import Activate from "./Activate";
import TripPlanner from "./TripPlanner";
import History from "./History";
import Preferences from "./Preferences";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/activate" element={<Activate />} />
        <Route path="/trips/:sessionId?" element={<TripPlanner />} />
        <Route path="/history" element={<History />} />
        <Route path="/preferences" element={<Preferences />} />
      </Routes>
    </BrowserRouter>
  );
}
