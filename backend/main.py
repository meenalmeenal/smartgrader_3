import os, base64, json, httpx
from fastapi import FastAPI, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
from PIL import Image
import io
import re as _re
from similarity import keyword_report, answer_level_sim, format_sim_context, concept_understanding_report
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"



# ── MCQ helpers ───────────────────────────────────────────────────────────────
_MCQ_OPTIONS = {"a","b","c","d","e","1","2","3","4","5"}

def is_mcq_answer(ans: str) -> bool:
    """True if student wrote just an option letter/number (MCQ-style)."""
    clean = ans.strip().lower().strip("().:) ")
    # Single letter/digit, or 'option b', 'choice a', etc.
    if clean in _MCQ_OPTIONS:
        return True
    m = _re.match(r'^(?:option|choice|ans(?:wer)?)\s*([a-e1-5])$', clean)
    return bool(m)

def extract_option(text: str) -> str:
    """Pull the option letter from text like 'B', '(b)', 'Option B: ...' """
    text = text.strip()[:20]  # only look at start of text
    m = _re.search(r'\b([a-eA-E1-5])\b', text)
    return m.group(1).lower() if m else text.strip().lower()[:1]


app = FastAPI(title="SmartGrader API")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:3000"], allow_methods=["*"], allow_headers=["*"])

GROQ_API_KEY   = os.getenv("GROQ_API_KEY")
OCR_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"
GROQ_URL   = "https://api.groq.com/openai/v1/chat/completions"

def to_b64(data): return base64.b64encode(data).decode()

def clean_json(text):
    text = text.strip()
    if not text:
        raise Exception("LLM returned empty response")
    # Strip intro sentence before [ or {
    start_arr = text.find("[")
    start_obj = text.find("{")
    if start_arr == -1 and start_obj == -1:
        raise Exception(f"No JSON found: {text[:200]}")
    if start_arr == -1: start = start_obj
    elif start_obj == -1: start = start_arr
    else: start = min(start_arr, start_obj)
    # Find the last ] or }
    end_arr = text.rfind("]")
    end_obj = text.rfind("}")
    end = max(end_arr, end_obj)
    text = text[start:end+1]
    # Strip code fences
    if "```" in text:
        parts = text.split("```")
        text = parts[1] if len(parts) > 1 else parts[0]
        if text.startswith("json"):
            text = text[4:]
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        import re
        # Replace single-quoted keys/values carefully using regex
        # Only replace quotes that are used as JSON delimiters
        text = re.sub(r"(?<![\\])'", '"', text)
        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            raise Exception(f"Could not parse JSON: {e}. Raw: {text[:300]}")


async def groq(system, user, temp=0.1):
    import asyncio
    for attempt in range(3):
        try:
            async with httpx.AsyncClient(timeout=90) as c:
                r = await c.post(GROQ_URL,
                    headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
                    json={"model":"llama-3.3-70b-versatile","temperature":temp,"max_tokens":4000,
                          "messages":[{"role":"system","content":system},{"role":"user","content":user}]})
                r.raise_for_status()
                return r.json()["choices"][0]["message"]["content"]
        except Exception as e:
            if attempt < 2:
                print(f"Groq attempt {attempt+1} failed: {e}. Retrying in 5s...")
                await asyncio.sleep(20)
                continue
            raise Exception(f"Groq failed after 3 attempts: {str(e)}")



def pdf_to_image_bytes(file_bytes):
    """Render ALL pages of a PDF and stitch them vertically into one PNG."""
    import fitz
    from PIL import Image as PILImage
    import io as _io

    pdf    = fitz.open(stream=file_bytes, filetype="pdf")
    matrix = fitz.Matrix(2, 2)   # 2× resolution for clarity

    page_images = []
    for i in range(len(pdf)):
        pix  = pdf.load_page(i).get_pixmap(matrix=matrix)
        img  = PILImage.open(_io.BytesIO(pix.tobytes("png")))
        page_images.append(img)
    pdf.close()

    if not page_images:
        raise Exception("PDF has no pages")

    # Stitch vertically: width = widest page, height = sum of all page heights
    total_w = max(img.width  for img in page_images)
    total_h = sum(img.height for img in page_images)
    canvas  = PILImage.new("RGB", (total_w, total_h), (255, 255, 255))
    y_offset = 0
    for img in page_images:
        canvas.paste(img, (0, y_offset))
        y_offset += img.height

    buf = _io.BytesIO()
    canvas.save(buf, format="PNG")
    return buf.getvalue(), "image/png"

