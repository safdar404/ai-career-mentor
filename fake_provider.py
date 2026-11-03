"""A deterministic stand-in for Claude/OpenAI used only in tests.

It inspects the system prompt to see which agent is calling and returns a
valid JSON response for that agent's contract. `weak=True` simulates a
learner who cannot answer.
"""
from __future__ import annotations

import json


class FakeProvider:
    name = "Fake"
    model = "fake-1"

    def __init__(self, weak: bool = False, broken_json_once: bool = False):
        self.weak = weak
        self.calls: list[str] = []
        self._broken = broken_json_once

    def complete(self, system, messages, max_tokens=1500, temperature=0.4):
        user = messages[-1]["content"]
        if self._broken:
            self._broken = False
            self.calls.append("broken")
            return "Sure! Here is the result: {not json"
        s = system
        if "Ask exactly ONE behavioural" in s:
            self.calls.append("hr.ask")
            return json.dumps({"question": "Tell me about yourself.", "topic": "pro.self_intro", "kind": "new"})
        if "ask exactly ONE interview question" in s:
            self.calls.append("interviewer.ask")
            topic = "genai.rag"
            if "You MUST ask about topic" in user:
                topic = user.split("You MUST ask about topic ")[1].split(" ")[0]
            return json.dumps({"question": f"How would you explain {topic}?", "topic": topic, "kind": "new"})
        if "Evaluate this behavioural/HR answer" in s or "Evaluate the candidate's answer for TECHNICAL" in s:
            self.calls.append("evaluate")
            v = 2 if self.weak else 7
            return json.dumps({"technical_accuracy": v, "conceptual_understanding": v, "practical_knowledge": v,
                               "overall_interview_performance": v, "attempted": not self.weak,
                               "what_was_correct": ["Mentioned retrieval"], "misunderstood": ["Confused RAG with fine-tuning"] if self.weak else [],
                               "incorrect_concepts": [], "missing_concepts": ["chunking"],
                               "correct_explanation": "RAG retrieves documents...", "improved_answer": "I would...",
                               "exercise": "Build a small RAG demo", "follow_up_needed": False,
                               "star": {"situation": "x", "task": "", "action": "y", "result": ""}})
        if "business English and interview communication coach" in s:
            self.calls.append("english.evaluate")
            return json.dumps({"english_grammar": 6, "vocabulary": 6, "sentence_structure": 5, "fluency_clarity": 6,
                               "confidence": 5, "professional_communication": 6,
                               "grammar_mistakes": [{"original": "I am having experience", "correction": "I have experience",
                                                     "explanation": "Stative verbs are not used in continuous form"}],
                               "unnatural_expressions": [], "corrected_answer": "I have experience.",
                               "natural_version": "I have hands-on experience.", "why_better": "More direct.",
                               "new_vocabulary": [{"term": "hands-on", "meaning": "practical", "example": "hands-on experience"}],
                               "words_to_practise": [{"word": "development", "stress": "deVELopment"}],
                               "practice_sentence": "I have hands-on experience with RAG."})
        if "role-playing to help a learner" in s:
            self.calls.append("english.converse")
            return json.dumps({"line": "Morning! How was your weekend?", "tip": "Answer with one detail."})
        if "learning analyst" in s:
            self.calls.append("gaps")
            return json.dumps({"gaps": [{"category": "technical", "topic": "genai.rag", "description": "Confuses RAG and fine-tuning",
                                         "severity": 2, "recommended_exercise": "Compare both in a table", "evidence": "said RAG retrains"},
                                        {"category": "communication", "topic": "comm.grammar", "description": "Continuous tense with stative verbs",
                                         "severity": 1, "recommended_exercise": "Drill", "evidence": "I am having"}]})
        if "Teach the topic" in s:
            self.calls.append("mentor.teach")
            return json.dumps({"title": "RAG", "simple_explanation": "Look up then answer.", "analogy": "Open-book exam",
                               "example": "```python\nprint('hi')\n```", "key_points": ["retrieve", "generate"],
                               "common_mistakes": ["thinking it retrains"], "urdu_note": "",
                               "check_question": "Explain RAG to a manager."})
        if "Create one Python coding challenge" in s:
            self.calls.append("mentor.challenge")
            return json.dumps({"title": "Chunk text", "problem": "Split text into chunks", "requirements": ["overlap"],
                               "starter_code": "def chunk(text, size, overlap):\n    pass",
                               "test_cases": [{"input": "chunk('abcdef',4,2)", "expected": "['abcd','cdef']"}], "hints": []})
        if "code review" in s:
            self.calls.append("mentor.review")
            return json.dumps({"correctness": 6, "code_quality": 7, "problem_solving": 6, "overall": 6, "summary": "Okay",
                               "likely_test_results": [], "issues": [{"severity": "medium", "issue": "No validation", "fix": "check size>overlap"}],
                               "what_was_good": ["clear names"], "improved_code": "...", "next_step": "add tests"})
        if "90-day roadmap" in s:
            self.calls.append("mentor.roadmap")
            return json.dumps({"phases": [{"phase": "P1", "days": "1-15", "focus": "f", "goals": ["g"], "daily_activities": ["a"], "milestone": "m"}],
                               "rationale": "Based on gaps"})
        if "Summarise one practice session" in s:
            self.calls.append("progress.session")
            return json.dumps({"headline": "Solid start", "strengths": ["a"], "weaknesses": ["b"], "next_steps": ["c"], "readiness_comment": "d"})
        if "weekly progress report" in s:
            self.calls.append("progress.weekly")
            return json.dumps({"english_communication": "Improving", "technical_knowledge": "RAG weak"})
        raise AssertionError("Unexpected prompt: " + s[:200])
