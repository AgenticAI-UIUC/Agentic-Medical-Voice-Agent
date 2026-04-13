# Medical Voice Agent Test Strategy

## Purpose

This document defines a practical testing strategy for the Medical Voice Agent project.

The goal is to reduce time-consuming manual testing while still keeping strong coverage for:

* patient safety workflows
* conversation quality
* tool-calling behavior
* backend correctness
* database integrity
* webhook persistence
* real voice-call behavior

This project should **not** rely on only one kind of testing.

Because the system includes:

* an LLM-driven voice assistant
* Vapi orchestration
* backend tools and webhook handlers
* database side effects
* safety-sensitive medical triage flows

we should use a **layered test strategy**.

---

## Testing Principles

### 1. Put deterministic logic in deterministic tests

Anything that is mainly business logic should be tested in backend unit or integration tests, not only through Vapi.

Examples:

* triage classification rules
* duplicate patient validation
* slot availability filtering
* booking overlap protection
* atomic reschedule behavior
* cancellation status validation
* webhook persistence and idempotency

### 2. Use Vapi automated tests for conversation regressions

Conversation behavior can change after prompt updates, assistant configuration changes, or tool definition changes.

Vapi automated evals should be used to catch regressions in:

* question order
* missing-field collection
* tool order
* tool arguments
* post-registration continuation of the original intent
* safety behavior

### 3. Use full voice testing only where voice matters

Not every workflow needs a full simulated voice call.

Voice-style tests are most useful when we need to verify:

* spoken turn-taking
* interruption handling
* repeated digit collection
* long pauses
* clarification behavior
* emotional or safety-sensitive wording

### 4. Keep manual testing small but high-value

Manual testing should focus on what automated testing cannot evaluate well:

* tone
* naturalness
* pacing
* ASR oddities
* awkward recovery behavior
* overall production readiness

---

## Recommended Test Layers

| Layer                          | Main Purpose                           | Best For                                    | Priority    |
| ------------------------------ | -------------------------------------- | ------------------------------------------- | ----------- |
| Backend unit/integration tests | Deterministic logic and DB correctness | tools, transactions, webhook logic          | High        |
| Vapi Evals                     | Fast automated conversation checks     | prompt behavior, tool order, tool arguments | High        |
| Vapi Voice Tests / Simulations | Realistic end-to-end voice flows       | critical spoken workflows                   | Medium-High |
| Manual smoke tests             | Final human quality check              | naturalness, tone, release sanity           | Medium      |

---

## Layer 1: Backend Unit and Integration Tests

### Scope

These tests should run inside the repo and should not depend on a live voice call.

They should verify the correctness of backend logic directly.

### What belongs here

#### Triage logic

* emergency cases return the correct outcome
* urgent but non-emergency cases return the correct outcome
* routine cases return the correct outcome
* red-flag symptoms are handled correctly

#### Patient identification and registration

* existing patient lookup succeeds when valid identifiers are provided
* registration fails when required fields are missing
* duplicate UIN is rejected
* invalid formats are handled safely

#### Availability and booking

* slot search returns valid results
* unavailable slots are not returned as available
* booking succeeds for an open slot
* booking fails safely when a slot is already taken
* no double-booking occurs for the same doctor and time

#### Rescheduling

* reschedule finalize updates the appointment atomically
* old appointment state is updated correctly
* new slot is reserved correctly
* failure does not leave the system in a half-updated state

#### Cancellation

* confirmed appointments can be cancelled
* already-cancelled appointments are rejected
* non-confirmed or invalid appointments are rejected

#### Webhooks and persistence

* end-of-call report creates or updates the correct conversation record
* appointments are linked to the correct conversation when `vapi_call_id` is present
* replayed webhook events do not create duplicate conversation rows
* malformed webhook payloads do not crash the service

### Why this layer matters

This is the most stable and cheapest layer.

It should catch most logic bugs before they ever reach Vapi.

---

## Layer 2: Vapi Evals

