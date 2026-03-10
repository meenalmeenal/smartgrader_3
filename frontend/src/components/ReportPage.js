import React, { useState } from "react";
import "./ReportPage.css";

const GRADE_COLOR = {"A+":"#f0c040",A:"#3fb950",B:"#58a6ff",C:"#d29922",D:"#e8875a",F:"#f85149"};

function ConfidenceBadge({ score }) {
  const color = score >= 80 ? "var(--green)" : score >= 55 ? "var(--orange)" : "var(--red)";
  const label = score >= 80 ? "High" : score >= 55 ? "Medium" : "Low";
  return (
    <div className="conf-badge" style={{color,borderColor:color+"55",background:color+"11"}}>
      <span className="conf-dot" style={{background:color}} />{score}% {label} Confidence
    </div>
  );
}

function ScoreRing({ obtained, max }) {
  const pct = max > 0 ? Math.round((obtained/max)*100) : 0;
  const color = pct>=75?"var(--green)":pct>=50?"var(--orange)":"var(--red)";
  const r=54, circ=2*Math.PI*r, offset=circ-(circ*pct/100);
  return (
    <div className="score-ring">
      <svg width="136" height="136" style={{transform:"rotate(-90deg)"}}>
        <circle cx="68" cy="68" r={r} fill="none" stroke="var(--bg3)" strokeWidth="12"/>
        <circle cx="68" cy="68" r={r} fill="none" stroke={color} strokeWidth="12"
          strokeDasharray={circ} strokeDashoffset={offset} strokeLinecap="round"
          style={{transition:"stroke-dashoffset 1.2s ease"}}/>
      </svg>
      <div className="ring-center">
        <span className="ring-score" style={{color}}>{obtained}</span>
        <span className="ring-max">/ {max}</span>
      </div>
    </div>
  );
}

function QuestionCard({ q }) {
  const [open, setOpen] = useState(false);
  const pct = q.marks_available>0 ? Math.round((q.marks_awarded/q.marks_available)*100) : 0;
  const barColor = pct>=75?"var(--green)":pct>=45?"var(--orange)":"var(--red)";
  const confColor = q.confidence>=80?"var(--green)":q.confidence>=55?"var(--orange)":"var(--red)";
  const isSubpart = q.display_label?.match(/[a-z]$/);

  return (
    <div className={`q-card ${q.needs_review?"needs-review":""} ${isSubpart?"is-subpart":""}`}>
      <div className="q-header" onClick={()=>setOpen(!open)}>
        <div className="q-num">{q.display_label}</div>
        <div className="q-bars">
          <div className="bar-row">
            <span className="bar-label">Marks</span>
            <div className="bar-track"><div className="bar-fill" style={{width:`${pct}%`,background:barColor}}/></div>
            <span className="bar-val" style={{color:barColor}}>{q.marks_awarded}/{q.marks_available}</span>
          </div>
          <div className="bar-row">
            <span className="bar-label">Confidence</span>
            <div className="bar-track"><div className="bar-fill" style={{width:`${q.confidence}%`,background:confColor,opacity:0.7}}/></div>
            <span className="bar-val" style={{color:confColor}}>{q.confidence}%</span>
          </div>
        </div>
        <div className="q-badges">
          {q.needs_review && <span className="badge review">⚠ Review</span>}
          <span className="chevron">{open?"▲":"▼"}</span>
        </div>
      </div>
      {open && (
        <div className="q-body">
          <div className="q-section"><div className="q-section-title">Student Answer</div>
            <div className="q-text student">{q.student_answer||<em>No answer written</em>}</div></div>
          <div className="q-section"><div className="q-section-title">Correct Answer</div>
            <div className="q-text correct">{q.correct_answer}</div></div>
          <div className="q-concepts">
            <div className="concept-group">
              <span className="cg-label present">✅ Present</span>
              {q.keywords_present?.length>0 ? q.keywords_present.map((k,i)=><span key={i} className="tag green">{k}</span>) : <span className="tag muted">None</span>}
            </div>
            <div className="concept-group">
              <span className="cg-label missing">❌ Missing</span>
              {q.keywords_missing?.length>0 ? q.keywords_missing.map((k,i)=><span key={i} className="tag red">{k}</span>) : <span className="tag muted">None — full marks!</span>}
            </div>
          </div>
          <div className="q-feedback"><span>💬</span><span>{q.feedback}</span></div>
          <div className="q-conf-reason"><span style={{color:confColor}}>◉</span><span><strong>Confidence: </strong>{q.confidence_reason}</span></div>
        </div>
      )}
    </div>
  );
}

