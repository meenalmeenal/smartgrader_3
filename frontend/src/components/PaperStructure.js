import React, { useState } from "react";
import "./PaperStructure.css";

// ── Helpers ───────────────────────────────────────────────────────────────────
const uid = () => Math.random().toString(36).slice(2, 8);

const makeSubpart = (label="a") => ({ id: uid(), label, marks: 2, answer_key: "" });
const makeQuestion = (num=1) => ({
  id: uid(), num, type: "question",   // "question" | "section"
  label: `Q${num}`, marks: 5,
  has_subparts: false,
  subparts: [],
  answer_key: "",
});
const makeSection = (label="Section A", startNum=1) => ({
  id: uid(), type: "section",
  label, startNum, questions: [makeQuestion(startNum)],
});

const totalMarks = (structure) => {
  let t = 0;
  for (const block of structure) {
    if (block.type === "section") {
      for (const q of block.questions) {
        if (q.has_subparts) t += q.subparts.reduce((s,p)=>s+Number(p.marks||0),0);
        else t += Number(q.marks||0);
      }
    } else {
      if (block.has_subparts) t += block.subparts.reduce((s,p)=>s+Number(p.marks||0),0);
      else t += Number(block.marks||0);
    }
  }
  return t;
};

// ── SubpartRow ────────────────────────────────────────────────────────────────
function SubpartRow({ sp, qLabel, onChange, onDelete }) {
  return (
    <div className="subpart-row">
      <div className="sp-label-wrap">
        <span className="sp-qlabel">{qLabel}</span>
        <input className="sp-label-input" value={sp.label} onChange={e=>onChange({...sp,label:e.target.value})} placeholder="a" />
      </div>
      <input className="sp-marks" type="number" min="0" value={sp.marks} onChange={e=>onChange({...sp,marks:e.target.value})} />
      <span className="sp-unit">marks</span>
      <button className="sp-del" onClick={onDelete}>✕</button>
    </div>
  );
}

// ── QuestionRow ───────────────────────────────────────────────────────────────
function QuestionRow({ q, sectionLabel, onChange, onDelete }) {
  const displayNum = sectionLabel ? `${sectionLabel} Q${q.num}` : q.label;

  const addSubpart = () => {
    const nextLabel = String.fromCharCode(97 + q.subparts.length);
    const fullLabel = `${q.label}${nextLabel}`; // e.g. Q4a, Q4b
    onChange({...q, subparts:[...q.subparts, makeSubpart(fullLabel)]});
};
  const updateSubpart = (idx, sp) => {
    const subs = [...q.subparts]; subs[idx]=sp;
    onChange({...q, subparts:subs});
  };
  const deleteSubpart = (idx) => {
    onChange({...q, subparts:q.subparts.filter((_,i)=>i!==idx)});
  };
  const toggleSubparts = () => {
    if (!q.has_subparts) onChange({...q, has_subparts:true, subparts:[makeSubpart(`${q.label}a`), makeSubpart(`${q.label}b`)]});
    else onChange({...q, has_subparts:false, subparts:[]});
  };

  const qMarks = q.has_subparts ? q.subparts.reduce((s,p)=>s+Number(p.marks||0),0) : Number(q.marks||0);

  return (
    <div className={`q-row ${q.has_subparts ? "has-subs" : ""}`}>
      <div className="q-row-header">
        <div className="q-num-badge">{displayNum}</div>

        {!q.has_subparts && (
          <div className="q-marks-wrap">
            <input className="q-marks-input" type="number" min="0" value={q.marks} onChange={e=>onChange({...q,marks:e.target.value})} />
            <span className="q-marks-unit">marks</span>
          </div>
        )}
        {q.has_subparts && (
          <div className="q-marks-total">
            <span className="total-val">{qMarks}</span>
            <span className="total-label">total marks</span>
          </div>
        )}

        <div className="q-actions">
          <button className={`sub-toggle ${q.has_subparts?"active":""}`} onClick={toggleSubparts}>
            {q.has_subparts ? "✕ Remove subparts" : "+ Add subparts (a, b, c...)"}
          </button>
          <button className="q-del" onClick={onDelete}>🗑</button>
        </div>
      </div>

      {q.has_subparts && (
        <div className="subparts-area">
          {q.subparts.map((sp,i)=>(
            <SubpartRow key={sp.id} sp={sp} qLabel={`${q.label}`}
              onChange={sp=>updateSubpart(i,sp)}
              onDelete={()=>deleteSubpart(i)}
            />
          ))}
          <button className="add-subpart-btn" onClick={addSubpart}>
            + Add subpart {q.label}{String.fromCharCode(97+q.subparts.length)}
          </button>
        </div>
      )}
    </div>
  );
}

