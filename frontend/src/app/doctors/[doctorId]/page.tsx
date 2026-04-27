'use client';

import { useQuery } from '@tanstack/react-query';
import {
  AlertCircle,
  CalendarClock,
  ChevronLeft,
  ChevronRight,
  FileText,
  Mail,
  Phone,
  UserRound,
} from 'lucide-react';
import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import { useEffect, useMemo, useState } from 'react';
import { Fragment } from 'react';

import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { useHasMounted } from '@/hooks/use-has-mounted';
import { getAccessToken } from '@/lib/api/auth';
import { ApiError } from '@/lib/api/client';
import { type DoctorSlot, getDoctorSchedule } from '@/lib/api/doctors';
import { logout } from '@/hooks/use-auth';

const START_HOUR = 8;
const END_HOUR = 20;
const GRID_HOURS = Array.from(
  { length: END_HOUR - START_HOUR + 1 },
  (_, i) => START_HOUR + i,
);

function startOfWeek(input: Date) {
  const date = new Date(input);
  const day = date.getDay();
  date.setDate(date.getDate() - day);
  date.setHours(0, 0, 0, 0);
  return date;
}

function formatDateOnly(date: Date) {
  return date.toISOString().slice(0, 10);
}

function hourLabel(hour: number) {
  const suffix = hour >= 12 ? 'PM' : 'AM';
  const normalized = hour % 12 === 0 ? 12 : hour % 12;
  return `${normalized} ${suffix}`;
}

function shouldShowSkeletonSlot(hour: number, dayIndex: number) {
  return (hour + dayIndex) % 3 === 0 || (hour === 9 && dayIndex % 2 === 0);
}

function slotTime(slot: DoctorSlot) {
  return new Date(slot.start_at).toLocaleTimeString([], {
    hour: '2-digit',
    minute: '2-digit',
  });
}

function slotTimeRange(slot: DoctorSlot) {
  const start = slotTime(slot);
  const end = new Date(slot.end_at).toLocaleTimeString([], {
    hour: '2-digit',
    minute: '2-digit',
  });
  return `${start} - ${end}`;
}

function patientName(slot: DoctorSlot) {
  return slot.patient?.full_name ?? slot.patient?.uin ?? 'Booked patient';
}

function patientHref(slot: DoctorSlot) {
  const search = new URLSearchParams();
  if (slot.patient?.id) {
    search.set('patientId', slot.patient.id);
  } else if (slot.patient?.uin) {
    search.set('uin', slot.patient.uin);
  }
  const qs = search.toString();
  return `/patients${qs ? `?${qs}` : ''}`;
}

function DetailRow({
  icon: Icon,
  label,
  value,
}: {
  icon: typeof UserRound;
  label: string;
  value?: string | null;
}) {
  return (
    <div className="flex items-start gap-3 rounded-md border p-3">
      <Icon className="mt-0.5 h-4 w-4 text-muted-foreground" />
      <div className="min-w-0">
        <dt className="text-xs font-medium uppercase text-muted-foreground">
          {label}
        </dt>
        <dd className="mt-1 wrap-break-word text-sm">
          {value?.trim() || 'Not recorded'}
        </dd>
      </div>
    </div>
  );
}

function ScheduleTableSkeleton({ days }: { days: Date[] }) {
  return (
    <div
      aria-busy="true"
      aria-label="Loading doctor schedule"
      className="overflow-x-auto rounded-xl border"
    >
      <div className="grid min-w-245 grid-cols-[90px_repeat(7,minmax(120px,1fr))]">
        <div className="border-b bg-muted/40 p-3" />
        {days.map((day) => (
          <div
            key={day.toISOString()}
            className="border-b border-l bg-muted/40 p-3 text-center"
          >
            <p className="text-xs uppercase text-muted-foreground">
              {day.toLocaleDateString(undefined, { weekday: 'short' })}
            </p>
            <p className="text-sm font-medium">
              {day.toLocaleDateString('en-US', {
                month: '2-digit',
                day: '2-digit',
                year: 'numeric',
              })}
            </p>
          </div>
        ))}

        {GRID_HOURS.map((hour) => (
          <Fragment key={hour}>
            <div className="border-b p-2 text-right text-xs text-muted-foreground">
              {hourLabel(hour)}
            </div>
            {days.map((day, dayIndex) => (
              <div
                key={`${day.toISOString()}-${hour}`}
                className="min-h-12 border-b border-l p-1"
              >
                {shouldShowSkeletonSlot(hour, dayIndex) && (
                  <div className="mb-1 h-9 w-full animate-pulse rounded-md bg-muted" />
                )}
              </div>
            ))}
          </Fragment>
        ))}
      </div>
    </div>
  );
}