// Group questions by parent for display
function groupByParent(questions) {
  const groups = [];
  const seen = new Map();
  for (const q of questions) {
    const p = q.parent;
    if (!p) { groups.push({ parent: null, items: [q] }); continue; }
    if (!seen.has(p)) { const g={parent:p,items:[]}; seen.set(p,g); groups.push(g); }
    seen.get(p).items.push(q);
  }
  return groups;
}

export default function ReportPage({ data, onReset }) {
  const { gradedQuestions, summary, extractedText } = data;
  const [showExtracted, setShowExtracted] = useState(false);
  const reviewCount = gradedQuestions.filter(q=>q.needs_review).length;
  const gradeColor  = GRADE_COLOR[summary.grade] || "var(--muted)";
  const avgConf     = summary.average_confidence || Math.round(gradedQuestions.reduce((s,q)=>s+q.confidence,0)/gradedQuestions.length);
  const groups      = groupByParent(gradedQuestions);

  return (
    <div className="report-page">
      <div className="score-header card">
        <ScoreRing obtained={summary.total_obtained} max={summary.total_max} />
        <div className="score-detail">
          <div className="grade-row">
            <span className="grade-letter" style={{color:gradeColor}}>{summary.grade}</span>
            <div><div className="score-big">{summary.total_obtained} / {summary.total_max}</div>
            <div className="score-pct">{summary.percentage}%</div></div>
          </div>
          <blockquote className="overall-comment">"{summary.overall_comment}"</blockquote>
          <div className="avg-conf">
            <ConfidenceBadge score={avgConf} />
            {reviewCount>0 && <div className="review-alert">⚠️ {reviewCount} part{reviewCount>1?"s":""} flagged for review</div>}
          </div>
        </div>
      </div>

      <div className="two-col">
        <div className="card strength-card"><h4>✅ Strengths</h4><ul>{summary.strengths?.map((s,i)=><li key={i}>{s}</li>)}</ul></div>
        <div className="card improve-card"><h4>📌 Areas to Improve</h4><ul>{summary.improvements?.map((s,i)=><li key={i}>{s}</li>)}</ul></div>
      </div>

      <div className="legend">
        <span className="legend-item"><span className="ld green"/>High Confidence (80–100%)</span>
        <span className="legend-item"><span className="ld orange"/>Medium (55–79%)</span>
        <span className="legend-item"><span className="ld red"/>Low — Review (&lt;55%)</span>
      </div>

      <div>
        <div className="section-title">📊 Question-wise Evaluation</div>
        <div className="questions-list">
          {groups.map((group, gi) => (
            <div key={gi} className="q-group">
              {group.parent && (
                <div className="q-group-header">
                  <span>{group.parent}</span>
                  <span className="group-total">
                    {group.items.reduce((s,q)=>s+q.marks_awarded,0)} / {group.items.reduce((s,q)=>s+q.marks_available,0)} marks
                  </span>
                </div>
              )}
              {group.items.map((q,i)=><QuestionCard key={i} q={q} />)}
            </div>
          ))}
        </div>
      </div>

      {extractedText && (
        <div className="card">
          <button className="toggle-btn" onClick={()=>setShowExtracted(!showExtracted)}>
            📄 {showExtracted?"Hide":"Show"} OCR Extracted Text
          </button>
          {showExtracted && <pre className="extracted">{extractedText}</pre>}
        </div>
      )}

      <div className="actions-row">
        <button className="btn-primary" onClick={()=>window.print()}>🖨️ Print Report</button>
        <button className="btn-outline" onClick={onReset}>← Grade Another</button>
      </div>
    </div>
  );
}