// ── SectionBlock ──────────────────────────────────────────────────────────────
function SectionBlock({ block, onChange, onDelete }) {
  const addQ = () => {
    const num = block.startNum + block.questions.length;
    onChange({...block, questions:[...block.questions, makeQuestion(num)]});
  };
  const updateQ = (idx, q) => {
    const qs=[...block.questions]; qs[idx]=q;
    onChange({...block, questions:qs});
  };
  const deleteQ = (idx) => onChange({...block, questions:block.questions.filter((_,i)=>i!==idx)});
  const secMarks = block.questions.reduce((s,q)=> s + (q.has_subparts ? q.subparts.reduce((a,p)=>a+Number(p.marks||0),0) : Number(q.marks||0)), 0);

  return (
    <div className="section-block">
      <div className="section-header">
        <div className="section-label-wrap">
          <span className="section-icon">§</span>
          <input className="section-name-input" value={block.label} onChange={e=>onChange({...block,label:e.target.value})} placeholder="Section A" />
          <span className="section-marks-badge">{secMarks} marks</span>
        </div>
        <button className="sec-del" onClick={onDelete}>Remove Section</button>
      </div>
      <div className="section-questions">
        {block.questions.map((q,i)=>(
          <QuestionRow key={q.id} q={q} sectionLabel={block.label}
            onChange={q=>updateQ(i,q)}
            onDelete={()=>deleteQ(i)}
          />
        ))}
        <button className="add-q-btn" onClick={addQ}>+ Add Question to {block.label}</button>
      </div>
    </div>
  );
}

// ── Main PaperStructure page ──────────────────────────────────────────────────
export default function PaperStructure({ uploadData, onGrade, onBack }) {
  const [structure, setStructure] = useState([makeQuestion(1), makeQuestion(2)]);
  const [mode, setMode] = useState("questions"); // "questions" | "sections"

  const total = totalMarks(structure);

  const addQuestion = () => {
    const num = structure.filter(b=>b.type==="question").length + 1;
    setStructure([...structure, makeQuestion(num)]);
  };
  const addSection = () => {
    const existingSections = structure.filter(b => b.type === "section");
    const totalQsSoFar = existingSections.reduce((t, s) => t + s.questions.length, 0);
    const nextNum = totalQsSoFar + 1;
    const label = `Section ${String.fromCharCode(65 + existingSections.length)}`;
    setStructure([...structure, makeSection(label, nextNum)]);
};

  const updateBlock = (idx, block) => { const s=[...structure]; s[idx]=block; setStructure(s); };
  const deleteBlock = (idx) => setStructure(structure.filter((_,i)=>i!==idx));

  const switchMode = (m) => {
    setMode(m);
    if (m === "sections") setStructure([makeSection("Section A", 1)]);
    else setStructure([makeQuestion(1), makeQuestion(2)]);
  };

  const handleGrade = () => onGrade(structure);

  return (
    <div className="ps-page">
      <div className="ps-header">
        <div>
          <h1>Paper Structure & Marks</h1>
          <p>Define exactly how marks are distributed. Add sections, questions, and subparts (a, b, c).</p>
        </div>
        <div className="total-badge">
          <span className="total-num">{total}</span>
          <span className="total-txt">Total Marks</span>
        </div>
      </div>

      {/* Mode selector */}
      <div className="mode-tabs">
        <button className={mode==="questions"?"mode-tab active":"mode-tab"} onClick={()=>switchMode("questions")}>
          <span>📝</span> Questions only <span className="mode-desc">Q1, Q2, Q3...</span>
        </button>
        <button className={mode==="sections"?"mode-tab active":"mode-tab"} onClick={()=>switchMode("sections")}>
          <span>📚</span> Sections <span className="mode-desc">Section A / B / C with questions inside</span>
        </button>
      </div>

      {/* Structure builder */}
      <div className="structure-area">
        {structure.map((block, idx) => (
          block.type === "section"
            ? <SectionBlock key={block.id} block={block} onChange={b=>updateBlock(idx,b)} onDelete={()=>deleteBlock(idx)} />
            : <QuestionRow key={block.id} q={block} onChange={q=>updateBlock(idx,q)} onDelete={()=>deleteBlock(idx)} />
        ))}

        {/* Add buttons */}
        <div className="add-row">
          {mode === "questions" && (
            <button className="add-block-btn" onClick={addQuestion}>+ Add Question</button>
          )}
          {mode === "sections" && (
            <button className="add-block-btn" onClick={addSection}>+ Add Section</button>
          )}
        </div>
      </div>

      {/* Summary strip */}
      <div className="summary-strip card">
        <div className="summary-stat">
          <span className="ss-val">{structure.filter(b=>b.type==="section").length || structure.length}</span>
          <span className="ss-label">{mode==="sections" ? "Sections" : "Questions"}</span>
        </div>
        <div className="summary-stat">
          <span className="ss-val">
            {structure.reduce((t,b)=> t + (b.type==="section" ? b.questions.reduce((s,q)=> s+(q.has_subparts ? q.subparts.length : 1),0) : (b.has_subparts ? b.subparts.length : 1)), 0)}
          </span>
          <span className="ss-label">Total Parts</span>
        </div>
        <div className="summary-stat accent">
          <span className="ss-val">{total}</span>
          <span className="ss-label">Total Marks</span>
        </div>
      </div>

      {/* Actions */}
      <div className="ps-actions">
        <button className="btn-ghost" onClick={onBack}>← Back</button>
        <button className="btn-primary" onClick={handleGrade} disabled={total === 0}>
          🎓 Grade Now ({total} marks)
        </button>
      </div>
    </div>
  );
}