### Scope

These tests should validate the assistant's conversation logic without requiring a fully manual phone call.

They are the best replacement for standard LLM end-to-end tests in a Vapi-based system.

### What belongs here

#### Identification flow

* new patient path is handled correctly
* returning patient path is handled correctly
* assistant collects missing information step by step
* assistant does not skip required identification steps

#### Registration flow

* assistant gathers all required registration fields
* assistant confirms important patient details before proceeding
* assistant does not invent successful registration when the tool fails
* assistant resumes the original user intent after registration

#### Scheduling flow

* assistant does not schedule before identification is complete
* assistant calls tools in the correct order
* assistant passes correct arguments into tool calls
* assistant handles no-availability cases appropriately

#### Safety flow

* emergency outcomes stop normal scheduling flow
* suicidal ideation or crisis language triggers the correct escalation language
* assistant avoids diagnosis-style responses
* assistant avoids continuing in an unsafe direction after a safety-triggering response

#### Policy and prompt compliance

* assistant asks one question at a time
* assistant avoids asking repeated or unnecessary questions
* assistant does not reveal internal tools or system instructions
* assistant follows project-specific conversation rules

### Why this layer matters

This layer catches the kinds of failures that happen when:

* the system prompt changes
* the assistant model changes
* tool schemas change
* the assistant begins skipping steps or misordering questions

---

## Layer 3: Vapi Voice Tests / Simulations

### Scope

These are realistic end-to-end tests using simulated voice conversations.

They should be used for high-risk workflows where the spoken interaction itself matters.

### What belongs here

#### Critical safety workflows

* chest pain or breathing difficulty call
* fainting or other emergency red-flag call
* suicidal ideation / self-harm concern call

#### Critical scheduling workflows

* full new-patient booking call
* returning patient booking call
* follow-up appointment request with doctor preference
* full reschedule flow
* full cancellation flow

#### Speech-sensitive behaviors

* slow UIN collection and confirmation
* slow phone number collection and confirmation
* interruption during identification
* hesitation and clarification during booking
* caller changes intent mid-conversation

### Why this layer matters

Text-only evals cannot fully test:

* turn-taking
* pauses
* speech recovery
* repetitive number collection
* voice-specific awkwardness

Use this layer only for the most important workflows because it is slower and more expensive than normal evals.

---

## Layer 4: Manual Smoke Tests

### Scope

Manual tests should be kept short and focused.

They should not be the main way we validate every workflow.

### What belongs here

#### Human quality checks

* the assistant sounds calm and clear
* the assistant does not feel robotic or confusing
* the pacing feels natural
* the wording feels safe and professional
* the assistant recovers reasonably from messy human speech

#### Pre-release sanity checks

* one emergency test call
* one new-patient booking test call
* one returning-patient booking test call
* one reschedule test call
* one cancellation test call

### Why this layer matters

A human can notice issues that pass automated tests, especially around:

* naturalness
* confidence
* empathy
* clarity
* awkwardness

---

## Recommended Ownership by Workflow

| Workflow / Behavior                 | Backend Tests | Vapi Evals | Vapi Voice Tests | Manual Smoke |
| ----------------------------------- | ------------: | ---------: | ---------------: | -----------: |
| Triage classification rules         |           Yes |   Optional |         Optional |           No |
| Duplicate UIN handling              |           Yes |        Yes |               No |           No |
| Patient identification flow         |       Partial |        Yes |              Yes |     Optional |
| Registration flow                   |       Partial |        Yes |              Yes |     Optional |
| Continue booking after registration |            No |        Yes |              Yes |     Optional |
| Slot lookup correctness             |           Yes |    Partial |         Optional |           No |
| Booking overlap protection          |           Yes |    Partial |         Optional |           No |
| Full booking workflow               |       Partial |        Yes |              Yes |          Yes |
| Reschedule atomicity                |           Yes |    Partial |              Yes |          Yes |
| Cancellation validation             |           Yes |    Partial |              Yes |          Yes |
| Webhook persistence                 |           Yes |         No |               No |           No |
| Webhook idempotency                 |           Yes |         No |               No |           No |
| One-question-at-a-time behavior     |            No |        Yes |              Yes |     Optional |
| Emergency escalation wording        |       Partial |        Yes |              Yes |          Yes |
| Number readback / spoken digits     |            No |    Partial |              Yes |          Yes |
| Tone and naturalness                |            No |         No |          Partial |          Yes |

