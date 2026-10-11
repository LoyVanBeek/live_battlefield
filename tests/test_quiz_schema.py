"""Validate the quiz JSON schema against example data.

The schema lives in docs/quiz_questions.schema.json and documents the
export/import format used by the shared quiz editor.  These tests prove it is
valid JSON Schema and accurately describes the real quiz question shape.
"""

import json
from pathlib import Path

import jsonschema
import pytest

SCHEMA_PATH = Path(__file__).parents[1] / "docs" / "quiz_questions.schema.json"
SCHEMA = json.loads(SCHEMA_PATH.read_text())

# ---------------------------------------------------------------------------
# Schema syntax
# ---------------------------------------------------------------------------

def test_schema_is_valid_json_schema():
    """The file itself is a valid draft 2020-12 JSON Schema document."""
    jsonschema.Draft202012Validator.check_schema(SCHEMA)


# ---------------------------------------------------------------------------
# Valid quizzes
# ---------------------------------------------------------------------------

VALID_QUIZ = [
    {
        "question_text": "What is the capital of France?",
        "bomb_value": 5,
        "source_url": "https://en.wikipedia.org/wiki/Paris",
        "answers": [
            {"answer_text": "Paris", "bomb_value": 5, "is_correct": True},
            {"answer_text": "London", "bomb_value": 0, "is_correct": False},
        ],
    },
    {
        "question_text": "What is 2+2?",
        "bomb_value": 4,
        "source_url": None,
        "answers": [
            {"answer_text": "4", "bomb_value": 4, "is_correct": True},
            {"answer_text": "5", "bomb_value": 0, "is_correct": False},
        ],
    },
]


def test_valid_quiz_passes():
    jsonschema.validate(VALID_QUIZ, SCHEMA)


def test_minimal_quiz_passes():
    """Single question, single answer, empty source."""
    quiz = [
        {
            "question_text": "Q",
            "bomb_value": 1,
            "source_url": "",
            "answers": [
                {"answer_text": "A", "bomb_value": 1, "is_correct": True},
            ],
        },
    ]
    jsonschema.validate(quiz, SCHEMA)


def test_empty_quiz_passes():
    """An empty array is valid (no questions)."""
    jsonschema.validate([], SCHEMA)


def test_http_source_url_passes():
    """Plain http (not https) is permitted."""
    quiz = [
        {
            "question_text": "Q",
            "bomb_value": 1,
            "source_url": "http://example.com/verify",
            "answers": [
                {"answer_text": "A", "bomb_value": 1, "is_correct": True},
            ],
        },
    ]
    jsonschema.validate(quiz, SCHEMA)


# ---------------------------------------------------------------------------
# Invalid quizzes
# ---------------------------------------------------------------------------

def test_not_an_array():
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate({"not": "a quiz"}, SCHEMA)


def test_missing_question_text():
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(
            [
                {
                    "bomb_value": 1,
                    "source_url": None,
                    "answers": [
                        {"answer_text": "A", "bomb_value": 1, "is_correct": True},
                    ],
                },
            ],
            SCHEMA,
        )


def test_empty_question_text():
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(
            [
                {
                    "question_text": "",
                    "bomb_value": 1,
                    "source_url": None,
                    "answers": [
                        {"answer_text": "A", "bomb_value": 1, "is_correct": True},
                    ],
                },
            ],
            SCHEMA,
        )


def test_no_answers():
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(
            [
                {
                    "question_text": "Q",
                    "bomb_value": 0,
                    "source_url": None,
                    "answers": [],
                },
            ],
            SCHEMA,
        )


def test_two_correct_answers():
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(
            [
                {
                    "question_text": "Q",
                    "bomb_value": 5,
                    "source_url": None,
                    "answers": [
                        {"answer_text": "A", "bomb_value": 5, "is_correct": True},
                        {"answer_text": "B", "bomb_value": 0, "is_correct": True},
                    ],
                },
            ],
            SCHEMA,
        )


def test_no_bomb_yielding_answer():
    """Every answer has bomb_value 0 — the invariant requires at least one ≥1."""
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(
            [
                {
                    "question_text": "Q",
                    "bomb_value": 0,
                    "source_url": None,
                    "answers": [
                        {"answer_text": "A", "bomb_value": 0, "is_correct": True},
                        {"answer_text": "B", "bomb_value": 0, "is_correct": False},
                    ],
                },
            ],
            SCHEMA,
        )


def test_javascript_source_rejected():
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(
            [
                {
                    "question_text": "Q",
                    "bomb_value": 1,
                    "source_url": "javascript:alert(1)",
                    "answers": [
                        {"answer_text": "A", "bomb_value": 1, "is_correct": True},
                    ],
                },
            ],
            SCHEMA,
        )


def test_data_source_rejected():
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(
            [
                {
                    "question_text": "Q",
                    "bomb_value": 1,
                    "source_url": "data:text/html,<script>alert(1)</script>",
                    "answers": [
                        {"answer_text": "A", "bomb_value": 1, "is_correct": True},
                    ],
                },
            ],
            SCHEMA,
        )


def test_scheme_less_source_is_not_http():
    """A scheme-less string like 'example.com' is not an http(s) URL and
    should be rejected — the server normalises it on save, but the canonical
    stored form always has the scheme."""
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(
            [
                {
                    "question_text": "Q",
                    "bomb_value": 1,
                    "source_url": "example.com/verify",
                    "answers": [
                        {"answer_text": "A", "bomb_value": 1, "is_correct": True},
                    ],
                },
            ],
            SCHEMA,
        )


def test_negative_answer_bomb_value():
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(
            [
                {
                    "question_text": "Q",
                    "bomb_value": 1,
                    "source_url": None,
                    "answers": [
                        {"answer_text": "A", "bomb_value": -1, "is_correct": True},
                    ],
                },
            ],
            SCHEMA,
        )


def test_non_boolean_is_correct():
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(
            [
                {
                    "question_text": "Q",
                    "bomb_value": 1,
                    "source_url": None,
                    "answers": [
                        {"answer_text": "A", "bomb_value": 1, "is_correct": "yes"},
                    ],
                },
            ],
            SCHEMA,
        )


def test_unknown_property_rejected():
    """additionalProperties: false prevents typos like 'anwser_text'."""
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(
            [
                {
                    "question_text": "Q",
                    "bomb_value": 1,
                    "source_url": None,
                    "anwser_text": "typo",
                    "answers": [
                        {"answer_text": "A", "bomb_value": 1, "is_correct": True},
                    ],
                },
            ],
            SCHEMA,
        )