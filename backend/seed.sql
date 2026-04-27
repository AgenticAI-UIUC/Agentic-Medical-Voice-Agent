-- ============================================================
-- Medical Voice Agent — Mock / Seed Data
--
-- Run this against your Supabase database after schema.sql.
-- Populates: specialties, symptom_specialty_map, doctors,
--            doctor_specialties, doctor_availability,
--            doctor_blocks, patients, and a few appointments.
--
-- All UUIDs are hardcoded so the script is idempotent
-- (safe to run multiple times with ON CONFLICT DO NOTHING).
-- Timestamps in this seed are intended to represent clinic-local times
-- in America/Chicago. Setting the session timezone here keeps demo slots
-- stable when they are later read back to callers in clinic time.
-- ============================================================

SET TIME ZONE 'America/Chicago';

-- ============================================================
-- 1. Specialties
-- ============================================================
INSERT INTO public.specialties (id, name, description) VALUES
  ('a0000000-0000-0000-0000-000000000001', 'General Practice',      'Primary care and general health concerns'),
  ('a0000000-0000-0000-0000-000000000002', 'Cardiology',            'Heart and cardiovascular system'),
  ('a0000000-0000-0000-0000-000000000003', 'Dermatology',           'Skin, hair, and nail conditions'),
  ('a0000000-0000-0000-0000-000000000004', 'Orthopedics',           'Bones, joints, muscles, and ligaments'),
  ('a0000000-0000-0000-0000-000000000005', 'Neurology',             'Brain, spinal cord, and nervous system'),
  ('a0000000-0000-0000-0000-000000000006', 'Gastroenterology',      'Digestive system and gastrointestinal tract'),
  ('a0000000-0000-0000-0000-000000000007', 'Psychiatry',            'Mental health and behavioral disorders'),
  ('a0000000-0000-0000-0000-000000000008', 'Ophthalmology',         'Eyes and vision'),
  ('a0000000-0000-0000-0000-000000000009', 'ENT',                   'Ear, nose, and throat'),
  ('a0000000-0000-0000-0000-000000000010', 'Pulmonology',           'Lungs and respiratory system')
ON CONFLICT (id) DO NOTHING;


-- ============================================================
-- 2. Symptom → Specialty Mapping (for triage engine)
-- ============================================================

-- General Practice (catch-all, lower weights)
INSERT INTO public.symptom_specialty_map (symptom, specialty_id, weight, follow_up_questions) VALUES
  ('fever',           'a0000000-0000-0000-0000-000000000001', 0.8, '["How long have you had the fever?", "What is your temperature?"]'),
  ('fatigue',         'a0000000-0000-0000-0000-000000000001', 0.7, '["How long have you been feeling fatigued?", "Does rest help?"]'),
  ('cold',            'a0000000-0000-0000-0000-000000000001', 1.0, '["Do you have a runny nose or sore throat?"]'),
  ('flu',             'a0000000-0000-0000-0000-000000000001', 1.0, '["Do you have body aches and chills?"]'),
  ('general checkup', 'a0000000-0000-0000-0000-000000000001', 2.0, null)
ON CONFLICT ON CONSTRAINT unique_symptom_specialty DO NOTHING;

-- Cardiology
INSERT INTO public.symptom_specialty_map (symptom, specialty_id, weight, follow_up_questions) VALUES
  ('chest pain',          'a0000000-0000-0000-0000-000000000002', 2.0, '["Does the pain radiate to your arm or jaw?", "Does it get worse with physical activity?"]'),
  ('heart palpitations',  'a0000000-0000-0000-0000-000000000002', 2.0, '["How often do you experience palpitations?", "Do you feel dizzy when they happen?"]'),
  ('shortness of breath', 'a0000000-0000-0000-0000-000000000002', 1.5, '["Does it happen at rest or only during activity?", "Do you have any swelling in your legs?"]'),
  ('high blood pressure', 'a0000000-0000-0000-0000-000000000002', 1.8, '["Are you currently on any blood pressure medication?"]'),
  ('dizziness',           'a0000000-0000-0000-0000-000000000002', 1.0, '["Do you feel lightheaded or like the room is spinning?"]')
ON CONFLICT ON CONSTRAINT unique_symptom_specialty DO NOTHING;