######### GROQ OCR commented out for less use of GROQ tokens ###########


# async def ocr(file_bytes, mime_type):
#     import asyncio
#     b64 = to_b64(file_bytes)
    
#     for attempt in range(3):
#         try:
#             async with httpx.AsyncClient(timeout=120) as c:
#                 r = await c.post(GROQ_URL,
#                     headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
#                     json={
#                         "model": OCR_MODEL,
#                         "max_tokens": 4000,
#                         "messages": [{
#                             "role": "user",
#                             "content": [
#                                 {"type": "text", "text": "Extract ALL text from this answer sheet exactly as written. Preserve question numbers (Q1, Q1a, Q1b, Q2 etc.), section headings, and full answers word for word. If unclear write [unclear]. Return only extracted text."},
#                                 {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{b64}"}}
#                             ]
#                         }]
#                     })
#                 r.raise_for_status()
#                 return r.json()["choices"][0]["message"]["content"]
#         except Exception as e:
#             if attempt < 2:
#                 await asyncio.sleep(10)
#                 continue
#             raise Exception(f"OCR failed after 3 attempts: {str(e)}")

#################################################################

# async def ocr_answer_key(file_bytes, mime_type):
#     """Specialized OCR for answer keys — focuses on identifying correct MCQ options."""
#     import asyncio
#     b64 = to_b64(file_bytes)

#     for attempt in range(3):
#         try:
#             async with httpx.AsyncClient(timeout=120) as c:
#                 r = await c.post(GROQ_URL,
#                     headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
#                     json={
#                         "model": OCR_MODEL,
#                         "max_tokens": 4000,
#                         "messages": [{
#                             "role": "user",
#                             "content": [
#                                 {"type": "text", "text": (
#                                     "This is an ANSWER KEY document. Extract all text exactly as written.\n"
#                                     "CRITICAL for MCQ questions:\n"
#                                     "- The correct option may be marked by: a tick (✓), checkmark, circle, star (*), underline, bold, or written as 'Ans: b' or '1.(b)'.\n"
#                                     "- Always clearly write which option letter is correct for each MCQ, e.g. 'Q1 correct answer: (b)'\n"
#                                     "- List ALL options with their letters (a/b/c/d) but clearly mark which is correct.\n"
#                                     "- Preserve question numbers (Q1, Q2, Q1a etc.) and all answer text word for word.\n"
#                                     "Return only the extracted text."
#                                 )},
#                                 {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{b64}"}}
#                             ]
#                         }]
#                     })
#                 r.raise_for_status()
#                 return r.json()["choices"][0]["message"]["content"]
#         except Exception as e:
#             if attempt < 2:
#                 await asyncio.sleep(10)
#                 continue
#             raise Exception(f"OCR (answer key) failed after 3 attempts: {str(e)}")


##################### GEMINI OCR ###########################    

############# GEMINI's OCR #################

async def ocr(file_bytes, mime_type):
    import asyncio
    payload = {"contents":[{"parts":[
        {"inline_data":{"mime_type":mime_type,"data":to_b64(file_bytes)}},
        {"text": "Extract ALL text from this answer sheet exactly as written. "
         "Preserve ALL question numbers, section headings, bullet points, arrows (→), and problem labels (Problem-1, Problem-2 etc.). "
         "Include EVERY line — do not skip or summarize anything. "
         "If unclear write [unclear]. Return only extracted text, nothing else."}
    ]}]}
    for attempt in range(3):
        try:
            async with httpx.AsyncClient(timeout=120) as c:
                r = await c.post(GEMINI_URL, json=payload)
                if r.status_code == 429:
                    wait = 30 * (attempt + 1)
                    print(f"Gemini 429 — waiting {wait}s before retry {attempt+1}/3")
                    await asyncio.sleep(wait)
                    continue
                r.raise_for_status()
                return r.json()["candidates"][0]["content"]["parts"][0]["text"]
        except Exception as e:
            if attempt < 2:
                print(f"Gemini OCR attempt {attempt+1} failed: {e}. Retrying...")
                await asyncio.sleep(10)
                continue
            raise Exception(f"OCR failed after 3 attempts: {str(e)}")
    raise Exception("Gemini OCR failed after 3 retries.")


