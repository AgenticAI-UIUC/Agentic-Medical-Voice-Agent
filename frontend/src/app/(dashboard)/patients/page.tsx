'use client';

import {
  CalendarCheck2,
  CalendarClock,
  Clock3,
  FileText,
  Link2,
  Mail,
  Phone,
  RefreshCw,
  Search,
  Stethoscope,
  UserRound,
  Users,
} from 'lucide-react';
import { useSearchParams } from 'next/navigation';
import { useEffect, useMemo, useState } from 'react';

import { EmptyState } from '@/components/common/empty-state';
import { PageHeader } from '@/components/common/page-header';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  useAppointmentsQuery,
  usePatientsQuery,
} from '@/hooks/use-patients';
import { getApiErrorMessage } from '@/lib/api/get-api-error-message';
import type {
  Patient,
  PatientAppointment,
} from '@/lib/api/patients';
import { cn } from '@/lib/utils';

const ACTIVE_STATUSES = new Set(['CONFIRMED']);
const VISIT_STATUSES = new Set(['CONFIRMED', 'COMPLETED']);
const EMPTY_PATIENTS: Patient[] = [];
const EMPTY_APPOINTMENTS: PatientAppointment[] = [];

function formatDateTime(value?: string | null) {
  if (!value) return '-';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString([], {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  });
}

function formatTime(value?: string | null) {
  if (!value) return '-';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleTimeString([], {
    hour: 'numeric',
    minute: '2-digit',
  });
}

function formatTimeRange(start?: string | null, end?: string | null) {
  if (!start && !end) return '-';
  return `${formatTime(start)} - ${formatTime(end)}`;
}

function formatDate(value?: string | null) {
  if (!value) return '-';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString([], {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  });
}

function normalizeStatus(status?: string | null) {
  return (status || 'UNKNOWN').replaceAll('_', ' ');
}

function StatusPill({ status }: { status?: string | null }) {
  const normalized = status || 'UNKNOWN';
  const tone =
    normalized === 'CONFIRMED'
      ? 'border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-900 dark:bg-emerald-950 dark:text-emerald-300'
      : normalized === 'CANCELLED'
        ? 'border-slate-200 bg-slate-50 text-slate-700 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300'
        : normalized === 'COMPLETED'
          ? 'border-blue-200 bg-blue-50 text-blue-700 dark:border-blue-900 dark:bg-blue-950 dark:text-blue-300'
          : 'border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-300';

  return (
    <span
      className={cn(
        'inline-flex rounded-full border px-2 py-0.5 text-xs font-medium',
        tone,
      )}
    >
      {normalizeStatus(normalized)}
    </span>
  );
}

function appointmentPatientKey(appointment: PatientAppointment) {
  return appointment.patient_id || appointment.patients?.uin || '';
}

function appointmentTimeSortValue(appointment: PatientAppointment) {
  const value = new Date(appointment.start_at).getTime();
  return Number.isNaN(value) ? 0 : value;
}

function appointmentCreatedSortValue(appointment: PatientAppointment) {
  const value = new Date(appointment.created_at ?? '').getTime();
  return Number.isNaN(value) ? appointmentTimeSortValue(appointment) : value;
}

function upcomingAppointment(appointments: PatientAppointment[]) {
  const now = Date.now();
  return appointments
    .filter(
      (appointment) =>
        ACTIVE_STATUSES.has(appointment.status) &&
        appointmentTimeSortValue(appointment) >= now,
    )
    .sort((a, b) => appointmentTimeSortValue(a) - appointmentTimeSortValue(b))[0];
}

function lastVisitAppointment(appointments: PatientAppointment[]) {
  const now = Date.now();
  return appointments
    .filter((appointment) => {
      const startAt = appointmentTimeSortValue(appointment);
      return (
        VISIT_STATUSES.has(appointment.status) &&
        startAt > 0 &&
        startAt < now
      );
    })
    .sort((a, b) => appointmentTimeSortValue(b) - appointmentTimeSortValue(a))[0];
}

function matchesPatient(patient: Patient, search: string) {
  if (!search.trim()) return true;
  const query = search.trim().toLowerCase();
  return [
    patient.full_name,
    patient.uin,
    patient.phone,
    patient.email ?? '',
  ].some((value) => value.toLowerCase().includes(query));
}