-- Dermatology
INSERT INTO public.symptom_specialty_map (symptom, specialty_id, weight, follow_up_questions) VALUES
  ('rash',         'a0000000-0000-0000-0000-000000000003', 2.0, '["Where on your body is the rash?", "Is it itchy or painful?"]'),
  ('acne',         'a0000000-0000-0000-0000-000000000003', 2.0, '["How long have you had acne?"]'),
  ('skin irritation', 'a0000000-0000-0000-0000-000000000003', 1.8, '["Is the affected area red, swollen, or flaky?"]'),
  ('mole changes', 'a0000000-0000-0000-0000-000000000003', 2.0, '["Has the mole changed in size, shape, or color?", "Is it bleeding or itching?"]'),
  ('hair loss',    'a0000000-0000-0000-0000-000000000003', 1.5, '["Is the hair loss in patches or all over?"]'),
  ('itching',      'a0000000-0000-0000-0000-000000000003', 1.2, '["Where is the itching?", "Have you started any new products recently?"]')
ON CONFLICT ON CONSTRAINT unique_symptom_specialty DO NOTHING;

-- Orthopedics
INSERT INTO public.symptom_specialty_map (symptom, specialty_id, weight, follow_up_questions) VALUES
  ('joint pain',   'a0000000-0000-0000-0000-000000000004', 2.0, '["Which joint is affected?", "Did this start after an injury?"]'),
  ('back pain',    'a0000000-0000-0000-0000-000000000004', 1.8, '["Is the pain in your upper or lower back?", "Does it radiate down your legs?"]'),
  ('knee pain',    'a0000000-0000-0000-0000-000000000004', 2.0, '["Did the knee pain start suddenly or gradually?", "Does it swell?"]'),
  ('fracture',     'a0000000-0000-0000-0000-000000000004', 2.5, '["Can you move the affected area?", "Is there visible swelling or deformity?"]'),
  ('sprain',       'a0000000-0000-0000-0000-000000000004', 2.0, '["When did the injury occur?"]'),
  ('shoulder pain', 'a0000000-0000-0000-0000-000000000004', 1.8, '["Can you raise your arm above your head?"]')
ON CONFLICT ON CONSTRAINT unique_symptom_specialty DO NOTHING;

-- Neurology
INSERT INTO public.symptom_specialty_map (symptom, specialty_id, weight, follow_up_questions) VALUES
  ('headache',     'a0000000-0000-0000-0000-000000000005', 1.5, '["How often do you get headaches?", "Where is the pain located?", "Do you experience sensitivity to light?"]'),
  ('migraine',     'a0000000-0000-0000-0000-000000000005', 2.0, '["Do you see visual disturbances before the migraine?"]'),
  ('numbness',     'a0000000-0000-0000-0000-000000000005', 1.8, '["Where do you feel the numbness?", "Is it constant or does it come and go?"]'),
  ('tingling',     'a0000000-0000-0000-0000-000000000005', 1.5, '["Where do you feel the tingling?"]'),
  ('seizure',      'a0000000-0000-0000-0000-000000000005', 2.5, '["Have you had seizures before?", "Are you currently on any medication?"]'),
  ('memory problems', 'a0000000-0000-0000-0000-000000000005', 1.5, '["How long have you noticed memory issues?"]')
ON CONFLICT ON CONSTRAINT unique_symptom_specialty DO NOTHING;

-- Gastroenterology
INSERT INTO public.symptom_specialty_map (symptom, specialty_id, weight, follow_up_questions) VALUES
  ('stomach pain',  'a0000000-0000-0000-0000-000000000006', 2.0, '["Where exactly is the pain?", "Does eating make it better or worse?"]'),
  ('nausea',        'a0000000-0000-0000-0000-000000000006', 1.5, '["How long have you been feeling nauseous?", "Have you been vomiting?"]'),
  ('heartburn',     'a0000000-0000-0000-0000-000000000006', 1.8, '["How often do you experience heartburn?"]'),
  ('bloating',      'a0000000-0000-0000-0000-000000000006', 1.2, '["Does the bloating happen after eating?"]'),
  ('diarrhea',      'a0000000-0000-0000-0000-000000000006', 1.5, '["How long has this been going on?"]'),
  ('constipation',  'a0000000-0000-0000-0000-000000000006', 1.2, '["How long have you been constipated?"]')
