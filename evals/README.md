# Vapi Eval Starter Pack

This folder gives us a repo-owned starting point for Vapi conversation evals.

The goal is to keep the first eval suite:

- small enough to run often
- concrete enough to score consistently
- close to the checked-in prompt, tool contracts, and seed data

## What Is Here

- `smoke/SMK-01_emergency_chest_pain.yaml`
- `smoke/SMK-02_new_patient_booking.yaml`
- `smoke/SMK-03_resume_after_registration.yaml`
- `smoke/SMK-04_returning_patient_booking.yaml`
- `smoke/SMK-05_asap_morning_fallback.yaml`
- `smoke/SMK-06_successful_existing_patient_booking.yaml`
- `smoke/SMK-07_successful_reschedule.yaml`
- `smoke/SMK-08_successful_cancel.yaml`

These are not tied to a specific vendor export format yet. They are written as stable case specs so we can:

- copy them into Vapi evals manually today
- use them as transcript-review scorecards
- automate them later without redefining the assertions

## Before Running

1. Seed the database with [backend/seed.sql](/Users/henrylong/Desktop/medical_voice_agent/Agentic-Medical-Voice-Agent/backend/seed.sql:1) or reset to a known test environment.
2. Make sure the live assistant prompt matches [Medical Voice Agent — System Prompt.md](/Users/henrylong/Desktop/medical_voice_agent/Agentic-Medical-Voice-Agent/Medical Voice Agent — System Prompt.md:1).
3. Make sure the Vapi tool definitions match the current tool contracts in [README.md](/Users/henrylong/Desktop/medical_voice_agent/Agentic-Medical-Voice-Agent/README.md:452).
4. Capture the transcript, tool timeline, and `call.id` for each run.

## Data Notes

- `SMK-01` is non-mutating.
- `SMK-05` stops after slot presentation and should be non-mutating.
- `SMK-02`, `SMK-03`, `SMK-04`, `SMK-06`, `SMK-07`, and `SMK-08` mutate appointment or patient data. Run them in a disposable environment, or reset data between runs.
- Cases marked with `needs_fresh_uin: true` should use a UIN that does not already exist in `patients`.

## How To Score A Case

Treat each file as a checklist with four levels of assertions:

- `expected_tool_path`: tools that should happen in order
- `must_do`: conversation behaviors that must appear
- `must_not_do`: regressions we want to catch immediately
- `failure_signals`: concrete reasons to fail the run

If a run passes the tool path but fails the spoken behavior, it still fails the eval.

## Suggested First Smoke Suite

Run these after prompt edits, tool schema changes, or backend changes that touch booking flow:

1. `SMK-01` emergency escalation
2. `SMK-02` new-patient booking
3. `SMK-03` continue booking after registration
4. `SMK-04` returning-patient booking
5. `SMK-05` "as soon as possible" fallback when no morning slots exist

## Demo-Friendly Success Suite

If you want a live demo that shows clear successful workflows without registration, use:

1. `SMK-06` successful existing-patient booking
2. `SMK-07` successful reschedule
3. `SMK-08` successful cancellation

## Good Next Cases

Once this starter pack feels stable, the next high-value additions are:

- duplicate-UIN correction while preserving collected name and phone
- follow-up booking with `find_appointment(include_past=true)`
- reschedule no-change path when the patient keeps the original appointment
- cancellation decline path where the patient decides not to cancel
- taken-slot recovery after `book` returns `TAKEN`
