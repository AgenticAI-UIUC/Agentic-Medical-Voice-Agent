from __future__ import annotations

from typing import Any

# Keep these IDs in sync with backend/seed.sql.
SPECIALTY_IDS = {
    "general_practice": "a0000000-0000-0000-0000-000000000001",
    "cardiology": "a0000000-0000-0000-0000-000000000002",
    "dermatology": "a0000000-0000-0000-0000-000000000003",
    "orthopedics": "a0000000-0000-0000-0000-000000000004",
    "neurology": "a0000000-0000-0000-0000-000000000005",
    "gastroenterology": "a0000000-0000-0000-0000-000000000006",
    "psychiatry": "a0000000-0000-0000-0000-000000000007",
    "ophthalmology": "a0000000-0000-0000-0000-000000000008",
    "ent": "a0000000-0000-0000-0000-000000000009",
    "pulmonology": "a0000000-0000-0000-0000-000000000010",
}


def _metadata(
    key: str,
    name: str,
    *,
    follow_up_questions: list[str],
    category: str = "symptom_cluster",
) -> dict[str, Any]:
    return {
        "specialty_id": SPECIALTY_IDS[key],
        "specialty_name": name,
        "category": category,
        "follow_up_questions": follow_up_questions,
        "source": "starter_triage_knowledge",
    }