ON CONFLICT ON CONSTRAINT unique_symptom_specialty DO NOTHING;

-- Psychiatry
INSERT INTO public.symptom_specialty_map (symptom, specialty_id, weight, follow_up_questions) VALUES
  ('anxiety',    'a0000000-0000-0000-0000-000000000007', 2.0, '["How long have you been experiencing anxiety?", "Does it interfere with daily activities?"]'),
  ('depression', 'a0000000-0000-0000-0000-000000000007', 2.0, '["How long have you been feeling this way?", "Have you had any changes in sleep or appetite?"]'),
  ('insomnia',   'a0000000-0000-0000-0000-000000000007', 1.5, '["How many hours of sleep do you get per night?", "Do you have trouble falling asleep or staying asleep?"]'),
  ('panic attacks', 'a0000000-0000-0000-0000-000000000007', 2.0, '["How frequently do they occur?"]'),
  ('stress',     'a0000000-0000-0000-0000-000000000007', 1.0, '["What is the main source of your stress?"]')
ON CONFLICT ON CONSTRAINT unique_symptom_specialty DO NOTHING;

-- Ophthalmology
INSERT INTO public.symptom_specialty_map (symptom, specialty_id, weight, follow_up_questions) VALUES
  ('blurry vision',  'a0000000-0000-0000-0000-000000000008', 2.0, '["Is the blurriness in one eye or both?", "Did it start suddenly?"]'),
  ('eye pain',       'a0000000-0000-0000-0000-000000000008', 2.0, '["Is the pain sharp or dull?", "Is there any redness?"]'),
  ('vision loss',    'a0000000-0000-0000-0000-000000000008', 2.5, '["Is it partial or complete?", "Did it happen suddenly?"]'),
  ('red eye',        'a0000000-0000-0000-0000-000000000008', 1.5, '["Is there any discharge?"]')
ON CONFLICT ON CONSTRAINT unique_symptom_specialty DO NOTHING;

-- ENT
INSERT INTO public.symptom_specialty_map (symptom, specialty_id, weight, follow_up_questions) VALUES
  ('sore throat',  'a0000000-0000-0000-0000-000000000009', 1.8, '["How long have you had the sore throat?", "Do you have difficulty swallowing?"]'),
  ('ear pain',     'a0000000-0000-0000-0000-000000000009', 2.0, '["Is the pain in one ear or both?", "Do you have any hearing changes?"]'),
  ('hearing loss', 'a0000000-0000-0000-0000-000000000009', 2.0, '["Was the hearing loss sudden or gradual?"]'),
  ('sinus pain',   'a0000000-0000-0000-0000-000000000009', 1.8, '["Do you have nasal congestion?", "Is there any facial pressure?"]'),
  ('nosebleed',    'a0000000-0000-0000-0000-000000000009', 1.5, '["How often do you get nosebleeds?"]'),
  ('runny nose',   'a0000000-0000-0000-0000-000000000009', 1.0, '["How long has it been going on?"]')
ON CONFLICT ON CONSTRAINT unique_symptom_specialty DO NOTHING;

-- Pulmonology
INSERT INTO public.symptom_specialty_map (symptom, specialty_id, weight, follow_up_questions) VALUES
  ('cough',              'a0000000-0000-0000-0000-000000000010', 1.5, '["How long have you had the cough?", "Is it dry or producing mucus?"]'),
  ('wheezing',           'a0000000-0000-0000-0000-000000000010', 2.0, '["When does the wheezing occur?", "Do you have a history of asthma?"]'),
  ('shortness of breath','a0000000-0000-0000-0000-000000000010', 1.5, '["Do you smoke or have you smoked in the past?"]'),
  ('chest tightness',    'a0000000-0000-0000-0000-000000000010', 1.5, '["Does the tightness get worse with activity?"]'),
  ('difficulty breathing','a0000000-0000-0000-0000-000000000010', 2.0, '["Is it worse when lying down?"]')
ON CONFLICT ON CONSTRAINT unique_symptom_specialty DO NOTHING;


