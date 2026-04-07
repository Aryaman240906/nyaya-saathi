"""Document analysis router — upload and analyze legal documents."""
from __future__ import annotations
import base64
import logging

from fastapi import APIRouter, UploadFile, File, Form
from typing import Optional

from services.reasoning import analyze_document
from services.language import detect_language
from services import gemini_rest

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/documents", tags=["documents"])


@router.post("/analyze")
async def analyze(
    file: Optional[UploadFile] = File(None),
    text: Optional[str] = Form(None),
    language: Optional[str] = Form(None),
):
    """
    Analyze a legal document.
    Accepts text files, direct text input, or images (JPEG/PNG).
    Images are analyzed using Gemini's multimodal vision capabilities.
    """
    content = ""

    if file:
        raw = await file.read()
        mime = file.content_type or ""

        # V4: Image analysis via Gemini Vision
        if mime.startswith("image/"):
            b64_data = base64.b64encode(raw).decode("utf-8")
            lang = language or "en"
            lang_instruction = (
                "Respond in Hindi." if lang == "hi"
                else "Respond in Hinglish (mix of Hindi and English)." if lang == "hinglish"
                else "Respond in simple English."
            )

            prompt = f"""You are NYAYA-SAATHI, an expert Indian legal document analyzer.
Analyze this uploaded legal document image and provide:
1. **Document Type** — What kind of document is this? (FIR, Legal Notice, Court Order, Agreement, etc.)
2. **Summary** — A brief, plain-language summary
3. **Key Points** — Important clauses, dates, obligations, rights, or deadlines
4. **Entities** — Names, addresses, dates, amounts mentioned
5. **What This Means For You** — Practical implications in simple language
6. **What You Should Do** — Recommended next steps with specific actions
7. **Documents Needed** — Any supporting documents you should gather

{lang_instruction}
Be empathetic. Assume the user is a common citizen who needs help understanding this document."""

            try:
                analysis = await gemini_rest.generate_content(
                    contents=[{
                        "role": "user",
                        "parts": [
                            {"text": prompt},
                            {
                                "inlineData": {
                                    "mimeType": mime,
                                    "data": b64_data,
                                }
                            },
                        ],
                    }],
                    temperature=0.2,
                    max_output_tokens=4096,
                )
                return {"analysis": analysis, "language": lang, "type": "image"}
            except Exception as e:
                logger.error("Image analysis failed: %s", e)
                return {"error": f"Failed to analyze image: {str(e)}"}

        # Text file handling
        try:
            content = raw.decode("utf-8")
        except UnicodeDecodeError:
            content = raw.decode("latin-1", errors="ignore")
    elif text:
        content = text
    else:
        return {"error": "Please provide either a file or text to analyze"}

    if len(content.strip()) < 10:
        return {"error": "Document text is too short to analyze"}

    # Detect language if not provided
    lang = language or detect_language(content)

    result = await analyze_document(content, lang)
    return result

