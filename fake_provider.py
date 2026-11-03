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
        if "TASK: Read one answer the learner just gave" in s:
            self.calls.append("coach.assess")
            nervous = "nervous" in user.lower() or "sorry" in user.lower()
            return json.dumps({"primary_emotion": "nervous" if nervous else "focused",
                               "emotions": [{"label": "nervous" if nervous else "focused", "intensity": 7},
                                            {"label": "hesitant", "intensity": 4}],
                               "confidence": 3 if nervous else 7, "calm": 3 if nervous else 7, "fear_of_speaking": 7 if nervous else 3,
                               "energy": 5, "evidence": ["Apologised twice", "Took 5s before the first word"],
                               "what_went_well": ["You named retrieval correctly"],
                               "reframe": {"thought": "I'm bad at this", "better": "I'm learning this, and I already know the core idea"},
                               "technique": {"name": "Box breathing", "why": "Slows your pace", "steps": ["In 4", "Hold 4", "Out 4", "Hold 4"], "seconds": 60},
                               "micro_exercise": "Say your first sentence again, slower, with a pause after it.",
                               "power_phrase": "Let me walk you through how RAG works.",
                               "mentor_message": "You know more than you think. Slow down and let your knowledge show.",
                               "next_focus": "Start answers with one clear sentence", "concern": False})
        if "private one-to-one mentoring chat" in s:
            self.calls.append("coach.chat")
            return json.dumps({"reply": "That freeze is very common. Let's practise a 3-breath reset.",
                               "technique": {"name": "3-breath reset", "steps": ["Breathe out slowly", "Plant your feet", "Say your first sentence"]},
                               "concern": False})
        if "personal confidence growth plan" in s:
            self.calls.append("coach.journey")
            return json.dumps({"summary": "Confidence is rising.", "patterns": ["Nervous at the start of sessions"],
                               "strengths": ["Persistence"],
                               "exposure_ladder": [{"step": f"Step {i}", "goal": "done"} for i in range(1, 6)],
                               "daily_routine": ["2 minutes of out-loud answers"], "affirmation": "I explain clearly when I slow down."})
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

    def see(self, system, prompt, image, mime="image/jpeg", max_tokens=900):
        self.calls.append("presence.see")
        assert image, "no image passed"
        return json.dumps({"person_visible": True, "eye_contact": 6, "posture": 7, "framing": 5, "lighting": 4,
                           "expression": 7, "background": 8, "overall": 6,
                           "observations": ["Your eyes are on the screen, not the lens"],
                           "tips": ["Raise the laptop so the camera is at eye level", "Face a window for softer light"],
                           "encouragement": "Good energy - small setup tweaks will lift it."})
