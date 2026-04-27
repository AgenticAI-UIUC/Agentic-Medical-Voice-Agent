from __future__ import annotations

import pytest

from app.api.vapi_tools import identify_patient
from tests.support import MockQuery, MockSupabase


def test_normalize_uin_handles_spoken_and_punctuated_values() -> None:
    assert (
        identify_patient._normalize_uin("one two three-four five six seven eight nine")
        == "123456789"
    )
    assert identify_patient._normalize_uin("123-45-6789") == "123456789"


def test_lookup_patient_requires_uin() -> None:
    result = identify_patient._lookup_patient({}, {})

    assert result["status"] == "INVALID"
    assert result["reason"] == "MISSING_UIN"
    assert "didn't catch your UIN" in result["message"]


def test_lookup_patient_rejects_non_9_digit_uin() -> None:
    result = identify_patient._lookup_patient({"uin": "one two three"}, {})

    assert result["status"] == "INVALID"
    assert result["reason"] == "WRONG_LENGTH"
    assert result["expected_digits"] == 9
    assert result["received_digits"] == 3
    assert "9-digit university UIN" in result["message"]
    assert "I heard 3 digits" in result["message"]


def test_lookup_patient_returns_not_found_with_normalized_uin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sb = MockSupabase(tables={"patients": [MockQuery(data=[])]})
    monkeypatch.setattr(identify_patient, "get_supabase", lambda: sb)

    result = identify_patient._lookup_patient(
        {"uin": "one two three four five six seven eight nine"}, {}
    )

    assert result["status"] == "NOT_FOUND"
    assert result["uin_searched"] == "123456789"


def test_lookup_patient_returns_patient_record(monkeypatch: pytest.MonkeyPatch) -> None:
    patient_rows = [
        {
            "id": "patient-1",
            "uin": "123456789",
            "full_name": "Sam Student",
            "phone": "2175551212",
            "email": "sam@example.com",
            "allergies": "peanuts",
        }
    ]
    sb = MockSupabase(tables={"patients": [MockQuery(data=patient_rows)]})
    monkeypatch.setattr(identify_patient, "get_supabase", lambda: sb)

    result = identify_patient._lookup_patient({"uin": "123 456 789"}, {})

    assert result["status"] == "FOUND"
    assert result["patient_id"] == "patient-1"
    assert result["full_name"] == "Sam Student"


@pytest.mark.parametrize(
    ("args", "message_fragment"),
    [
        ({"uin": "123"}, "I heard 3 digits"),
        ({"uin": "123456789"}, "full name"),
        ({"uin": "123456789", "full_name": "Sam Student"}, "valid phone number"),
    ],
)
def test_register_patient_validates_required_fields(
    args: dict[str, str], message_fragment: str
) -> None:
    result = identify_patient._register_patient(args, {})

    assert result["status"] == "INVALID"
    assert message_fragment in result["message"]


def test_register_patient_invalid_uin_includes_digit_counts() -> None:
    result = identify_patient._register_patient({"uin": "12345678"}, {})

    assert result["status"] == "INVALID"
    assert result["reason"] == "WRONG_LENGTH"
    assert result["expected_digits"] == 9
    assert result["received_digits"] == 8
    assert (
        result["message"]
        == "I heard 8 digits, but I need your 9-digit university UIN to register you."
    )


def test_register_patient_returns_existing_patient_for_duplicate_uin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    existing = [{"id": "patient-1", "uin": "123456789", "full_name": "Sam Student"}]
    sb = MockSupabase(tables={"patients": [MockQuery(data=existing)]})
    monkeypatch.setattr(identify_patient, "get_supabase", lambda: sb)

    result = identify_patient._register_patient(
        {"uin": "123456789", "full_name": "Sam Student", "phone": "217-555-1212"},
        {},
    )

    assert result["status"] == "ALREADY_EXISTS"
    assert result["patient_id"] == "patient-1"


def test_register_patient_allows_duplicate_phone(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    no_uin_match = MockQuery(data=[])
    insert_query = MockQuery(data=[{"id": "patient-2"}])
    sb = MockSupabase(tables={"patients": [no_uin_match, insert_query]})
    monkeypatch.setattr(identify_patient, "get_supabase", lambda: sb)

    result = identify_patient._register_patient(
        {"uin": "123456789", "full_name": "Sam Student", "phone": "(217) 555-1212"},
        {},
    )

    assert result["status"] == "REGISTERED"
    assert result["patient_id"] == "patient-2"
    assert insert_query.inserted_rows[0]["phone"] == "2175551212"


def test_register_patient_inserts_new_patient(monkeypatch: pytest.MonkeyPatch) -> None:
    no_uin_match = MockQuery(data=[])
    insert_query = MockQuery(data=[{"id": "patient-3"}])
    sb = MockSupabase(tables={"patients": [no_uin_match, insert_query]})
    monkeypatch.setattr(identify_patient, "get_supabase", lambda: sb)

    result = identify_patient._register_patient(
        {
            "uin": "one two three four five six seven eight nine",
            "full_name": "Sam Student",
            "phone": "(217) 555-1212",
            "email": " sam@example.com ",
            "allergies": " peanuts ",
        },
        {},
    )

    assert result["status"] == "REGISTERED"
    assert result["patient_id"] == "patient-3"
    assert result["message"] == "Registration complete for Sam Student."
    assert insert_query.inserted_rows[0] == {
        "uin": "123456789",
        "full_name": "Sam Student",
        "phone": "2175551212",
        "email": "sam@example.com",
        "allergies": "peanuts",
    }
