'use client';

import { useQuery } from '@tanstack/react-query';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import { useEffect, useMemo, useState } from 'react';
import { Fragment } from 'react';

import { Button } from '@/components/ui/button';
import { useHasMounted } from '@/hooks/use-has-mounted';
import { getAccessToken } from '@/lib/api/auth';
import { ApiError } from '@/lib/api/client';
import { getDoctorSchedule } from '@/lib/api/doctors';
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

export default function DoctorSchedulePage() {
  const router = useRouter();
  const params = useParams<{ doctorId: string }>();
  const hasMounted = useHasMounted();
  const token = hasMounted ? getAccessToken() : null;

  const [weekStart, setWeekStart] = useState(() => startOfWeek(new Date()));

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
      <main className="mx-auto min-h-screen max-w-7xl p-6">
        Loading app...
      </main>
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

      {scheduleQuery.isPending && (
        <p className="text-muted-foreground">Loading schedule...</p>
      )}

      {scheduleQuery.isSuccess && (
        <div className="overflow-x-auto rounded-xl border">
          <div className="grid min-w-[980px] grid-cols-[90px_repeat(7,minmax(120px,1fr))]">
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
                      className="relative border-b border-l p-1"
                    >
                      {slots.map((slot) => (
                        <div
                          key={slot.id}
                          className={`mb-1 rounded-md px-2 py-1 text-xs font-medium ${
                            slot.status === 'AVAILABLE'
                              ? 'bg-emerald-100 text-emerald-700'
                              : slot.status === 'BOOKED'
                                ? 'bg-rose-100 text-rose-700'
                                : 'bg-slate-200 text-slate-700'
                          }`}
                        >
                          <p>
                            {new Date(slot.start_at).toLocaleTimeString([], {
                              hour: '2-digit',
                              minute: '2-digit',
                            })}
                          </p>
                          <p>{slot.status}</p>
                        </div>
                      ))}
                    </div>
                  );
                })}
              </Fragment>
            ))}
          </div>
        </div>
      )}
    </main>
  );
}
