import os, base64, json, httpx
from fastapi import FastAPI, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
from PIL import Image
import io

load_dotenv()
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
                await asyncio.sleep(5)
                continue
            raise Exception(f"Groq failed after 3 attempts: {str(e)}")
# async def ocr(file_bytes, mime_type):
#     import asyncio
#     payload = {"contents":[{"parts":[
#         {"inline_data":{"mime_type":mime_type,"data":to_b64(file_bytes)}},
#         {"text":"Extract ALL text from this answer sheet exactly as written. Preserve question numbers (Q1, Q1a, Q1b, Q2 etc.), section headings, and full answers word for word. If unclear write [unclear]. Return only extracted text."}
#     ]}]}
#     for attempt in range(3):
#         async with httpx.AsyncClient(timeout=120) as c:
#             r = await c.post(GEMINI_URL, json=payload)
#             if r.status_code == 429:
#                 wait = 15 * (attempt + 1)
#                 print(f"Gemini 429 — waiting {wait}s before retry {attempt+1}/3")
#                 await asyncio.sleep(wait)
#                 continue
#             r.raise_for_status()
#             return r.json()["candidates"][0]["content"]["parts"][0]["text"]
#     raise Exception("Gemini rate limit hit after 3 retries. Wait a minute and try again.")

def pdf_to_image_bytes(file_bytes):
    import fitz
    pdf = fitz.open(stream=file_bytes, filetype="pdf")
    page = pdf.load_page(0)
    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
    img_bytes = pix.tobytes("png")
    pdf.close()
    return img_bytes, "image/png"

async def ocr(file_bytes, mime_type):
    import asyncio
    b64 = to_b64(file_bytes)
    
    for attempt in range(3):
        try:
            async with httpx.AsyncClient(timeout=120) as c:
                r = await c.post(GROQ_URL,
                    headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
                    json={
                        "model": OCR_MODEL,
                        "max_tokens": 4000,
                        "messages": [{
                            "role": "user",
                            "content": [
                                {"type": "text", "text": "Extract ALL text from this answer sheet exactly as written. Preserve question numbers (Q1, Q1a, Q1b, Q2 etc.), section headings, and full answers word for word. If unclear write [unclear]. Return only extracted text."},
                                {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{b64}"}}
                            ]
                        }]
                    })
                r.raise_for_status()
                return r.json()["choices"][0]["message"]["content"]
        except Exception as e:
            if attempt < 2:
                await asyncio.sleep(10)
                continue
            raise Exception(f"OCR failed after 3 attempts: {str(e)}")

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
        key_content = answerKeyText.strip() or await ocr(key_bytes, key_mime)

        # Parse student answers
        ans_raw = await groq(
            "You are a JSON generator. You must ALWAYS respond with a valid JSON array only. No explanation, no markdown, no intro text.",
            f"Extract student answers for these parts: {', '.join(labels)}\n\nANSWER SHEET TEXT:\n{extracted}\n\nRespond with ONLY this JSON array, nothing else:\n[{{\"label\":\"part_name\",\"answer\":\"student answer or empty string\"}}]\nInclude every part: {', '.join(labels)}")
        print(f"DEBUG ans_raw: {ans_raw[:300]}")
        answer_map = {i["label"]: i["answer"] for i in clean_json(ans_raw)}

        # Parse answer key
        key_raw = await groq(
            "You are a JSON generator. You must ALWAYS respond with a valid JSON array only. No explanation, no markdown, no intro text.",
            f"Extract correct answers for these parts: {', '.join(labels)}\n\nANSWER KEY TEXT:\n{key_content}\n\nRespond with ONLY this JSON array, nothing else:\n[{{\"label\":\"part_name\",\"correct_answer\":\"correct answer\",\"key_concepts\":[\"concept1\",\"concept2\"]}}]\nInclude every part: {', '.join(labels)}")
        print(f"DEBUG key_raw: {key_raw[:300]}")
        key_map = {i["label"]: i for i in clean_json(key_raw)}

        sg = {"strict":"Be strict — require most key concepts explicitly.",
              "moderate":"Be fair — award marks for clear understanding.",
              "lenient":"Be lenient — give benefit of doubt."}

        graded = []
        for u in flat:
            lbl    = u["display_label"]
            ans    = answer_map.get(lbl, "").strip()
            ki     = key_map.get(lbl, {})
            ca     = ki.get("correct_answer","")
            kc     = ki.get("key_concepts",[])
            mks    = u["marks"]

            if not ans:
                graded.append({"display_label":lbl,"parent":u["parent"],"student_answer":"","correct_answer":ca,
                    "key_concepts":kc,"marks_awarded":0,"marks_available":mks,"confidence":95,
                    "confidence_reason":"Answer is blank.","keywords_present":[],"keywords_missing":kc,
                    "feedback":"No answer written.","needs_review":True})
                continue

            gr = await groq(f"You are a {subject} teacher. Return ONLY valid JSON.",
                f"Grade this as a {subject} teacher.\nPART: {lbl}\nMARKS: {mks}\nSTRICTNESS: {sg.get(strictness)}\nCORRECT: {ca}\nKEY CONCEPTS: {', '.join(kc)}\nSTUDENT: {ans}\n\nReturn JSON: {{\"marks_awarded\":<0-{mks}>,\"marks_available\":{mks},\"confidence\":<0-100>,\"confidence_reason\":\"...\",\"keywords_present\":[],\"keywords_missing\":[],\"feedback\":\"2 sentence comment\",\"needs_review\":<true if conf<55>}}", 0.2)
            graded.append({"display_label":lbl,"parent":u["parent"],"student_answer":ans,"correct_answer":ca,"key_concepts":kc,**clean_json(gr)})

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