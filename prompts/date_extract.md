You are extracting dates from a medical document page. Return STRICTLY a JSON object with the requested fields (only include fields that apply).

Schema:
{
  "pre_date": "DD-MM-YYYY" | null,       // for investigation reports dated BEFORE hospitalization
  "post_date": "DD-MM-YYYY" | null,      // for investigation reports dated AFTER treatment
  "doa": "DD-MM-YYYY" | null,            // date of admission from discharge summary
  "dod": "DD-MM-YYYY" | null             // date of discharge from discharge summary
}

Rules:
- Output ONLY the JSON object, no prose before or after.
- Use DD-MM-YYYY format; if the document shows DD/MM/YY or 12-Mar-2026 or similar, normalize.
- If a field is not derivable from this page's text, set it to null.
- Do not guess. Do not invent dates.