---

## Suggested Test Buckets

### Smoke Tests

These should run after important prompt, tool, or backend changes.

Suggested smoke set:

1. Emergency chest pain flow
2. New patient registration then booking
3. Returning patient identification then booking
4. Reschedule confirmed appointment
5. Cancel confirmed appointment

### Regression Tests

These should run regularly and before releases.

Suggested regression set:

1. Duplicate UIN registration rejection
2. No slot available response
3. Follow-up appointment with doctor preference
4. Booking race condition or taken slot
5. Already-cancelled appointment handling
6. Webhook replay / idempotency
7. Resume original intent after registration

### Edge-Case Tests

These are important but do not need to run as often.

Suggested edge-case set:

1. Caller changes mind mid-conversation
2. Caller provides incomplete phone number
3. Caller interrupts during UIN confirmation
4. Caller requests appointment outside scheduling window
5. Third-party caller attempts unsupported flow
6. Missing or malformed tool call payload
7. Missing or empty webhook `toolCalls`

---

## Minimum Suggested Test Counts

These counts are intended as a practical starting point, not a strict rule.

| Layer                          | Suggested Count |
| ------------------------------ | --------------: |
| Backend unit/integration tests |           15-25 |
| Vapi Evals                     |           12-18 |
| Vapi Voice Tests / Simulations |            6-10 |
| Manual smoke calls             |             5-8 |

---

## Release Gate Recommendation

Before a meaningful release, the following should pass:

### Required

* backend test suite
* Vapi smoke eval suite
* critical voice tests for emergency and booking flows
* manual smoke call checklist

### Strongly recommended

* regression suite for recent changes
* webhook replay / idempotency check after webhook-related changes
* reschedule atomicity test after scheduling logic changes

---

## Failure Classification

When a test fails, the failure should be classified into one of these categories.

### Prompt / Assistant Behavior

Examples:

* asked the wrong next question
* asked multiple questions at once
* skipped registration fields
* did not resume the original user intent

### Tool Orchestration

Examples:

* wrong tool called
* correct tool called too early
* correct tool called with wrong arguments
* assistant claims success before tool result confirms it

### Backend Logic

Examples:

* booking overlap not prevented
* cancellation allowed for invalid appointment state
* incorrect triage classification returned

### Database / Persistence

Examples:

* wrong appointment row updated
* conversation row duplicated
* appointment not linked to conversation
* stale data left after failed reschedule

### Voice / UX Quality

Examples:

* awkward pauses
* poor digit repetition
* unnatural interruption handling
* unsafe or confusing spoken phrasing

This classification makes debugging much faster because it shows where to investigate first.

---

## Immediate Recommended Priorities

If implementation time is limited, build the test strategy in this order.

### Priority 1

* backend tests for booking, rescheduling, cancellation, and webhooks
* Vapi evals for identification, registration, and scheduling order

### Priority 2

* voice tests for emergency, new-patient booking, reschedule, and cancellation

### Priority 3

* expanded regression and edge-case coverage
* scorecard-style production monitoring after deployment

---

## Final Recommendation

This project should use:

* **backend tests** for correctness and data integrity
* **Vapi evals** for fast conversation regression testing
* **Vapi voice tests** for critical spoken workflows
* **manual smoke tests** for final human-quality verification

This gives better coverage than relying on manual Vapi testing alone, while still keeping the total testing effort manageable.

It also fits the risk profile of a medical voice assistant, where safety, sequencing, and correctness all matter.