KNOWLEDGE_CHUNKS: list[dict[str, Any]] = [
    {
        "content": (
            "Cardiology evaluates heart and cardiovascular symptoms. Patients may "
            "describe chest pressure, chest tightness, squeezing in the chest, a "
            "heavy weight on the chest, or feeling like an elephant is sitting on "
            "their chest. Related symptoms include pain spreading to the left arm, "
            "jaw, neck, or back, shortness of breath, sweating, nausea, dizziness, "
            "palpitations, high blood pressure, swollen ankles, or symptoms that get "
            "worse with exertion and improve with rest."
        ),
        "metadata": _metadata(
            "cardiology",
            "Cardiology",
            follow_up_questions=[
                "Does the chest discomfort spread to your arm, jaw, neck, or back?",
                "Does it get worse with physical activity or improve with rest?",
            ],
        ),
    },
    {
        "content": (
            "Pulmonology evaluates breathing and lung symptoms such as persistent "
            "cough, wheezing, chest tightness related to breathing, asthma symptoms, "
            "shortness of breath, noisy breathing, coughing up mucus, or breathing "
            "that is worse when lying down or walking. Patients may say they cannot "
            "catch their breath, their lungs feel tight, they are winded with small "
            "activities, or they have a long cough after a cold."
        ),
        "metadata": _metadata(
            "pulmonology",
            "Pulmonology",
            follow_up_questions=[
                "Is the breathing trouble worse at rest, with activity, or when lying down?",
                "Do you have wheezing, cough, or a history of asthma?",
            ],
        ),
    },
    {
        "content": (
            "Neurology evaluates brain, nerve, and spinal symptoms. This includes "
            "migraines, recurring headaches, severe headaches with light sensitivity, "
            "visual aura, flashing lights, zigzag lines, pain behind the eyes with "
            "headache, numbness, tingling, weakness, tremors, seizures, memory "
            "changes, balance problems, dizziness, or limbs feeling asleep and not "
            "waking up."
        ),
        "metadata": _metadata(
            "neurology",
            "Neurology",
            follow_up_questions=[
                "Do you have vision changes, light sensitivity, numbness, or tingling?",
                "Did the symptoms start suddenly or have they been recurring?",
            ],
        ),
    },
    {
        "content": (
            "Migraine with aura is commonly evaluated by neurology. Patients may "
            "describe sharp pain behind one or both eyes, pressure behind the eyes, "
            "or deep eye-area pain that happens with or before a headache. Visual "
            "aura can include flashing lights, zigzag lines, shimmering spots, blind "
            "spots, tunnel vision, or blurry vision before the pain starts. When eye "
            "pain is paired with flashing or zigzag visual changes before recurring "
            "head pain, this pattern fits migraine-with-aura style symptoms more "
            "than a primary eye condition."
        ),
        "metadata": _metadata(
            "neurology",
            "Neurology",
            follow_up_questions=[
                "Do the flashing lights or zigzag lines happen before the pain starts?",
                "Have these episodes happened more than once?",
            ],
        ),
    },
    {
        "content": (
            "Dermatology evaluates skin, hair, and nail concerns. Patients may have "
            "a rash, itchy skin, hives, acne, mole changes, flaky or irritated skin, "
            "skin discoloration, lesions that bleed or change shape, hair loss, nail "
            "changes, or a reaction after using a new product, medication, food, or "
            "environmental exposure."
        ),
        "metadata": _metadata(
            "dermatology",
            "Dermatology",
            follow_up_questions=[
                "Where is the skin problem and is it itchy, painful, or spreading?",
                "Have you noticed bleeding, color change, swelling, or a new exposure?",
            ],
        ),
    },
    {
        "content": (
            "Orthopedics evaluates bones, joints, muscles, ligaments, and injuries. "
            "This includes knee pain, shoulder pain, hip pain, back pain, neck pain, "
            "joint stiffness, swelling after an injury, sprains, fractures, sports "
            "injuries, reduced range of motion, difficulty walking, popping or "
            "grinding joints, and pain that worsens with movement or weight bearing."
        ),
        "metadata": _metadata(
            "orthopedics",
            "Orthopedics",
            follow_up_questions=[
                "Which joint or body part hurts, and did it start after an injury?",
                "Can you move it normally or put weight on it?",
            ],
        ),
    },
    {
        "content": (
            "Gastroenterology evaluates digestive symptoms such as stomach pain, "
            "abdominal cramps, nausea, vomiting, heartburn, reflux, bloating, "
            "diarrhea, constipation, blood in stool, trouble swallowing, pain after "
            "eating, or a burning feeling in the upper abdomen or chest that seems "
            "related to meals."
        ),
        "metadata": _metadata(
            "gastroenterology",
            "Gastroenterology",
            follow_up_questions=[
                "Where is the abdominal discomfort and does eating change it?",
                "Have you had vomiting, diarrhea, constipation, or heartburn?",
            ],
        ),
    },
    {
        "content": (
            "Psychiatry evaluates mental health and behavioral symptoms. Patients "
            "may describe anxiety, panic attacks, depression, low mood, loss of "
            "interest, insomnia, trouble sleeping, excessive stress, racing thoughts, "
            "difficulty concentrating, appetite changes, mood swings, or symptoms "
            "that interfere with work, school, relationships, or daily activities."
        ),
        "metadata": _metadata(
            "psychiatry",
            "Psychiatry",
            follow_up_questions=[
                "How long have these feelings been going on?",
                "Are they affecting sleep, appetite, work, school, or relationships?",
            ],
        ),
    },
    {
        "content": (
            "Ophthalmology evaluates eye and vision symptoms. This includes blurry "
            "vision, eye pain, red eye, vision loss, double vision, halos around "
            "lights, discharge, eye injury, light sensitivity, dry eyes, or sudden "
            "changes in vision. Eye pain with redness or sudden vision loss needs "
            "prompt evaluation."
        ),
        "metadata": _metadata(
            "ophthalmology",
            "Ophthalmology",
            follow_up_questions=[
                "Is the vision change in one eye or both, and did it start suddenly?",
                "Do you have eye redness, discharge, injury, or light sensitivity?",
            ],
        ),
    },
    {
        "content": (
            "ENT evaluates ear, nose, and throat symptoms. This includes sore throat, "
            "ear pain, hearing loss, ringing in the ears, sinus pressure, facial "
            "pressure, nasal congestion, runny nose, nosebleeds, hoarseness, trouble "
            "swallowing, tonsil concerns, or repeated sinus or ear infections."
        ),
        "metadata": _metadata(
            "ent",
            "ENT",
            follow_up_questions=[
                "Is the problem mainly in your ears, nose, throat, or sinuses?",
                "Do you have hearing changes, congestion, facial pressure, or trouble swallowing?",
            ],
        ),
    },
    {
        "content": (
            "General Practice evaluates broad or unclear concerns, routine checkups, "
            "mild fever, fatigue, cold or flu symptoms, body aches, preventive care, "
            "medication questions, and symptoms that do not clearly point to a single "
            "specialty. A general practice visit can be a good first step when the "
            "patient is unsure which specialist they need."
        ),
        "metadata": _metadata(
            "general_practice",
            "General Practice",
            category="generalist_fallback",
            follow_up_questions=[
                "How long have you been feeling this way?",
                "Are the symptoms getting worse, staying the same, or improving?",
            ],
        ),
    },
]
