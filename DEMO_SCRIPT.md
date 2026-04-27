# Demo Script

This script is designed for a clean demo with the current seed data.

- It assumes you reran `backend/seed.sql` on the demo database before the demo.
- It keeps Henry Long on the booking and cancellation flow.
- It keeps Henry Mo on the reschedule flow.
- It uses paths that should have strong slot availability in the seeded data.

## Demo Accounts

- `Henry Long` — UIN `246813579`
- `Henry Mo` — UIN `135792468`

## Why These Paths Are Safe

- Henry Long's booking uses `headache`, which routes cleanly to `Neurology`.
- `Neurology` is covered by `Dr. Priya Patel`, who has seeded availability on Wednesday, Thursday, and Friday afternoons.
- Henry Mo already has one seeded `Orthopedics` appointment with `Dr. James Wilson`.
- Dr. James Wilson has many weekday slots in the seed, so rescheduling should have multiple options.

## Pre-Demo Checklist

1. Rerun `backend/seed.sql`.
2. Make sure Henry Long has no upcoming appointment before the demo starts.
3. Make sure Henry Mo has one upcoming confirmed appointment.
4. Run the demo in this order: Henry Long books, Henry Long cancels, then Henry Mo reschedules.
5. Accept the first slot the assistant offers unless you need to slow the demo down.

Optional quick SQL check:

```sql
select
  p.full_name,
  p.uin,
  a.status,
  d.full_name as doctor_name,
  a.start_at,
  a.reason
from patients p
left join appointments a on a.patient_id = p.id
left join doctors d on d.id = a.doctor_id
where p.full_name in ('Henry Long', 'Henry Mo')
order by p.full_name, a.start_at;
```

If you rerun the seed on `April 14, 2026`, Henry Mo's seeded appointment should be with `Dr. James Wilson` on `Wednesday, April 22, 2026 at 9:30 AM` Chicago time.



### Optional Database Reset Before Testing

If you want a clean test run in Supabase without rebuilding the schema, wipe this app's data first in the Supabase SQL Editor:

```sql
TRUNCATE TABLE
  public.appointments,
  public.conversations,
  public.doctor_blocks,
  public.doctor_availability,
  public.doctor_specialties,
  public.symptom_specialty_map,
  public.patients,
  public.doctors,
  public.specialties,
  public.conversations
RESTART IDENTITY CASCADE;
```

Then rerun the seed data:

```sql
-- paste backend/seed.sql into the SQL Editor
```





## Part 1: Henry Long Books an Appointment

Goal: show booking for an existing patient without registration.

Suggested spoken script:

```text
Henry Long: I'd like to make an appointment.

If asked whether you're new or returning:
Henry Long: I've been here before.

Henry Long: My UIN is 246 813 579.
Henry Long: Yes.

If asked what the visit is for:
Henry Long: I have a headache.

If asked whether you have a specialist preference:
Henry Long: I don't have a specialist preference.

If asked whether the suggested specialty sounds right:
Henry Long: Yes.

If asked for a doctor preference:
Henry Long: No preference.

If asked when you want to come in:
Henry Long: As soon as possible.

If asked morning or afternoon:
Henry Long: Afternoon.

When slots are offered:
Henry Long: I'll take the first one.
```

Operator note:

- Write down the doctor name and appointment time the assistant confirms.
- You will use that same appointment in Part 2.

## Part 2: Henry Long Cancels the Appointment He Just Booked

Goal: show cancellation on the same Henry Long account.

Suggested spoken script:

```text
Henry Long: I need to cancel my appointment.

If asked whether you're new or returning:
Henry Long: I've been here before.

Henry Long: My UIN is 246 813 579.
Henry Long: Yes.

If asked which appointment:
Henry Long: The appointment for my headache that I just booked.

--------- Alternative if you want a more natural prompt: -----------
Henry Mo: I don't remember which one. Can you tell me when my upcoming appointment is?


If the assistant reads back the doctor and time:
Henry Long: Yes, that's the one.

If asked to confirm cancellation:
Henry Long: Yes, please cancel it.
```

Operator note:

- This works best if you do it immediately after Part 1, while Henry Long has only one upcoming appointment.

## Part 3: Henry Mo Reschedules His Seeded Appointment

Goal: show the reschedule flow using the seeded appointment.

Suggested spoken script:

```text
Henry Mo: I need to reschedule my appointment.

If asked whether you're new or returning:
Henry Mo: I've been here before.

Henry Mo: My UIN is 135 792 468.
Henry Mo: Yes.

If asked which appointment:
Henry Mo: It's my appointment with Dr. James Wilson for shoulder pain.

--------- Alternative if you want a more natural prompt: -----------
Henry Mo: I don't remember which one. Can you tell me when my upcoming appointment is?



If the assistant reads back the appointment:
Henry Mo: Yes, that's the one.

If asked when you'd like to reschedule: (pick next week, so the appointment is stil exists on the demo day with the professor)

Henry Mo: next week.
 
If asked morning or afternoon:
Henry Mo: Afternoon.

When new slots are offered:
Henry Mo: I'll take the first one.
```

Operator note:

- If the assistant wants the exact seeded appointment date and you reran the seed on `April 14, 2026`, use `Wednesday, April 22, 2026 at 9:30 AM`.
- If you reseed on a different day, use the actual date from the SQL check above.

## Backup Lines

Use these only if the conversation branches.

- `Neurology sounds right.`
- `No, this is not a follow-up.`
- `The appointment with the doctor you just mentioned is the one I mean.`
- `Could you repeat the options?`
- `I'll take the earliest one you offered.`

## What Success Looks Like

- Henry Long books one confirmed appointment.
- Henry Long then cancels that same appointment.
- Henry Mo successfully moves his existing appointment to a new confirmed slot.
- The assistant sounds confident, asks one question at a time, and confirms the selected times clearly.
