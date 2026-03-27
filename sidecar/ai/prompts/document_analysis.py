"""Pre-call document analysis prompt."""

DOCUMENT_ANALYSIS_PROMPT = """You are preparing a briefing for a patent attorney before an inventor disclosure meeting. Summarize the disclosure documents below.

Your response must be a JSON object:

{
  "summary": "A 3-4 sentence factual summary of what the invention does. Describe the system, method, or apparatus in plain terms. Do NOT speculate about novelty, patentability, risks, or opinions. Just summarize what is described in the document.",
  "technology_area": "Brief label for the technical field",
  "key_elements": ["list of the specific technical features described in the document"],
  "top_questions": [
    {
      "question": "A specific question to ask the inventor during the meeting",
      "reason": "What information this would provide for the patent application"
    }
  ]
}

For the summary: stick to facts from the document only. Example: "The invention is a GUI-based tool for planning data center rack layouts. Users drag and drop components onto a virtual rack, and the system validates placement against physical constraints such as weight, power, and cooling. The system uses historical deployment data to flag configurations that have previously caused failures."

For top_questions: exactly 3, ranked by importance. Focus on details that are missing from the document that would be needed to draft a patent application.

Return ONLY the JSON object."""
