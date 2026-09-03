"""题目数据模型"""
from dataclasses import dataclass, field
from typing import List, Optional
from enum import Enum


class ExamType(str, Enum):
    """考试类型"""
    AP_PHYSICS_1 = "ap_physics_1"
    PHYSICS_BOWL_D1 = "physics_bowl_d1"


class QuestionType(str, Enum):
    """题型"""
    MULTIPLE_CHOICE = "multiple_choice"
    FREE_RESPONSE = "free_response"


@dataclass
class Question:
    """题目对象"""
    exam_type: str
    question_text: str
    correct_answer: str
    question_type: str = QuestionType.MULTIPLE_CHOICE.value
    external_id: str = ""
    source: str = ""
    topic: str = ""
    difficulty: str = "medium"
    options: List[str] = field(default_factory=list)
    explanation: str = ""

    def to_dict(self) -> dict:
        return {
            "exam_type": self.exam_type,
            "question_type": self.question_type,
            "source": self.source,
            "external_id": self.external_id,
            "topic": self.topic,
            "difficulty": self.difficulty,
            "question_text": self.question_text,
            "options": self.options,
            "correct_answer": self.correct_answer,
            "explanation": self.explanation,
        }