export default function DoctorSchedulePage() {
  const router = useRouter();
  const params = useParams<{ doctorId: string }>();
  const hasMounted = useHasMounted();
  const token = hasMounted ? getAccessToken() : null;

  const [weekStart, setWeekStart] = useState(() => startOfWeek(new Date()));
  const [selectedSlot, setSelectedSlot] = useState<DoctorSlot | null>(null);

  const scheduleQuery = useQuery({
    queryKey: ['doctor-schedule', params.doctorId, formatDateOnly(weekStart)],
    queryFn: () =>
      getDoctorSchedule(token ?? '', params.doctorId, {
        startDate: formatDateOnly(weekStart),
        days: 7,
      }),
    enabled: hasMounted && !!token,
  });

  const days = useMemo(() => {
    return Array.from({ length: 7 }, (_, index) => {
      const date = new Date(weekStart);
      date.setDate(weekStart.getDate() + index);
      return date;
    });
  }, [weekStart]);

  useEffect(() => {
    if (hasMounted && !token) {
      router.replace('/login');
    }
  }, [hasMounted, router, token]);

  useEffect(() => {
    if (
      scheduleQuery.error instanceof ApiError &&
      [401, 403].includes(scheduleQuery.error.status)
    ) {
      void logout().finally(() => router.replace('/login'));
    }
  }, [scheduleQuery.error, router]);

  if (!hasMounted) {
    return (
      <main className="mx-auto min-h-screen max-w-7xl p-6">Loading app...</main>
    );
  }

  if (!token) {
    return (
      <main className="mx-auto min-h-screen max-w-7xl p-6">
        Redirecting to login...
      </main>
    );
  }

  return (
    <main className="mx-auto min-h-screen max-w-7xl p-6">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <Link
            href="/"
            className="text-sm text-muted-foreground hover:text-foreground"
          >
            ← Back to doctors
          </Link>
          <h1 className="mt-2 text-2xl font-semibold">
            {scheduleQuery.data?.doctor_name ?? 'Doctor schedule'}
          </h1>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="icon"
            onClick={() =>
              setWeekStart((curr) => {
                const next = new Date(curr);
                next.setDate(curr.getDate() - 7);
                return next;
              })
            }
          >
            <ChevronLeft className="h-4 w-4" />
          </Button>
          <Button
            variant="outline"
            size="icon"
            onClick={() =>
              setWeekStart((curr) => {
                const next = new Date(curr);
                next.setDate(curr.getDate() + 7);
                return next;
              })
            }
          >
            <ChevronRight className="h-4 w-4" />
          </Button>
        </div>
      </div>

      {scheduleQuery.isPending && <ScheduleTableSkeleton days={days} />}

      {scheduleQuery.isSuccess && (
        <div className="overflow-x-auto rounded-xl border">
          <div className="grid min-w-245 grid-cols-[90px_repeat(7,minmax(120px,1fr))]">
            <div className="border-b bg-muted/40 p-3" />
            {days.map((day) => (
              <div
                key={day.toISOString()}
                className="border-b border-l bg-muted/40 p-3 text-center"
              >
                <p className="text-xs uppercase text-muted-foreground">
                  {day.toLocaleDateString(undefined, { weekday: 'short' })}
                </p>
                <p className="text-sm font-medium">
                  {day.toLocaleDateString('en-US', {
                    month: '2-digit',
                    day: '2-digit',
                    year: 'numeric',
                  })}
                </p>
              </div>
            ))}

            {GRID_HOURS.map((hour) => (
              <Fragment key={hour}>
                <div
                  key={`label-${hour}`}
                  className="border-b p-2 text-right text-xs text-muted-foreground"
                >
                  {hourLabel(hour)}
                </div>
                {days.map((day) => {
                  const daySchedule = scheduleQuery.data.schedule.find(
                    (item) => item.date === formatDateOnly(day),
                  );

                  const slots = (daySchedule?.slots ?? []).filter((slot) => {
                    const slotStart = new Date(slot.start_at);
                    return slotStart.getHours() === hour;
                  });

                  return (
                    <div
                      key={`${day.toISOString()}-${hour}`}
                      className="relative min-h-12 border-b border-l p-1"
                    >
                      {slots.map((slot) => {
                        const slotClass = `mb-1 w-full rounded-md px-2 py-1 text-left text-xs font-medium ${
                          slot.status === 'AVAILABLE'
                            ? 'bg-emerald-100 text-emerald-700'
                            : slot.status === 'BOOKED'
                              ? 'bg-rose-100 text-rose-700 hover:bg-rose-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rose-400 cursor-pointer'
                              : 'bg-slate-200 text-slate-700'
                        }`;

                        if (slot.status === 'BOOKED') {
                          return (
                            <button
                              key={slot.id}
                              type="button"
                              className={slotClass}
                              onClick={() => setSelectedSlot(slot)}
                              aria-label={`View booked appointment for ${patientName(slot)}`}
                            >
                              <p>{slotTime(slot)}</p>
                              <p>BOOKED</p>
                              <p className="truncate text-[11px] font-normal">
                                {patientName(slot)}
                              </p>
                            </button>
                          );
                        }

                        return (
                          <div key={slot.id} className={slotClass}>
                            <p>{slotTime(slot)}</p>
                            <p>{slot.status}</p>
                          </div>
                        );
                      })}
                    </div>
                  );
                })}
              </Fragment>
            ))}
          </div>
        </div>
      )}

      <Dialog
        open={selectedSlot !== null}
        onOpenChange={(open) => {
          if (!open) setSelectedSlot(null);
        }}
      >
        {selectedSlot && (
          <DialogContent>
            <DialogHeader>
              <DialogTitle>{patientName(selectedSlot)}</DialogTitle>
              <DialogDescription>
                Booked appointment, {slotTimeRange(selectedSlot)}
              </DialogDescription>
            </DialogHeader>

            <dl className="grid gap-3 sm:grid-cols-2">
              <DetailRow
                icon={UserRound}
                label="UIN"
                value={selectedSlot.patient?.uin}
              />
              <DetailRow
                icon={Phone}
                label="Phone"
                value={selectedSlot.patient?.phone}
              />
              <DetailRow
                icon={Mail}
                label="Email"
                value={selectedSlot.patient?.email}
              />
              <DetailRow
                icon={AlertCircle}
                label="Urgency"
                value={selectedSlot.urgency}
              />
              <div className="sm:col-span-2">
                <DetailRow
                  icon={CalendarClock}
                  label="Reason"
                  value={selectedSlot.reason}
                />
              </div>
              <div className="sm:col-span-2">
                <DetailRow
                  icon={FileText}
                  label="Symptoms"
                  value={selectedSlot.symptoms}
                />
              </div>
            </dl>

            <DialogFooter>
              {(selectedSlot.patient?.id || selectedSlot.patient?.uin) && (
                <Button asChild>
                  <Link href={patientHref(selectedSlot)}>
                    <UserRound className="h-4 w-4" />
                    View patient
                  </Link>
                </Button>
              )}
            </DialogFooter>
          </DialogContent>
        )}
      </Dialog>
    </main>
  );
}
