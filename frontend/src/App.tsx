import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "./AppShell";
import { EvaluationPage } from "./EvaluationPage";
import { EvaluationsTab } from "./EvaluationsTab";
import { IngestTab } from "./IngestTab";
import { LandingPage } from "./LandingPage";
import { LatencyPage } from "./LatencyPage";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route element={<AppShell />}>
          <Route path="/latency" element={<LatencyPage />} />
          <Route path="/evaluations" element={<EvaluationsTab />} />
          <Route path="/evaluations/upload" element={<IngestTab />} />
          <Route path="/evaluations/:recordingId" element={<EvaluationPage />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
