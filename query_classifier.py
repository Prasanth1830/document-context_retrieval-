import google.generativeai as genai
import logging

logger = logging.getLogger("document-context-retrieval-system")

PATTERNS = [
    "summarize",
    "key_risks",
    "main_parties",
    "date_period",
    "recommendations",
    "topic_check",
    "statistics",
    "sections_covered",
    "gaps_missing",
    "term_explain",
    "other"
]

def classify_query(user_query: str) -> str:
    try:
        model = genai.GenerativeModel("gemini-2.5-flash")
        
        prompt = f"""
        Classify the following user query into EXACTLY ONE of these categories:
        1. summarize (e.g. 'summarize this document', 'what is this about')
        2. key_risks (e.g. 'key risks', 'what are the dangers', 'risks mentioned')
        3. main_parties (e.g. 'main people', 'parties involved', 'who is in this')
        4. date_period (e.g. 'date covered', 'time period', 'when did this happen')
        5. recommendations (e.g. 'recommendations', 'conclusions', 'what should we do')
        6. topic_check (e.g. 'does it mention X', 'is Y in here')
        7. statistics (e.g. 'numbers', 'statistics', 'how many')
        8. sections_covered (e.g. 'sections', 'what topics are covered')
        9. gaps_missing (e.g. 'anything missing', 'what is unclear')
        10. term_explain (e.g. 'what does X mean', 'explain Y')
        11. other (for any specific factual questions that don't fit above)
        
        Output ONLY the category name exactly as written (e.g. 'summarize'). Do not include numbers or quotes.
        
        User query: {user_query}
        Category:"""
        
        resp = model.generate_content(prompt)
        result = resp.text.strip().lower()
        
        # Ensure it matches one of the expected patterns
        if result in PATTERNS:
            return result
        return "other"
    except Exception as e:
        logger.error(f"Failed to classify query: {str(e)}")
        return "other"
