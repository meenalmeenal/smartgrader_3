
import React, { useState } from "react";
import "./ResultPage.css";

const GRADE_COLOR = { "A+": "#27AE60", "A": "#2ECC71", "B+": "#82C341", "B": "#F1C40F", "C": "#F39C12", "D": "#E67E22", "F": "#C0392B" };

function ScoreRing({ obtained, max }) {
  const pct = max > 0 ? Math.round((obtained / max) * 100) : 0;
  const color = pct >= 75 ? "#27AE60" : pct >= 50 ? "#F39C12" : "#C0392B";
  const r = 54; const circ = 2 * Math.PI * r;
  const offset = circ - (circ * pct) / 100;
  return (
    <div className="ring-wrap">
      <svg width="136" height="136" style={{ transform: "rotate(-90deg)" }}>
        <circle cx="68" cy="68" r={r} fill="none" stroke="#EDE9E0" strokeWidth="12" />
        <circle cx="68" cy="68" r={r} fill="none" stroke={color} strokeWidth="12"
          strokeDasharray={circ} strokeDashoffset={offset} strokeLinecap="round"
          style={{ transition: "stroke-dashoffset 1.2s ease" }} />
      </svg>
      <div className="ring-center">
        <span className="ring-score" style={{ color }}>{obtained}</span>
        <span className="ring-max">/{max}</span>
        <span className="ring-pct" style={{ color }}>{pct}%</span>
      </div>
    </div>
  );
}

function ConfidenceBar({ value }) {
  const color = value >= 75 ? "#27AE60" : value >= 50 ? "#F39C12" : "#C0392B";
  return (
    <div className="conf-bar-wrap">
      <div className="conf-bar-bg">
        <div className="conf-bar-fill" style={{ width: value + "%", background: color }} />
      </div>
      <span className="conf-val" style={{ color }}>{value}%</span>
    </div>
  );
}

export default function ResultPage({ result, onReset }) {
  const [showExtracted, setShowExtracted] = useState(false);
  const gradeColor = GRADE_COLOR[result.grade] || "#1A1612";
  const reviewCount = result.needs_review_count || 0;

  return (
    <div className="result-page">
      {/* Score Header */}
      <div className="score-header card">
        <ScoreRing obtained={result.total_obtained} max={result.total_max} />
        <div className="score-info">
          <div className="score-meta">
            {result.student_name && <span className="student-name">{result.student_name}</span>}
            <span className="subject-tag">{result.subject}</span>
          </div>
          <div className="grade-row">
            <span className="grade-letter" style={{ color: gradeColor }}>{result.grade}</span>
            <div>
              <div className="score-numbers">{result.total_obtained} / {result.total_max}</div>
              <div className="performance">{result.performance_label}</div>
            </div>
          </div>
          <blockquote className="teacher-comment">"{result.overall_comment}"</blockquote>
          <div className="meta-chips">
            <span className="chip">Avg Confidence: {result.avg_confidence}%</span>
            {reviewCount > 0 && (
              <span className="chip chip-warn">⚠ {reviewCount} question{reviewCount > 1 ? "s" : ""} need review</span>
            )}
          </div>
        </div>
      </div>

      {/* Strengths & Improvements */}
      <div className="two-col">
        <div className="card strength-card">
          <div className="card-label green">✓ Strengths</div>
          <ul className="bullet-list green-list">
            {result.strengths?.map((s, i) => <li key={i}>{s}</li>)}
          </ul>
        </div>
        <div className="card improve-card">
          <div className="card-label red">↑ Areas to Improve</div>
          <ul className="bullet-list red-list">
            {result.improvements?.map((s, i) => <li key={i}>{s}</li>)}
          </ul>
        </div>
      </div>

      {/* Questions */}
      <div>
        <div className="section-title">Question-wise Breakdown</div>
        <div className="questions-list">
          {result.questions?.map((q, i) => {
            const pct = q.marks_available > 0 ? Math.round((q.marks_awarded / q.marks_available) * 100) : 0;
            const markColor = pct >= 75 ? "#27AE60" : pct >= 50 ? "#F39C12" : "#C0392B";
            return (
              <div key={i} className={"q-card card" + (q.needs_review ? " needs-review" : "")}>
                {q.needs_review && <div className="review-flag">⚠ Teacher Review Recommended</div>}
                <div className="q-row">
                  <div className="q-num">Q{q.number}</div>
                  <div className="q-body">
                    <div className="q-answers">
                      <div className="q-answer-block student-block">
                        <span className="answer-label">Student wrote</span>
                        <p>{q.student_answer}</p>
                      </div>
                      <div className="q-answer-block key-block">
                        <span className="answer-label">Answer key</span>
                        <p>{q.correct_answer}</p>
                      </div>
                    </div>
                    <div className="q-keywords">
                      {q.keywords_present?.length > 0 && (
                        <div className="kw-group">
                          <span className="kw-label">✓ Present:</span>
                          {q.keywords_present.map((k, j) => <span key={j} className="kw-tag present">{k}</span>)}
                        </div>
                      )}
                      {q.keywords_missing?.length > 0 && (
                        <div className="kw-group">
                          <span className="kw-label">✗ Missing:</span>
                          {q.keywords_missing.map((k, j) => <span key={j} className="kw-tag missing">{k}</span>)}
                        </div>
                      )}
                    </div>
                    <div className="q-feedback">💬 {q.feedback}</div>
                    <div className="q-confidence">
                      <span className="conf-label">AI Confidence</span>
                      <ConfidenceBar value={q.confidence || 0} />
                      <span className="conf-reason">{q.confidence_reason}</span>
                    </div>
                  </div>
                  <div className="q-score">
                    <div className="q-marks" style={{ color: markColor }}>{q.marks_awarded}<span className="q-max">/{q.marks_available}</span></div>
                    <div className="q-verdict" style={{ color: markColor }}>{q.verdict}</div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Extracted text */}
      {result.extracted_text && (
        <div className="card">
          <button className="toggle-link" onClick={() => setShowExtracted(!showExtracted)}>
            {showExtracted ? "▲ Hide" : "▼ Show"} Extracted OCR Text
          </button>
          {showExtracted && <pre className="ocr-text">{result.extracted_text}</pre>}
        </div>
      )}

      {/* Actions */}
      <div className="actions">
        <button className="btn-primary" onClick={() => window.print()}>🖨 Print Report</button>
        <button className="btn-primary" style={{ background: "var(--green)" }} onClick={onReset}>+ Grade Another</button>
      </div>
    </div>
  );
}