-- ============================================================
-- 3. Doctors
-- ============================================================
INSERT INTO public.doctors (id, full_name, is_active) VALUES
  ('b0000000-0000-0000-0000-000000000001', 'Dr. Sarah Chen',       true),
  ('b0000000-0000-0000-0000-000000000002', 'Dr. Michael Torres',   true),
  ('b0000000-0000-0000-0000-000000000003', 'Dr. Emily Johnson',    true),
  ('b0000000-0000-0000-0000-000000000004', 'Dr. James Wilson',     true),
  ('b0000000-0000-0000-0000-000000000005', 'Dr. Priya Patel',      true),
  ('b0000000-0000-0000-0000-000000000006', 'Dr. Robert Kim',       true),
  ('b0000000-0000-0000-0000-000000000007', 'Dr. Lisa Martinez',    true),
  ('b0000000-0000-0000-0000-000000000008', 'Dr. David Okafor',     true)
ON CONFLICT (id) DO NOTHING;


-- ============================================================
-- 4. Doctor ↔ Specialty Links
-- ============================================================
INSERT INTO public.doctor_specialties (doctor_id, specialty_id) VALUES
  -- Dr. Chen: General Practice + Pulmonology
  ('b0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000001'),
  ('b0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000010'),
  -- Dr. Torres: Cardiology
  ('b0000000-0000-0000-0000-000000000002', 'a0000000-0000-0000-0000-000000000002'),
  -- Dr. Johnson: Dermatology
  ('b0000000-0000-0000-0000-000000000003', 'a0000000-0000-0000-0000-000000000003'),
  -- Dr. Wilson: Orthopedics
  ('b0000000-0000-0000-0000-000000000004', 'a0000000-0000-0000-0000-000000000004'),
  -- Dr. Patel: Neurology + Psychiatry
  ('b0000000-0000-0000-0000-000000000005', 'a0000000-0000-0000-0000-000000000005'),
  ('b0000000-0000-0000-0000-000000000005', 'a0000000-0000-0000-0000-000000000007'),
  -- Dr. Kim: Gastroenterology
  ('b0000000-0000-0000-0000-000000000006', 'a0000000-0000-0000-0000-000000000006'),
  -- Dr. Martinez: Ophthalmology + ENT
  ('b0000000-0000-0000-0000-000000000007', 'a0000000-0000-0000-0000-000000000008'),
  ('b0000000-0000-0000-0000-000000000007', 'a0000000-0000-0000-0000-000000000009'),
  -- Dr. Okafor: General Practice
  ('b0000000-0000-0000-0000-000000000008', 'a0000000-0000-0000-0000-000000000001')
ON CONFLICT (doctor_id, specialty_id) DO NOTHING;


-- ============================================================
-- 5. Doctor Availability (weekly templates)
--    day_of_week: 0=Sun, 1=Mon, 2=Tue, 3=Wed, 4=Thu, 5=Fri, 6=Sat
-- ============================================================

-- Dr. Chen — Mon/Wed/Fri, morning + afternoon with lunch break
INSERT INTO public.doctor_availability (doctor_id, day_of_week, start_time, end_time, slot_minutes) VALUES
  ('b0000000-0000-0000-0000-000000000001', 1, '09:00', '12:00', 60),
  ('b0000000-0000-0000-0000-000000000001', 1, '13:00', '17:00', 60),
  ('b0000000-0000-0000-0000-000000000001', 3, '09:00', '12:00', 60),
  ('b0000000-0000-0000-0000-000000000001', 3, '13:00', '17:00', 60),
  ('b0000000-0000-0000-0000-000000000001', 5, '09:00', '12:00', 60),
  ('b0000000-0000-0000-0000-000000000001', 5, '13:00', '17:00', 60);

-- Dr. Torres — Tue/Thu, morning + afternoon
INSERT INTO public.doctor_availability (doctor_id, day_of_week, start_time, end_time, slot_minutes) VALUES
  ('b0000000-0000-0000-0000-000000000002', 2, '08:00', '12:00', 60),
  ('b0000000-0000-0000-0000-000000000002', 2, '13:00', '16:00', 60),
  ('b0000000-0000-0000-0000-000000000002', 4, '08:00', '12:00', 60),
  ('b0000000-0000-0000-0000-000000000002', 4, '13:00', '16:00', 60);