async def ocr_answer_key(file_bytes, mime_type):
    import asyncio
    payload = {"contents":[{"parts":[
        {"inline_data":{"mime_type":mime_type,"data":to_b64(file_bytes)}},
        {"text":(
            "This is an ANSWER KEY document. Extract all text exactly as written.\n"
            "CRITICAL for MCQ questions:\n"
            "- The correct option may be marked by: a tick (✓), checkmark, circle, star (*), underline, bold, or written as 'Ans: b' or '1.(b)'.\n"
            "- Always clearly write which option letter is correct for each MCQ, e.g. 'Q1 correct answer: (b)'\n"
            "- List ALL options with their letters (a/b/c/d) but clearly mark which is correct.\n"
            "- Preserve question numbers (Q1, Q2, Q1a etc.) and all answer text word for word.\n"
            "Return only the extracted text."
        )}
    ]}]}
    for attempt in range(3):
        try:
            async with httpx.AsyncClient(timeout=120) as c:
                r = await c.post(GEMINI_URL, json=payload)
                if r.status_code == 429:
                    wait = 30 * (attempt + 1)
                    print(f"Gemini 429 — waiting {wait}s before retry {attempt+1}/3")
                    await asyncio.sleep(wait)
                    continue
                r.raise_for_status()
                return r.json()["candidates"][0]["content"]["parts"][0]["text"]
        except Exception as e:
            if attempt < 2:
                await asyncio.sleep(10)
                continue
            raise Exception(f"OCR (answer key) failed after 3 attempts: {str(e)}")
    raise Exception("OCR answer key failed after 3 retries.")

def flatten(structure):
    units = []
    for block in structure:
        if block["type"] == "section":
            for q in block["questions"]:
                ql = f"{block['label']} Q{q['num']}"
                if q.get("has_subparts") and q.get("subparts"):
                    for sp in q["subparts"]:
                        units.append({"id":f"{q['id']}_{sp['id']}","display_label":f"{sp['label']}","marks":int(sp.get("marks") or 0),"parent":ql})
                else:
                    units.append({"id":q["id"],"display_label":ql,"marks":int(q.get("marks") or 0),"parent":block["label"]})
        else:
            q = block
            if q.get("has_subparts") and q.get("subparts"):
                for sp in q["subparts"]:
                    units.append({"id":f"{q['id']}_{sp['id']}","display_label":f"{sp['label']}","marks":int(sp.get("marks") or 0),"parent":q["label"]})
            else:
                units.append({"id":q["id"],"display_label":q["label"],"marks":int(q.get("marks") or 0),"parent":None})
    return units

@app.get("/api/health")
def health(): return {"status":"ok","message":"SmartGrader API running"}

