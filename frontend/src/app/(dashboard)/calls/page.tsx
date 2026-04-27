'use client';

import {
  Activity,
  CalendarDays,
  ClipboardCheck,
  Clock3,
  PhoneCall,
  RefreshCw,
} from 'lucide-react';
import Link from 'next/link';
import { useState } from 'react';

import { PageHeader } from '@/components/common/page-header';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { useStaffCallsQuery } from '@/hooks/use-calls';
import type { StaffCall } from '@/lib/api/calls';
import { cn } from '@/lib/utils';

type TranscriptLine = {
  role: string;
  text: string;
  isPartial: boolean;
  time?: string;
};

const STATUS_FILTERS = [
  { label: 'All', value: undefined },
  { label: 'Live', value: 'in-progress' },
  { label: 'Ended', value: 'ended' },
  { label: 'Ringing', value: 'ringing' },
] as const;

function formatDateTime(value?: string | null) {
  if (!value) return '-';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
}

function formatShortTime(value?: string | null) {
  if (!value) return '-';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleTimeString([], {
    hour: 'numeric',
    minute: '2-digit',
  });
}

function asText(value: unknown): string {
  if (typeof value === 'string') return value;
  if (typeof value === 'number' || typeof value === 'boolean') {
    return String(value);
  }
  if (Array.isArray(value)) {
    return value.map(asText).filter(Boolean).join(' ');
  }
  if (value && typeof value === 'object') {
    const record = value as Record<string, unknown>;
    if (record.text) return asText(record.text);
    if (record.content) return asText(record.content);
  }
  return '';
}

const PUBLIC_TRANSCRIPT_ROLES = new Set([
  'assistant',
  'message',
  'transcript',
  'user',
]);

function normalizeTranscriptRole(value: unknown) {
  const role = asText(value).trim().toLowerCase();
  if (role === 'bot') return 'assistant';
  if (role === 'customer' || role === 'human') return 'user';
  if (!role) return 'message';
  return PUBLIC_TRANSCRIPT_ROLES.has(role) ? role : null;
}

function normalizeTranscript(transcript: unknown): TranscriptLine[] {
  if (Array.isArray(transcript)) {
    return transcript
      .map((item) => {
        if (typeof item === 'string') {
          return {
            role: 'transcript',
            text: item,
            isPartial: false,
          };
        }

        if (!item || typeof item !== 'object') return null;

        const record = item as Record<string, unknown>;
        const role = normalizeTranscriptRole(record.role || record.speaker);
        if (!role) return null;

        const text =
          asText(record.message) ||
          asText(record.transcript) ||
          asText(record.content) ||
          asText(record.text);

        if (!text.trim()) return null;

        return {
          role,
          text,
          isPartial:
            record.transcript_type === 'partial' ||
            record.transcriptType === 'partial',
          time:
            asText(record.secondsFromStart) ||
            asText(record.time) ||
            undefined,
        };
      })
      .filter((line): line is TranscriptLine => Boolean(line));
  }

  const text = asText(transcript);
  return text
    ? [
        {
          role: 'transcript',
          text,
          isPartial: false,
        },
      ]
    : [];
}

function statusLabel(status: string) {
  return status
    .split('-')
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ');
}

function StatusPill({ status }: { status: string }) {
  const tone =
    status === 'in-progress'
      ? 'border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-900 dark:bg-emerald-950 dark:text-emerald-300'
      : status === 'ended'
        ? 'border-slate-200 bg-slate-50 text-slate-700 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300'
        : status === 'ringing' || status === 'queued'
          ? 'border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-300'
          : 'border-blue-200 bg-blue-50 text-blue-700 dark:border-blue-900 dark:bg-blue-950 dark:text-blue-300';

  return (
    <span
      className={cn(
        'inline-flex min-w-0 items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium',
        tone,
      )}
    >
      {status === 'in-progress' ? (
        <span className="h-1.5 w-1.5 rounded-full bg-current" />
      ) : null}
      {statusLabel(status || 'unknown')}
    </span>
  );
}

function patientName(call: StaffCall) {
  return call.patient?.full_name || call.patient?.uin || 'Unknown patient';
}

function patientRecordHref(call: StaffCall) {
  const search = new URLSearchParams();

  if (call.patient?.id) {
    search.set('patientId', call.patient.id);
  } else if (call.patient?.uin) {
    search.set('uin', call.patient.uin);
  }

  const qs = search.toString();
  return `/patients${qs ? `?${qs}` : ''}`;
}