-- Dr. Johnson — Mon/Tue/Wed, mornings only
INSERT INTO public.doctor_availability (doctor_id, day_of_week, start_time, end_time, slot_minutes) VALUES
  ('b0000000-0000-0000-0000-000000000003', 1, '09:00', '13:00', 60),
  ('b0000000-0000-0000-0000-000000000003', 2, '09:00', '13:00', 60),
  ('b0000000-0000-0000-0000-000000000003', 3, '09:00', '13:00', 60);

-- Dr. Wilson — Mon through Fri, full day
INSERT INTO public.doctor_availability (doctor_id, day_of_week, start_time, end_time, slot_minutes) VALUES
  ('b0000000-0000-0000-0000-000000000004', 1, '08:00', '12:00', 60),
  ('b0000000-0000-0000-0000-000000000004', 1, '13:00', '17:00', 60),
  ('b0000000-0000-0000-0000-000000000004', 2, '08:00', '12:00', 60),
  ('b0000000-0000-0000-0000-000000000004', 2, '13:00', '17:00', 60),
  ('b0000000-0000-0000-0000-000000000004', 3, '08:00', '12:00', 60),
  ('b0000000-0000-0000-0000-000000000004', 3, '13:00', '17:00', 60),
  ('b0000000-0000-0000-0000-000000000004', 4, '08:00', '12:00', 60),
  ('b0000000-0000-0000-0000-000000000004', 4, '13:00', '17:00', 60),
  ('b0000000-0000-0000-0000-000000000004', 5, '08:00', '12:00', 60),
  ('b0000000-0000-0000-0000-000000000004', 5, '13:00', '17:00', 60);

-- Dr. Patel — Wed/Thu afternoons, Friday extended afternoon block
INSERT INTO public.doctor_availability (doctor_id, day_of_week, start_time, end_time, slot_minutes) VALUES
  ('b0000000-0000-0000-0000-000000000005', 3, '13:00', '18:00', 60),
  ('b0000000-0000-0000-0000-000000000005', 4, '13:00', '18:00', 60),
  ('b0000000-0000-0000-0000-000000000005', 5, '12:00', '18:00', 60);

-- Dr. Kim — Mon/Wed, morning + afternoon
INSERT INTO public.doctor_availability (doctor_id, day_of_week, start_time, end_time, slot_minutes) VALUES
  ('b0000000-0000-0000-0000-000000000006', 1, '10:00', '13:00', 60),
  ('b0000000-0000-0000-0000-000000000006', 1, '14:00', '17:00', 60),
  ('b0000000-0000-0000-0000-000000000006', 3, '10:00', '13:00', 60),
  ('b0000000-0000-0000-0000-000000000006', 3, '14:00', '17:00', 60);

-- Dr. Martinez — Tue/Thu, full day
INSERT INTO public.doctor_availability (doctor_id, day_of_week, start_time, end_time, slot_minutes) VALUES
  ('b0000000-0000-0000-0000-000000000007', 2, '09:00', '12:00', 60),
  ('b0000000-0000-0000-0000-000000000007', 2, '13:00', '17:00', 60),
  ('b0000000-0000-0000-0000-000000000007', 4, '09:00', '12:00', 60),
  ('b0000000-0000-0000-0000-000000000007', 4, '13:00', '17:00', 60);

-- Dr. Okafor — Mon/Tue/Thu/Fri, mornings
INSERT INTO public.doctor_availability (doctor_id, day_of_week, start_time, end_time, slot_minutes) VALUES
  ('b0000000-0000-0000-0000-000000000008', 1, '08:00', '12:00', 60),
  ('b0000000-0000-0000-0000-000000000008', 2, '08:00', '12:00', 60),
  ('b0000000-0000-0000-0000-000000000008', 4, '08:00', '12:00', 60),
  ('b0000000-0000-0000-0000-000000000008', 5, '08:00', '12:00', 60);


-- ============================================================
-- 6. Doctor Blocks (a few example time-offs)
-- ============================================================
INSERT INTO public.doctor_blocks (doctor_id, start_at, end_at, reason) VALUES
  -- Dr. Chen out for a conference next Wednesday
  ('b0000000-0000-0000-0000-000000000001',
   (date_trunc('week', now()) + interval '9 days' + interval '9 hours')::timestamptz,
   (date_trunc('week', now()) + interval '9 days' + interval '17 hours')::timestamptz,
   'Medical conference'),
  -- Dr. Wilson out Friday afternoon
  ('b0000000-0000-0000-0000-000000000004',
   (date_trunc('week', now()) + interval '11 days' + interval '13 hours')::timestamptz,
   (date_trunc('week', now()) + interval '11 days' + interval '17 hours')::timestamptz,
   'Personal appointment');


