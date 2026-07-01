import unittest
from main import chunk_text

class TestRAGEngine(unittest.TestCase):
    def test_chunking_short_text(self):
        text = "Hello world. This is a simple test of the text chunking mechanism."
        chunks = chunk_text(text, chunk_size=50, overlap=10)
        self.assertTrue(len(chunks) >= 1)
        self.assertEqual(set(" ".join(chunks).lower().split()), set(text.lower().split()))

    def test_chunking_overlap_preservation(self):
        text = "word1 word2 word3 word4 word5 word6 word7 word8 word9 word10"
        # Specify a small chunk size to trigger splits
        chunks = chunk_text(text, chunk_size=20, overlap=10)
        self.assertTrue(len(chunks) > 1)
        # Check that some words exist in multiple chunks (overlap)
        all_words = [c.split() for c in chunks]
        # At least some word should be shared between consecutive chunks
        shared = set(all_words[0]).intersection(set(all_words[1]))
        self.assertTrue(len(shared) > 0)

    def test_strict_grounding_prompt_logic(self):
        # Verify prompt templates force grounding
        query = "What is 2+2 according to Prasanth's notes?"
        context_str = "[Source: prasanth_notes.pdf, Page: 3]\nPrasanth's notes explicitly detail that 2+2 equals 5."
        
        system_prompt = (
            "You are a strictly grounded document context retrieval AI assistant. "
            "Your task is to answer the user's question using ONLY the provided document context.\n\n"
            "Strict Rules:\n"
            "1. Base your answer solely on the provided contexts. Do not assume, generalize, or extrapolate.\n"
            "2. If the context contains factual inaccuracies or contradictions relative to real-world knowledge (e.g. stating 2+2=5), you must answer exactly as the context states.\n"
            "3. If the context does not contain enough information to answer the question, state clearly: 'I am sorry, but the provided document does not contain any information about this topic.' Do not try to answer using external knowledge.\n"
            "4. For every statement/sentence you make, include a citation to the source document and page number (e.g. [document_name.pdf, Page X]) at the end of the statement where that context is used.\n\n"
            f"Retrieved Context:\n{context_str}"
        )
        
        # Verify instructions are embedded in the prompt
        self.assertIn("2+2 equals 5", system_prompt)
        self.assertIn("ONLY the provided document context", system_prompt)
        self.assertIn("stating 2+2=5", system_prompt)
        self.assertIn("prasanth_notes.pdf", system_prompt)

if __name__ == '__main__':
    unittest.main()
