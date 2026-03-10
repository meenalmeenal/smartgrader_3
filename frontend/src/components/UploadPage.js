import React, { useState, useRef } from "react";
import "./UploadPage.css";

const SUBJECTS = ["Biology","Chemistry","Physics","History","Geography","English","Economics","Political Science","Sociology","Psychology","General"];

export default function UploadPage({ onNext }) {
  const [answerSheet, setAnswerSheet]     = useState(null);
  const [answerKey,   setAnswerKey]       = useState(null);
  const [answerKeyText, setAnswerKeyText] = useState("");
  const [keyMode,  setKeyMode]   = useState("file");
  const [subject,  setSubject]   = useState("Biology");
  const [strictness, setStrictness] = useState("moderate");
  const [studentName, setStudentName] = useState("");
  const [dragOver, setDragOver]  = useState(null);
  const sheetRef = useRef(); const keyRef = useRef();

  const handleNext = () => {
    if (!answerSheet) return;
    if (keyMode === "file" && !answerKey) return;
    if (keyMode === "text" && !answerKeyText.trim()) return;
    onNext({ answerSheet, answerKey, answerKeyText: keyMode === "text" ? answerKeyText : "", subject, strictness, studentName });
  };

  const DropZone = ({ label, sub, file, setter, id, refEl }) => (
    <div
      className={`dropzone ${dragOver === id ? "dz-over" : ""} ${file ? "dz-filled" : ""}`}
      onClick={() => refEl.current?.click()}
      onDragOver={(e) => { e.preventDefault(); setDragOver(id); }}
      onDragLeave={() => setDragOver(null)}
      onDrop={(e) => { e.preventDefault(); setDragOver(null); const f = e.dataTransfer.files[0]; if(f) setter(f); }}
    >
      <input ref={refEl} type="file" accept="image/jpeg,image/png,image/webp,application/pdf" style={{display:"none"}} onChange={(e) => setter(e.target.files[0])} />
      <div className="dz-icon">{file ? "✅" : "📄"}</div>
      <div className="dz-label">{file ? file.name : label}</div>
      <div className="dz-sub">{file ? `${(file.size/1024).toFixed(0)} KB` : sub}</div>
      {file && <button className="dz-remove" onClick={(e) => { e.stopPropagation(); setter(null); }}>✕ Remove</button>}
    </div>
  );

  const canNext = answerSheet && (keyMode === "file" ? answerKey : answerKeyText.trim());

  return (
    <div className="upload-page">
      <div className="page-header">
        <h1>Upload Papers</h1>
        <p>Upload the scanned answer sheet and answer key. You'll set marks per question in the next step.</p>
      </div>

      <div className="upload-row">
        <div className="upload-col">
          <div className="col-label">Student's Answer Sheet <span className="req">*</span></div>
          <DropZone label="Upload Answer Sheet" sub="JPG · PNG · WEBP · PDF" file={answerSheet} setter={setAnswerSheet} id="sheet" refEl={sheetRef} />
        </div>
        <div className="upload-col">
          <div className="col-label-row">
            <span className="col-label">Answer Key <span className="req">*</span></span>
            <div className="key-mode-tabs">
              <button className={keyMode==="file"?"tab active":"tab"} onClick={()=>setKeyMode("file")}>Upload File</button>
              <button className={keyMode==="text"?"tab active":"tab"} onClick={()=>setKeyMode("text")}>Type Text</button>
            </div>
          </div>
          {keyMode === "file"
            ? <DropZone label="Upload Answer Key" sub="Handwritten or printed" file={answerKey} setter={setAnswerKey} id="key" refEl={keyRef} />
            : <textarea className="key-textarea" placeholder={"Type answer key here...\n\nQ1. Answer for Q1\nQ1a. Sub-part answer\nQ2. Answer for Q2"} value={answerKeyText} onChange={(e)=>setAnswerKeyText(e.target.value)} />
          }
        </div>
      </div>

      <div className="card settings-card">
        <div className="settings-header">⚙️ Basic Settings</div>
        <div className="settings-grid">
          <div className="field">
            <label>Student Name <span className="opt">(optional)</span></label>
            <input type="text" value={studentName} onChange={(e)=>setStudentName(e.target.value)} placeholder="e.g. Riya Sharma" />
          </div>
          <div className="field">
            <label>Subject</label>
            <select value={subject} onChange={(e)=>setSubject(e.target.value)}>
              {SUBJECTS.map(s=><option key={s}>{s}</option>)}
            </select>
          </div>
          <div className="field full-width">
            <label>Strictness Level</label>
            <div className="strictness-row">
              {[["strict","🔴 Strict","Exact concepts required"],["moderate","🟡 Moderate","Fair judgment"],["lenient","🟢 Lenient","Benefit of doubt"]].map(([v,l,d])=>(
                <button key={v} className={`strict-btn ${strictness===v?"active":""}`} onClick={()=>setStrictness(v)}>
                  {l}<span>{d}</span>
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>

      <div className="submit-row">
        <button className="btn-primary submit-btn" onClick={handleNext} disabled={!canNext}>
          Next: Set Marks Structure →
        </button>
        {!canNext && <span className="submit-hint">{!answerSheet ? "Upload answer sheet to continue" : "Upload or type answer key to continue"}</span>}
      </div>
    </div>
  );
}