-- ============================================================
-- 7. Test Patients
-- ============================================================
INSERT INTO public.patients (id, uin, full_name, phone, email, allergies) VALUES
  ('c0000000-0000-0000-0000-000000000001', '123456789', 'Alice Wang',     '2175551001', 'alice.wang@university.edu',    'Penicillin'),
  ('c0000000-0000-0000-0000-000000000002', '234567890', 'Bob Martinez',   '2175551002', 'bob.martinez@university.edu',  null),
  ('c0000000-0000-0000-0000-000000000003', '345678901', 'Carol Johnson',  '2175551003', 'carol.j@university.edu',       'Shellfish'),
  ('c0000000-0000-0000-0000-000000000004', '456789012', 'David Lee',      '2175551004', 'david.lee@university.edu',     null),
  ('c0000000-0000-0000-0000-000000000005', '567890123', 'Emma Thompson',  '2175551005', 'emma.t@university.edu',        'Latex, Sulfa'),
  ('c0000000-0000-0000-0000-000000000006', '678901235', 'Nina Carter',    '2175551006', 'nina.carter@university.edu',  null),
  ('c0000000-0000-0000-0000-000000000007', '246813579', 'Henry Long',     '2175551010', 'henry.long@demo.example.com', null),
  ('c0000000-0000-0000-0000-000000000008', '135792468', 'Henry Mo',       '2175551011', 'henry.mo@demo.example.com',   null)
ON CONFLICT (id) DO NOTHING;


-- ============================================================
-- 8. Sample Appointments (a few existing bookings to test
--    rescheduling/cancellation and to pre-fill some slots)
-- ============================================================

-- Alice has an upcoming cardiology appointment with Dr. Torres (next Tuesday 9 AM)
INSERT INTO public.appointments (id, patient_id, doctor_id, specialty_id, start_at, end_at, reason, symptoms, severity_rating, urgency, status) VALUES
  ('d0000000-0000-0000-0000-000000000001',
   'c0000000-0000-0000-0000-000000000001',
   'b0000000-0000-0000-0000-000000000002',
   'a0000000-0000-0000-0000-000000000002',
   (date_trunc('week', now()) + interval '8 days' + interval '9 hours')::timestamptz,
   (date_trunc('week', now()) + interval '8 days' + interval '10 hours')::timestamptz,
   'Recurring chest tightness', 'chest pain, shortness of breath', 6, 'ROUTINE', 'CONFIRMED')
ON CONFLICT (id) DO NOTHING;

-- Bob has a dermatology appointment with Dr. Johnson (next Monday 10 AM)
INSERT INTO public.appointments (id, patient_id, doctor_id, specialty_id, start_at, end_at, reason, symptoms, severity_rating, urgency, status) VALUES
  ('d0000000-0000-0000-0000-000000000002',
   'c0000000-0000-0000-0000-000000000002',
   'b0000000-0000-0000-0000-000000000003',
   'a0000000-0000-0000-0000-000000000003',
   (date_trunc('week', now()) + interval '7 days' + interval '10 hours')::timestamptz,
   (date_trunc('week', now()) + interval '7 days' + interval '11 hours')::timestamptz,
   'Persistent rash on arm', 'rash, itching', 4, 'ROUTINE', 'CONFIRMED')
ON CONFLICT (id) DO NOTHING;

-- Carol has a neurology appointment with Dr. Patel (next Thursday 2 PM)
INSERT INTO public.appointments (id, patient_id, doctor_id, specialty_id, start_at, end_at, reason, symptoms, severity_rating, urgency, status) VALUES
  ('d0000000-0000-0000-0000-000000000003',
   'c0000000-0000-0000-0000-000000000003',
   'b0000000-0000-0000-0000-000000000005',
   'a0000000-0000-0000-0000-000000000005',
   (date_trunc('week', now()) + interval '10 days' + interval '14 hours')::timestamptz,
   (date_trunc('week', now()) + interval '10 days' + interval '15 hours')::timestamptz,
   'Frequent migraines', 'migraine, headache, nausea', 7, 'ROUTINE', 'CONFIRMED')