function hasPatientRecord(call: StaffCall) {
  return Boolean(call.patient?.id || call.patient?.uin);
}

function appointmentLabel(call: StaffCall) {
  const appointment = call.appointments[0];
  if (!appointment) return 'No appointment linked';

  const doctor = appointment.doctors?.full_name || 'doctor';
  const when = formatDateTime(appointment.start_at);
  return `${appointment.status ?? 'Appointment'} with ${doctor} at ${when}`;
}

function latestTranscriptLine(call: StaffCall) {
  const lines = normalizeTranscript(call.transcript);
  return lines.at(-1)?.text ?? call.summary ?? 'No transcript yet';
}

export default function CallsPage() {
  const [status, setStatus] = useState<string | undefined>(undefined);
  const callsQuery = useStaffCallsQuery({ status, limit: 50 });
  const calls = callsQuery.data ?? [];
  const [selectedCallId, setSelectedCallId] = useState<string | null>(null);

  const selectedCall =
    calls.find((call) => call.id === selectedCallId) ?? calls[0] ?? null;

  const stats = {
    total: calls.length,
    live: calls.filter((call) => call.call_status === 'in-progress').length,
    ended: calls.filter((call) => call.call_status === 'ended').length,
    outcomes: calls.filter((call) => call.outcome).length,
  };

  const transcriptLines = selectedCall
    ? normalizeTranscript(selectedCall.transcript)
    : [];

  return (
    <div className="space-y-6">
      <PageHeader
        title="Vapi Calls"
        description="Monitor live and recent patient calls alongside scheduling work."
        action={
          <div className="flex flex-wrap gap-2">
            <Button asChild variant="outline">
              <Link href="/">
                <CalendarDays className="h-4 w-4" />
                Doctors
              </Link>
            </Button>
            <Button
              variant="outline"
              onClick={() => void callsQuery.refetch()}
              disabled={callsQuery.isFetching}
            >
              <RefreshCw
                className={cn(
                  'h-4 w-4',
                  callsQuery.isFetching && 'animate-spin',
                )}
              />
              Refresh
            </Button>
          </div>
        }
      />

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Card className="rounded-lg py-4">
          <CardContent className="flex items-center gap-3 px-4">
            <PhoneCall className="h-5 w-5 text-muted-foreground" />
            <div>
              <p className="text-2xl font-semibold">{stats.total}</p>
              <p className="text-xs text-muted-foreground">Total calls</p>
            </div>
          </CardContent>
        </Card>
        <Card className="rounded-lg py-4">
          <CardContent className="flex items-center gap-3 px-4">
            <Activity className="h-5 w-5 text-emerald-600" />
            <div>
              <p className="text-2xl font-semibold">{stats.live}</p>
              <p className="text-xs text-muted-foreground">Live now</p>
            </div>
          </CardContent>
        </Card>
        <Card className="rounded-lg py-4">
          <CardContent className="flex items-center gap-3 px-4">
            <Clock3 className="h-5 w-5 text-muted-foreground" />
            <div>
              <p className="text-2xl font-semibold">{stats.ended}</p>
              <p className="text-xs text-muted-foreground">Ended</p>
            </div>
          </CardContent>
        </Card>
        <Card className="rounded-lg py-4">
          <CardContent className="flex items-center gap-3 px-4">
            <ClipboardCheck className="h-5 w-5 text-blue-600" />
            <div>
              <p className="text-2xl font-semibold">{stats.outcomes}</p>
              <p className="text-xs text-muted-foreground">Outcomes</p>
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="flex flex-wrap gap-2">
        {STATUS_FILTERS.map((filter) => (
          <Button
            key={filter.label}
            variant={status === filter.value ? 'default' : 'outline'}
            size="sm"
            onClick={() => setStatus(filter.value)}
          >
            {filter.label}
          </Button>
        ))}
      </div>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1.05fr)_minmax(360px,0.95fr)]">
        <Card className="rounded-lg">
          <CardHeader>
            <CardTitle>Call Feed</CardTitle>
            <CardDescription>
              {callsQuery.isFetching
                ? 'Updating...'
                : `Last checked ${new Date().toLocaleTimeString([], {
                    hour: 'numeric',
                    minute: '2-digit',
                    second: '2-digit',
                  })}`}
            </CardDescription>
          </CardHeader>
          <CardContent>
            {callsQuery.isPending ? (
              <p className="text-sm text-muted-foreground">Loading calls...</p>
            ) : callsQuery.isError ? (
              <p className="text-sm text-red-600">Failed to load calls.</p>
            ) : calls.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                No calls found for this filter.
              </p>
            ) : (
              <Table className="min-w-[760px]">
                <TableHeader>
                  <TableRow>
                    <TableHead>Call</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Outcome</TableHead>
                    <TableHead>Updated</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {calls.map((call) => (
                    <TableRow
                      key={call.id}
                      className={cn(
                        'cursor-pointer',
                        selectedCall?.id === call.id && 'bg-muted/60',
                      )}
                      data-state={
                        selectedCall?.id === call.id ? 'selected' : undefined
                      }
                      onClick={() => setSelectedCallId(call.id)}
                    >
                      <TableCell className="max-w-[280px] whitespace-normal">
                        <div className="space-y-1">
                          <p className="font-medium">{patientName(call)}</p>
                          <p className="break-all text-xs text-muted-foreground">
                            {call.call_id}
                          </p>
                          <p className="line-clamp-2 text-xs text-muted-foreground">
                            {latestTranscriptLine(call)}
                          </p>
                        </div>
                      </TableCell>
                      <TableCell>
                        <StatusPill status={call.call_status} />
                      </TableCell>
                      <TableCell className="max-w-[180px] whitespace-normal text-sm">
                        {call.outcome ?? call.ended_reason ?? '-'}
                      </TableCell>
                      <TableCell>{formatShortTime(call.last_event_at)}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>

        <Card className="rounded-lg">
          <CardHeader>
            <CardTitle>Transcript</CardTitle>
            <CardDescription>
              {selectedCall ? appointmentLabel(selectedCall) : 'No call selected'}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-5">
            {selectedCall ? (
              <>
                <div className="grid gap-3 text-sm sm:grid-cols-2">
                  <div>
                    <p className="text-xs font-medium uppercase text-muted-foreground">
                      Patient
                    </p>
                    {hasPatientRecord(selectedCall) ? (
                      <Link
                        href={patientRecordHref(selectedCall)}
                        className="font-medium text-primary underline-offset-4 hover:underline"
                      >
                        {patientName(selectedCall)}
                      </Link>
                    ) : (
                      <p>{patientName(selectedCall)}</p>
                    )}
                  </div>
                  <div>
                    <p className="text-xs font-medium uppercase text-muted-foreground">
                      Status
                    </p>
                    <StatusPill status={selectedCall.call_status} />
                  </div>
                  <div>
                    <p className="text-xs font-medium uppercase text-muted-foreground">
                      Started
                    </p>
                    <p>{formatDateTime(selectedCall.started_at)}</p>
                  </div>
                  <div>
                    <p className="text-xs font-medium uppercase text-muted-foreground">
                      Ended
                    </p>
                    <p>{formatDateTime(selectedCall.ended_at)}</p>
                  </div>
                </div>

                {selectedCall.summary ? (
                  <div className="rounded-lg border bg-muted/30 p-3 text-sm">
                    {selectedCall.summary}
                  </div>
                ) : null}

                <div className="max-h-[560px] space-y-3 overflow-y-auto pr-1">
                  {transcriptLines.length === 0 ? (
                    <p className="text-sm text-muted-foreground">
                      No transcript has arrived yet.
                    </p>
                  ) : (
                    transcriptLines.map((line, index) => (
                      <div
                        key={`${line.role}-${index}-${line.text.slice(0, 20)}`}
                        className={cn(
                          'rounded-lg border p-3 text-sm',
                          line.role === 'assistant'
                            ? 'bg-muted/40'
                            : 'bg-background',
                        )}
                      >
                        <div className="mb-1 flex items-center justify-between gap-2">
                          <p className="font-medium capitalize">{line.role}</p>
                          <div className="flex items-center gap-2 text-xs text-muted-foreground">
                            {line.isPartial ? <span>Partial</span> : null}
                            {line.time ? <span>{line.time}s</span> : null}
                          </div>
                        </div>
                        <p className="whitespace-pre-wrap break-words leading-6">
                          {line.text}
                        </p>
                      </div>
                    ))
                  )}
                </div>
              </>
            ) : (
              <p className="text-sm text-muted-foreground">
                Select a call to inspect its transcript.
              </p>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