function DetailBlock({
  label,
  value,
  mono = false,
}: {
  label: string;
  value?: string | number | null;
  mono?: boolean;
}) {
  const displayValue =
    value === undefined || value === null || value === '' ? '-' : value;

  return (
    <div>
      <p className="text-xs font-medium uppercase text-muted-foreground">
        {label}
      </p>
      <p
        className={cn(
          'mt-1 break-words',
          mono && 'font-mono text-xs',
        )}
      >
        {displayValue}
      </p>
    </div>
  );
}

function NarrativeRow({
  icon: Icon,
  label,
  value,
}: {
  icon: typeof FileText;
  label: string;
  value?: string | null;
}) {
  if (!value?.trim()) return null;

  return (
    <div className="rounded-md border bg-muted/20 p-3">
      <p className="flex items-center gap-2 text-xs font-medium uppercase text-muted-foreground">
        <Icon className="h-4 w-4" />
        {label}
      </p>
      <p className="mt-2 whitespace-pre-wrap break-words text-sm">{value}</p>
    </div>
  );
}

export default function PatientsPage() {
  const searchParams = useSearchParams();
  const requestedPatientId = searchParams.get('patientId');
  const requestedUin = searchParams.get('uin');
  const [search, setSearch] = useState('');
  const [selectedPatientId, setSelectedPatientId] = useState<string | null>(
    null,
  );

  const patientsQuery = usePatientsQuery({ limit: 200 });
  const appointmentsQuery = useAppointmentsQuery({ limit: 200 });

  const patients = patientsQuery.data ?? EMPTY_PATIENTS;
  const appointments = appointmentsQuery.data ?? EMPTY_APPOINTMENTS;

  useEffect(() => {
    if (!requestedPatientId && !requestedUin) return;

    const matchedPatient = patients.find(
      (patient) =>
        (requestedPatientId && patient.id === requestedPatientId) ||
        (requestedUin && patient.uin === requestedUin),
    );

    if (!matchedPatient) return;

    setSearch('');
    setSelectedPatientId(matchedPatient.id);
  }, [patients, requestedPatientId, requestedUin]);

  const appointmentsByPatient = useMemo(() => {
    return appointments.reduce<Record<string, PatientAppointment[]>>(
      (groups, appointment) => {
        const keys = [
          appointmentPatientKey(appointment),
          appointment.patients?.uin ?? '',
        ].filter(Boolean);

        for (const key of keys) {
          groups[key] ??= [];
          groups[key].push(appointment);
        }

        return groups;
      },
      {},
    );
  }, [appointments]);

  const filteredPatients = patients.filter((patient) =>
    matchesPatient(patient, search),
  );

  const selectedPatient =
    filteredPatients.find((patient) => patient.id === selectedPatientId) ??
    filteredPatients[0] ??
    null;

  const selectedAppointments = selectedPatient
    ? [
        ...(appointmentsByPatient[selectedPatient.id] ?? []),
        ...(appointmentsByPatient[selectedPatient.uin] ?? []),
      ].filter(
        (appointment, index, list) =>
          list.findIndex((item) => item.id === appointment.id) === index,
      )
    : [];

  const sortedSelectedAppointments = [...selectedAppointments].sort(
    (a, b) => appointmentCreatedSortValue(b) - appointmentCreatedSortValue(a),
  );

  const stats = {
    patients: patients.length,
    appointments: appointments.length,
    active: appointments.filter((appointment) =>
      ACTIVE_STATUSES.has(appointment.status),
    ).length,
    linkedPatients: patients.filter(
      (patient) =>
        (appointmentsByPatient[patient.id]?.length ?? 0) +
          (appointmentsByPatient[patient.uin]?.length ?? 0) >
        0,
    ).length,
  };

  const isLoading = patientsQuery.isPending || appointmentsQuery.isPending;
  const isError = patientsQuery.isError || appointmentsQuery.isError;
  const errorMessage = patientsQuery.isError
    ? getApiErrorMessage(
        patientsQuery.error,
        'Failed to load patient records.',
      )
    : appointmentsQuery.isError
      ? getApiErrorMessage(
          appointmentsQuery.error,
          'Failed to load appointments.',
        )
      : null;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Patients"
        description="Review patient records and every appointment currently linked to them."
        action={
          <Button
            variant="outline"
            onClick={() => {
              void patientsQuery.refetch();
              void appointmentsQuery.refetch();
            }}
            disabled={patientsQuery.isFetching || appointmentsQuery.isFetching}
          >
            <RefreshCw
              className={cn(
                'h-4 w-4',
                (patientsQuery.isFetching || appointmentsQuery.isFetching) &&
                  'animate-spin',
              )}
            />
            Refresh
          </Button>
        }
      />

      <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Card className="rounded-lg py-4">
          <CardContent className="flex items-center gap-3 px-4">
            <Users className="h-5 w-5 text-muted-foreground" />
            <div>
              <p className="text-2xl font-semibold">{stats.patients}</p>
              <p className="text-xs text-muted-foreground">Patients</p>
            </div>
          </CardContent>
        </Card>
        <Card className="rounded-lg py-4">
          <CardContent className="flex items-center gap-3 px-4">
            <CalendarCheck2 className="h-5 w-5 text-muted-foreground" />
            <div>
              <p className="text-2xl font-semibold">{stats.appointments}</p>
              <p className="text-xs text-muted-foreground">Appointments</p>
            </div>
          </CardContent>
        </Card>
        <Card className="rounded-lg py-4">
          <CardContent className="flex items-center gap-3 px-4">
            <CalendarClock className="h-5 w-5 text-emerald-600" />
            <div>
              <p className="text-2xl font-semibold">{stats.active}</p>
              <p className="text-xs text-muted-foreground">Confirmed</p>
            </div>
          </CardContent>
        </Card>
        <Card className="rounded-lg py-4">
          <CardContent className="flex items-center gap-3 px-4">
            <UserRound className="h-5 w-5 text-blue-600" />
            <div>
              <p className="text-2xl font-semibold">{stats.linkedPatients}</p>
              <p className="text-xs text-muted-foreground">With visits</p>
            </div>
          </CardContent>
        </Card>
      </section>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1.05fr)_minmax(360px,0.95fr)]">
        <Card className="rounded-lg">
          <CardHeader className="gap-4">
            <div>
              <CardTitle>Patient List</CardTitle>
              <CardDescription>
                {isLoading
                  ? 'Loading records...'
                  : `${filteredPatients.length} of ${patients.length} patients`}
              </CardDescription>
            </div>
            <div className="relative">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="Search name, UIN, phone, or email"
                className="pl-9"
              />
            </div>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <p className="text-sm text-muted-foreground">
                Loading patients...
              </p>
            ) : isError ? (
              <p className="text-sm text-red-600">
                {errorMessage ?? 'Failed to load patient records.'}
              </p>
            ) : filteredPatients.length === 0 ? (
              <EmptyState
                title="No patients found"
                description="Try a different search term or refresh the records."
              />
            ) : (
              <Table className="min-w-[760px]">
                <TableHeader>
                  <TableRow>
                    <TableHead>Patient</TableHead>
                    <TableHead>Contact</TableHead>
                    <TableHead>Appointments</TableHead>
                    <TableHead>Next visit</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredPatients.map((patient) => {
                    const patientAppointments = [
                      ...(appointmentsByPatient[patient.id] ?? []),
                      ...(appointmentsByPatient[patient.uin] ?? []),
                    ].filter(
                      (appointment, index, list) =>
                        list.findIndex((item) => item.id === appointment.id) ===
                        index,
                    );
                    const next = upcomingAppointment(patientAppointments);

                    return (
                      <TableRow
                        key={patient.id}
                        className={cn(
                          'cursor-pointer',
                          selectedPatient?.id === patient.id && 'bg-muted/60',
                        )}
                        data-state={
                          selectedPatient?.id === patient.id
                            ? 'selected'
                            : undefined
                        }
                        onClick={() => setSelectedPatientId(patient.id)}
                      >
                        <TableCell className="max-w-[260px] whitespace-normal">
                          <div className="space-y-1">
                            <p className="font-medium">{patient.full_name}</p>
                            <p className="text-xs text-muted-foreground">
                              UIN {patient.uin}
                            </p>
                            {patient.allergies ? (
                              <p className="line-clamp-1 text-xs text-muted-foreground">
                                Allergies: {patient.allergies}
                              </p>
                            ) : null}
                          </div>
                        </TableCell>
                        <TableCell className="max-w-[220px] whitespace-normal">
                          <div className="space-y-1 text-sm">
                            <p>{patient.phone}</p>
                            <p className="text-xs text-muted-foreground">
                              {patient.email ?? 'No email'}
                            </p>
                          </div>
                        </TableCell>
                        <TableCell>{patientAppointments.length}</TableCell>
                        <TableCell className="max-w-[190px] whitespace-normal text-sm">
                          {next ? (
                            <div className="space-y-1">
                              <p>{formatDateTime(next.start_at)}</p>
                              <p className="text-xs text-muted-foreground">
                                {next.doctors?.full_name ?? 'Unassigned doctor'}
                              </p>
                            </div>
                          ) : (
                            <span className="text-muted-foreground">-</span>
                          )}
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>

        <Card className="rounded-lg">
          <CardHeader>
            <CardTitle>Appointments</CardTitle>
            <CardDescription>
              {selectedPatient
                ? `${selectedPatient.full_name} · UIN ${selectedPatient.uin}`
                : 'Select a patient'}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-5">
            {selectedPatient ? (
              <>
                <div className="grid gap-3 text-sm sm:grid-cols-2">
                  <div>
                    <p className="text-xs font-medium uppercase text-muted-foreground">
                      Phone
                    </p>
                    <p className="flex items-center gap-2">
                      <Phone className="h-4 w-4 text-muted-foreground" />
                      {selectedPatient.phone}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs font-medium uppercase text-muted-foreground">
                      Email
                    </p>
                    <p className="flex items-center gap-2">
                      <Mail className="h-4 w-4 text-muted-foreground" />
                      {selectedPatient.email ?? 'No email'}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs font-medium uppercase text-muted-foreground">
                      Created
                    </p>
                    <p>{formatDate(selectedPatient.created_at)}</p>
                  </div>
                  <div>
                    <p className="text-xs font-medium uppercase text-muted-foreground">
                      Last visit
                    </p>
                    <p>
                      {formatDateTime(
                        lastVisitAppointment(selectedAppointments)?.start_at,
                      )}
                    </p>
                  </div>
                </div>

                {selectedPatient.allergies ? (
                  <div className="rounded-lg border bg-muted/30 p-3 text-sm">
                    <p className="text-xs font-medium uppercase text-muted-foreground">
                      Allergies
                    </p>
                    <p className="mt-1">{selectedPatient.allergies}</p>
                  </div>
                ) : null}

                <div className="space-y-3">
                  {sortedSelectedAppointments.length === 0 ? (
                    <EmptyState
                      title="No appointments linked"
                      description="This patient does not have appointments in the current appointment result set."
                    />
                  ) : (
                    sortedSelectedAppointments.map((appointment) => (
                      <div
                        key={appointment.id}
                        className="rounded-lg border p-3 text-sm"
                      >
                        <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                          <div className="space-y-1">
                            <p className="font-medium">
                              {formatDate(appointment.start_at)}
                            </p>
                            <p className="text-muted-foreground">
                              {appointment.doctors?.full_name ??
                                'Unassigned doctor'}
                            </p>
                          </div>
                          <StatusPill status={appointment.status} />
                        </div>

                        <div className="mt-3 grid gap-3 text-sm sm:grid-cols-2">
                          <DetailBlock
                            label="Specialty"
                            value={appointment.specialties?.name}
                          />
                          <DetailBlock
                            label="Urgency"
                            value={normalizeStatus(appointment.urgency)}
                          />
                          <DetailBlock
                            label="Booked at"
                            value={formatDateTime(appointment.created_at)}
                          />
                          <div>
                            <p className="text-xs font-medium uppercase text-muted-foreground">
                              Time
                            </p>
                            <p className="mt-1">
                              <Clock3 className="mr-1 inline h-4 w-4 text-muted-foreground" />
                              {formatTimeRange(
                                appointment.start_at,
                                appointment.end_at,
                              )}
                            </p>
                          </div>
                          <DetailBlock
                            label="Follow-up from"
                            value={appointment.follow_up_from_id}
                            mono
                          />
                        </div>

                        <div className="mt-3 grid gap-3 border-t pt-3">
                          <NarrativeRow
                            icon={Stethoscope}
                            label="Reason"
                            value={appointment.reason}
                          />
                          <NarrativeRow
                            icon={FileText}
                            label="Symptoms"
                            value={appointment.symptoms}
                          />
                          {appointment.specialties?.name ? (
                            <p className="flex items-center gap-2 text-xs text-muted-foreground">
                              <Link2 className="h-4 w-4" />
                              Routed to {appointment.specialties.name} during booking.
                            </p>
                          ) : null}
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </>
            ) : (
              <p className="text-sm text-muted-foreground">
                Select a patient to inspect their appointments.
              </p>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
