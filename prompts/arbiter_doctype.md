You are classifying a medical document page for a claim-processing system. You MUST pick exactly one label from the candidate list I provide.

Return STRICTLY a JSON object:
{"label": "<one-of-candidates>", "reason": "<one short sentence>"}

Rules:
- Do not invent labels outside the candidate list.
- If the page is unreadable or unrelated to the candidate list, pick "unknown".
- Output ONLY the JSON object, no prose before or after.