ON CONFLICT (id) DO NOTHING;

-- David has a past completed general practice visit (last week)
INSERT INTO public.appointments (id, patient_id, doctor_id, specialty_id, start_at, end_at, reason, symptoms, severity_rating, urgency, status) VALUES
  ('d0000000-0000-0000-0000-000000000004',
   'c0000000-0000-0000-0000-000000000004',
   'b0000000-0000-0000-0000-000000000001',
   'a0000000-0000-0000-0000-000000000001',
   (date_trunc('day', now() - interval '5 days') + interval '9 hours')::timestamptz,
   (date_trunc('day', now() - interval '5 days') + interval '10 hours')::timestamptz,
   'Annual checkup', 'general checkup', 1, 'ROUTINE', 'COMPLETED')
ON CONFLICT (id) DO NOTHING;

-- Nina has two future appointments to test multi-appointment disambiguation
INSERT INTO public.appointments (id, patient_id, doctor_id, specialty_id, start_at, end_at, reason, symptoms, severity_rating, urgency, status) VALUES
  ('d0000000-0000-0000-0000-000000000005',
   'c0000000-0000-0000-0000-000000000006',
   'b0000000-0000-0000-0000-000000000007',
   'a0000000-0000-0000-0000-000000000009',
   (date_trunc('week', now()) + interval '8 days' + interval '9 hours')::timestamptz,
   (date_trunc('week', now()) + interval '8 days' + interval '10 hours')::timestamptz,
   'Ear pain follow-up', 'ear pain', 4, 'ROUTINE', 'CONFIRMED')
ON CONFLICT (id) DO NOTHING;

INSERT INTO public.appointments (id, patient_id, doctor_id, specialty_id, start_at, end_at, reason, symptoms, severity_rating, urgency, status) VALUES
  ('d0000000-0000-0000-0000-000000000006',
   'c0000000-0000-0000-0000-000000000006',
   'b0000000-0000-0000-0000-000000000007',
   'a0000000-0000-0000-0000-000000000008',
   (date_trunc('week', now()) + interval '10 days' + interval '14 hours')::timestamptz,
   (date_trunc('week', now()) + interval '10 days' + interval '15 hours')::timestamptz,
   'Blurry vision follow-up', 'blurry vision', 3, 'ROUTINE', 'CONFIRMED')
ON CONFLICT (id) DO NOTHING;

-- Henry Mo has one upcoming appointment for the reschedule demo.
-- Henry Long is seeded only as a patient so he can demo booking as an
-- existing patient, then cancel the appointment he creates during the call.
INSERT INTO public.appointments (id, patient_id, doctor_id, specialty_id, start_at, end_at, reason, symptoms, severity_rating, urgency, status) VALUES
  ('d0000000-0000-0000-0000-000000000007',
   'c0000000-0000-0000-0000-000000000008',
   'b0000000-0000-0000-0000-000000000004',
   'a0000000-0000-0000-0000-000000000004',
   (date_trunc('week', now()) + interval '9 days' + interval '14 hours')::timestamptz,
   (date_trunc('week', now()) + interval '9 days' + interval '15 hours')::timestamptz,
   'Ongoing shoulder pain', 'shoulder pain, joint pain', 5, 'ROUTINE', 'CONFIRMED')
ON CONFLICT (id) DO NOTHING;


-- ============================================================
-- Done! Summary of test data:
--
-- Specialties:  10 (General Practice through Pulmonology)
-- Symptoms:     ~50 mapped to specialties with weights and follow-up questions
-- Doctors:       8 with varied availability schedules
-- Patients:      8 test/demo patients
-- Appointments:  6 upcoming CONFIRMED and 1 past COMPLETED
-- Blocks:        2 (Dr. Chen conference, Dr. Wilson personal)
--
-- Test UINs for voice testing:
--   Alice Wang:      123456789
--   Bob Martinez:   234567890
--   Carol Johnson:  345678901
--   David Lee:      456789012
--   Emma Thompson:  567890123
--   Nina Carter:    678901235
--   Henry Long:      246813579
--   Henry Mo:        135792468
-- ============================================================
