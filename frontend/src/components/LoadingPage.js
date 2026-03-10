
import React, { useState, useEffect } from "react";
import "./LoadingPage.css";

const STEPS = [
  { icon: "📄", label: "Reading scanned answer sheet with Gemini Vision..." },
  { icon: "📋", label: "Reading answer key with Gemini Vision..." },
  { icon: "✂️",  label: "Segmenting answers into question pairs..." },
  { icon: "🔑", label: "Parsing answer key concepts and marks..." },
  { icon: "📊", label: "Grading each question with Llama 3.3..." },
  { icon: "🎯", label: "Calculating confidence scores..." },
  { icon: "📝", label: "Generating teacher feedback..." },
];

export default function LoadingPage() {
  const [active, setActive] = useState(0);

  useEffect(() => {
    const id = setInterval(() => setActive((a) => (a + 1) % STEPS.length), 2800);
    return () => clearInterval(id);
  }, []);

  return (
    <div className="loading-page">
      <div className="loading-card card">
        <div className="spinner-wrap">
          <div className="spinner" />
          <span className="spinner-icon">{STEPS[active].icon}</span>
        </div>
        <h2 className="loading-title">Grading in Progress</h2>
        <p className="loading-step">{STEPS[active].label}</p>
        <div className="step-dots">
          {STEPS.map((_, i) => (
            <div key={i} className={"dot" + (i === active ? " active" : i < active ? " done" : "")} />
          ))}
        </div>
        <div className="loading-note">This may take 30–60 seconds depending on the number of questions</div>
      </div>
    </div>
  );
}
