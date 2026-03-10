import React, { useState } from "react";
import axios from "axios";
import UploadPage from "./components/UploadPage";
import PaperStructure from "./components/PaperStructure";
import LoadingPage from "./components/LoadingPage";
import ReportPage from "./components/ReportPage";
import "./App.css";

export default function App() {
  const [page, setPage] = useState("upload");
  const [uploadData, setUploadData] = useState(null);   // files + basic settings
  const [structure, setStructure] = useState(null);     // paper structure with marks
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");

  // Step 1 → Step 2
  const handleUploaded = (data) => {
    setUploadData(data);
    setPage("structure");
  };

  // Step 2 → Step 3 (grade)
  const handleGrade = async (paperStructure) => {
    setStructure(paperStructure);
    setError("");
    setPage("loading");
    try {
      const fd = new FormData();
      fd.append("answerSheet",   uploadData.answerSheet);
      fd.append("answerKey",     uploadData.answerKey);
      fd.append("answerKeyText", uploadData.answerKeyText || "");
      fd.append("subject",       uploadData.subject);
      fd.append("studentName",   uploadData.studentName || "");
      fd.append("strictness",    uploadData.strictness);
      fd.append("structure",     JSON.stringify(paperStructure));
      const res = await axios.post("/api/grade", fd, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      setResult(res.data);
      setPage("report");
    } catch (err) {
      setError(err.response?.data?.error || err.message || "Something went wrong");
      setPage("structure");
    }
  };

  const handleReset = () => {
    setPage("upload"); setUploadData(null);
    setStructure(null); setResult(null); setError("");
  };

  const stepNum = { upload:1, structure:2, loading:3, report:4 }[page] || 1;

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="topbar-inner">
          <div className="brand">
            <span className="brand-mark">SG</span>
            <div>
              <span className="brand-name">GradeSmart</span>
              <span className="brand-tag">AI Evaluation System</span>
            </div>
          </div>

          {page !== "report" && page !== "loading" && (
            <div className="step-trail">
              {["Upload","Structure","Grade","Report"].map((s,i) => (
                <div key={i} className={`step-dot ${stepNum > i+1 ? "done" : ""} ${stepNum === i+1 ? "active" : ""}`}>
                  <div className="dot-circle">{stepNum > i+1 ? "✓" : i+1}</div>
                  <span>{s}</span>
                </div>
              ))}
            </div>
          )}

          <div className="topbar-pills">
            <span className="pill green">Gemini 2.5 Flash</span>
            <span className="pill blue">Llama 3.3 70B</span>
          </div>
          {page === "report" && <button className="btn-ghost" onClick={handleReset}>← New</button>}
        </div>
      </header>

      <main className="main-area">
        {error && <div className="error-bar">⚠️ {error}</div>}
        {page === "upload"    && <UploadPage    onNext={handleUploaded} />}
        {page === "structure" && <PaperStructure uploadData={uploadData} onGrade={handleGrade} onBack={() => setPage("upload")} />}
        {page === "loading"   && <LoadingPage />}
        {page === "report"    && result && <ReportPage data={result} onReset={handleReset} />}
      </main>
    </div>
  );
}