@app.post("/api/grade")
async def grade(
    answerSheet:   UploadFile = File(...),
    answerKey:     UploadFile = File(...),
    subject:       str = Form("Biology"),
    studentName:   str = Form(""),
    strictness:    str = Form("moderate"),
    answerKeyText: str = Form(""),
    structure:     str = Form("[]"),
):
    try:
        flat = flatten(json.loads(structure))
        total_max = sum(u["marks"] for u in flat)
        labels = [u["display_label"] for u in flat]

        # OCR
        sheet_bytes = await answerSheet.read()
        sheet_mime = answerSheet.content_type
        if sheet_mime == "application/pdf":
            sheet_bytes, sheet_mime = pdf_to_image_bytes(sheet_bytes)
        extracted = await ocr(sheet_bytes, sheet_mime)
        print(f"OCR extracted {len(extracted)} characters")
        print(f"First 200 chars: {extracted[:200]}")

        key_bytes = await answerKey.read()
        key_mime = answerKey.content_type
        if key_mime == "application/pdf":
            key_bytes, key_mime = pdf_to_image_bytes(key_bytes)
        key_content = answerKeyText.strip() or await ocr_answer_key(key_bytes, key_mime)


        key_raw = await groq(
            "You are a JSON generator. You must ALWAYS respond with a valid JSON array only. No explanation, no markdown, no intro text.",
            f"Extract correct answers for these parts: {', '.join(labels)}\n\nANSWER KEY TEXT:\n{key_content}\n\n"
            f"IMPORTANT RULES:\n"
            f"- correct_answer: the full correct answer text. For MCQ, include the option letter prefix, e.g. '(b) Adiabatic process'\n"
            f"- correct_option: ONLY for MCQ questions — put just the single option letter here (a/b/c/d/e). For non-MCQ put empty string.\n"
            f"- key_concepts: list of key terms/concepts the answer must contain. For MCQ this can be empty.\n\n"
            f"Respond with ONLY this JSON array, nothing else:\n"
            f"[{{\"label\":\"part_name\",\"correct_answer\":\"(b) full answer\",\"correct_option\":\"b\",\"key_concepts\":[\"concept1\",\"concept2\"]}}]\n"
            f"Include every part: {', '.join(labels)}")
        print(f"DEBUG key_raw: {key_raw[:300]}")
        key_map = {i["label"]: i for i in clean_json(key_raw)}
        # Build question context
        question_context = "\n".join([
            f"- {lbl}: about '{key_map.get(lbl, {}).get('correct_answer', '')[:100]}'"
            for lbl in labels
        ])
        

        ans_raw = await groq(
            "You are a JSON generator. You must ALWAYS respond with a valid JSON array only. No explanation, no markdown, no intro text.",
            f"IMPORTANT: For questions that expect both benefits/concepts AND real-world examples/problems:\n"
            f"- Collect ALL bullet points under any related heading (e.g. 'Why Blockchain?')\n"
            f"- AND collect ALL 'Problem-X → Topic' lines on the page\n"
            f"- Combine them ALL into that question's answer\n"
            f"- The student may not have written Q2/Q3 labels for these — match by content\n"
            f"Extract student answers for these question parts: {', '.join(labels)}\n\n"
            f"ANSWER SHEET TEXT:\n{extracted}\n\n"
            f"WHAT EACH QUESTION IS ABOUT (match by meaning not label):\n{question_context}\n\n"
            f"CRITICAL RULES:\n"
            f"1. Match by MEANING not by Q number — student may have used wrong labels\n"
            f"2. Collect COMPLETE answer including all bullet points and examples\n"
            f"3. If one question asks about multiple problems, combine ALL Problem-X entries\n"
            f"4. NEVER truncate — include everything relevant\n"
            f"5. For MCQ: if student wrote only a letter (a/b/c/d), put ONLY that letter\n"
            f"6. If nothing found use empty string\n\n"
            f"Respond ONLY: [{{\"label\":\"part_name\",\"answer\":\"complete student answer\"}}]\n"
            f"Include every part: {', '.join(labels)}")
        print(f"DEBUG ans_raw FULL: {ans_raw}")
        answer_map = {i["label"]: i["answer"] for i in clean_json(ans_raw)}

        # Parse answer key
        
        # Strictness → similarity thresholds
        STRICT_THRESHOLDS = {
            "strict":   {"present": 0.80, "partial": 0.60},
            "moderate": {"present": 0.70, "partial": 0.45},
            "lenient":  {"present": 0.60, "partial": 0.35},
        }
        thresh = STRICT_THRESHOLDS.get(strictness, STRICT_THRESHOLDS["moderate"])

        graded = []
        for u in flat:
            lbl = u["display_label"]
            ans = answer_map.get(lbl, "").strip()
            ki  = key_map.get(lbl, {})
            ca  = ki.get("correct_answer", "")
            kc  = ki.get("key_concepts", [])
            mks = u["marks"]

            if not ans:
                graded.append({"display_label":lbl,"parent":u["parent"],"student_answer":"","correct_answer":ca,
                    "key_concepts":kc,"marks_awarded":0,"marks_available":mks,"confidence":95,
                    "confidence_reason":"Answer is blank.","keywords_present":[],"keywords_missing":kc,
                    "keywords_partial":[],"feedback":"No answer written.","needs_review":True})
                continue

            # ── MCQ: exact letter match, skip similarity ───────────────────
            if is_mcq_answer(ans):
                student_opt = extract_option(ans)
                # Prefer the dedicated correct_option field extracted by LLM
                # Fall back to parsing the option letter out of correct_answer text
                correct_opt = ki.get("correct_option", "").strip().lower()[:1]
                if not correct_opt or correct_opt not in "abcde12345":
                    correct_opt = extract_option(ca)
                is_correct    = student_opt == correct_opt
                marks_awarded = mks if is_correct else 0
                verdict       = "Correct" if is_correct else "Incorrect"
                graded.append({
                    "display_label":     lbl,
                    "parent":            u["parent"],
                    "student_answer":    ans,
                    "correct_answer":    ca,
                    "key_concepts":      kc,
                    "marks_awarded":     marks_awarded,
                    "marks_available":   mks,
                    "confidence":        95,
                    "confidence_reason": "MCQ — exact option match.",
                    "keywords_present":  [ca] if is_correct else [],
                    "keywords_missing":  [] if is_correct else [ca],
                    "keywords_partial":  [],
                    "feedback":          f"{'Correct option selected.' if is_correct else f'Incorrect. The correct option was {correct_opt.upper()}.'}",
                    "needs_review":      False,
                    "answer_type":       "mcq",
                    "similarity_scores": {"answer_sim": 1.0 if is_correct else 0.0, "multiplier": 1.0 if is_correct else 0.0},
                })
                continue

            # ── Text answer: deterministic marks via hybrid similarity ─────
            report      = concept_understanding_report(ans, ca, kc,
                              threshold_present=thresh["present"],
                              threshold_partial=thresh["partial"])
            ans_sim     = answer_level_sim(ans, ca)
            sim_context = format_sim_context(report, ans_sim)

            # Marks — keyword presence + conceptual understanding
            # Similarity-based marks
            sim_marks = report["blended_multiplier"] * mks

            # Confidence — RAG grounding primary signal
            avg_keyword = 0.0  # default if no keywords
            if report["per_keyword"]:
                avg_keyword = sum(r["hybrid"] for r in report["per_keyword"]) / len(report["per_keyword"])
                rag_confidence = (ans_sim * 0.60) + (avg_keyword * 0.40)
            else:
                rag_confidence = ans_sim

            # ── LLM grades + writes feedback ──────────────────────────────
            _kw_understood   = [e['keyword'] for e in report['per_keyword'] if e.get('understanding') == 'understood' and e['status'] != 'present']
            _kw_not_understood = [e['keyword'] for e in report['per_keyword'] if e.get('understanding') == 'not_understood']
            _all_correct     = len(report['missing']) == 0 and len(_kw_not_understood) == 0
            
            fb_raw = await groq(
                f"You are a {subject} teacher marking a student exam. Return ONLY valid JSON. Never use double quotes inside string values.",
                f"Verify this student answer and write feedback.\n"
                f"QUESTION PART: {lbl} | MAX MARKS: {mks}\n"
                f"STUDENT ANSWER: {ans[:300]}\n"
                f"MODEL ANSWER: {ca[:300]}\n\n"
                f"SIMILARITY ENGINE DETECTED:\n"
                f"- Keywords found in student text: {report['present']}\n"
                f"- Keywords understood but not stated: {_kw_understood}\n"
                f"- Keywords not understood: {_kw_not_understood}\n\n"
                f"YOUR JOB — two tasks:\n"
                f"TASK 1 — Verify keyword usage: For each keyword in {report['present']}, check if the student used it CORRECTLY\n"
                f"in the right conceptual context. A keyword present in text does NOT mean it was used correctly.\n"
                f"Example: 'blockchain is not immutable' contains 'immutable' but uses it WRONGLY.\n"
                f"If a keyword is misused, treat it as missing and reduce suggested_marks accordingly.\n\n"
                f"TASK 2 — Write feedback following these rules STRICTLY:\n"
                f"1. Focus ONLY on conceptual correctness — does the student understand the {subject} topic?\n"
                f"2. NEVER mention spelling, grammar, punctuation, typos, or sentence structure.\n"
                f"3. NEVER mention OCR artifacts, abbreviations, or handwriting.\n"
                f"4. If all concepts correct AND all keywords used correctly → write 2 affirming sentences.\n"
                f"5. If a keyword was misused → mention which concept needs correction.\n"
                f"6. If keywords_understood_but_not_stated → say 'you showed understanding but use the term X'.\n"
                f"7. suggested_marks must be an integer 0 to {mks}. Base it on conceptual correctness + correct keyword usage.\n\n"
                f"Return ONLY: {{\"feedback\":\"2 sentence concept-focused comment\","
                f"\"confidence_reason\":\"one sentence explaining AI confidence in this grade\","
                f"\"suggested_marks\":0,"
                f"\"needs_review\":{str(rag_confidence < 0.55).lower()}}}",
                0.1)  # Low temperature for consistency

            import re as _re2
            def _fix_json_field(raw, field):
                pattern = rf'("{field}"\s*:\s*")(.*?)("(?:\s*[,}}]))'
                def replacer(m):
                    inner = m.group(2).replace('\\"', '__ESCAPED__')
                    inner = inner.replace('"', "'")
                    inner = inner.replace('__ESCAPED__', '\\"')
                    return m.group(1) + inner + m.group(3)
                return _re2.sub(pattern, replacer, raw, flags=_re2.DOTALL)

            fb_raw_fixed = _fix_json_field(fb_raw, "feedback")
            fb_raw_fixed = _fix_json_field(fb_raw_fixed, "confidence_reason")
            try:
                fb = clean_json(fb_raw_fixed)
            except:
                # Last resort — extract just the fields manually
                feedback_match = _re2.search(r'"feedback"\s*:\s*"(.*?)"(?:\s*[,}])', fb_raw_fixed, _re2.DOTALL)
                reason_match   = _re2.search(r'"confidence_reason"\s*:\s*"(.*?)"(?:\s*[,}])', fb_raw_fixed, _re2.DOTALL)
                marks_match    = _re2.search(r'"suggested_marks"\s*:\s*(\d+)', fb_raw_fixed)
                review_match   = _re2.search(r'"needs_review"\s*:\s*(true|false)', fb_raw_fixed)
                fb = {
                    "feedback":          feedback_match.group(1) if feedback_match else "",
                    "confidence_reason": reason_match.group(1)   if reason_match   else "",
                    "suggested_marks":   int(marks_match.group(1)) if marks_match  else round(sim_marks),
                    "needs_review":      review_match.group(1) == "true" if review_match else rag_confidence < 0.55
                }

            # Blend: sim is the stable anchor (70%), LLM is a context-aware correction (30%)
            # LLM adjustment is clamped to ±1 mark to prevent wild swings
            llm_marks = float(fb.get("suggested_marks", sim_marks))
            llm_marks = max(0, min(mks, llm_marks))
            llm_adjustment = max(-1, min(1, llm_marks - sim_marks))  # cap LLM correction to ±1
            marks_awarded = max(0, min(mks, round(sim_marks + (llm_adjustment * 0.30))))

            # Confidence — agreement between sim and LLM boosts confidence
            sim_pct   = sim_marks / mks if mks else 0
            llm_pct   = llm_marks / mks if mks else 0
            agreement = 1.0 - abs(sim_pct - llm_pct)
            rag_confidence = (ans_sim * 0.50) + (avg_keyword * 0.30) + (agreement * 0.20)
            confidence = round(min(95, max(40, rag_confidence * 100)))


            graded.append({
                "display_label":     lbl,
                "parent":            u["parent"],
                "student_answer":    ans,
                "correct_answer":    ca,
                "key_concepts":      kc,
                "marks_awarded":     marks_awarded,
                "marks_available":   mks,
                "confidence":        confidence,
                "confidence_reason": fb.get("confidence_reason", ""),
                "keywords_present":  report["present"],
                "keywords_missing":  report["missing"],
                "keywords_partial":  report["partial"],
                "feedback":          fb.get("feedback", ""),
                "needs_review": rag_confidence < 0.55,
                "answer_type":       "text",
                "similarity_scores": {
                    "answer_sim": ans_sim,
                    "multiplier": report["blended_multiplier"],
                }
            })

        total_obt = sum(g["marks_awarded"] for g in graded)
        pct       = round(total_obt/total_max*100) if total_max else 0
        avg_conf  = round(sum(g["confidence"] for g in graded)/len(graded)) if graded else 0
        q_sum     = "\n".join(f"{g['display_label']}: {g['marks_awarded']}/{g['marks_available']} — {g['feedback']}" for g in graded)

        sr = await groq("You are a teacher. Return ONLY valid JSON.",
            f"Write report for {subject} student {studentName or 'Student'} scoring {total_obt}/{total_max} ({pct}%).\n{q_sum}\nReturn: {{\"grade\":\"A+/A/B/C/D/F\",\"overall_comment\":\"...\",\"strengths\":[\"...\"],\"improvements\":[\"...\"],\"average_confidence\":{avg_conf}}}\nScale: 90+=A+,80+=A,70+=B,60+=C,40+=D,<40=F", 0.4)
        summary = clean_json(sr)
        summary.update({"total_obtained":total_obt,"total_max":total_max,"percentage":pct})

        return JSONResponse({"success":True,"extractedText":extracted,"gradedQuestions":graded,"summary":summary})
    except Exception as e:
        import traceback; traceback.print_exc()
        return JSONResponse({"error":str(e)}, status_code=500)