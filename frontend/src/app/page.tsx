'use client';

import { useQuery } from '@tanstack/react-query';
import { ArrowRight, CalendarDays, PhoneCall, Stethoscope } from 'lucide-react';
import Image from 'next/image';
import Link from 'next/link';

import { DashboardShell } from '@/components/common/dashboard-shell';
import { EmptyState } from '@/components/common/empty-state';
import { PageHeader } from '@/components/common/page-header';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { useHasMounted } from '@/hooks/use-has-mounted';
import { getAccessToken } from '@/lib/api/auth';
import { getDoctors } from '@/lib/api/doctors';

export default function LandingPage() {
  const hasMounted = useHasMounted();
  const token = hasMounted ? getAccessToken() : null;

  const doctorsQuery = useQuery({
    queryKey: ['doctors'],
    queryFn: () => getDoctors(token ?? ''),
    enabled: hasMounted && !!token,
  });

  const doctors = doctorsQuery.data ?? [];
  const specialties = new Set(doctors.flatMap((doctor) => doctor.specialties));

  return (
    <DashboardShell>
      <div className="space-y-6">
        <PageHeader
          title="Doctor Directory"
          description="Browse active doctors and open weekly availability."
          action={
            <Button asChild variant="outline">
              <Link href="/calls">
                <PhoneCall className="h-4 w-4" />
                View calls
              </Link>
            </Button>
          }
        />

        <section className="grid gap-3 sm:grid-cols-3">
          <Card className="rounded-lg py-4">
            <CardContent className="flex items-center gap-3 px-4">
              <Stethoscope className="h-5 w-5 text-muted-foreground" />
              <div>
                <p className="text-2xl font-semibold">{doctors.length}</p>
                <p className="text-xs text-muted-foreground">Active doctors</p>
              </div>
            </CardContent>
          </Card>
          <Card className="rounded-lg py-4">
            <CardContent className="flex items-center gap-3 px-4">
              <CalendarDays className="h-5 w-5 text-muted-foreground" />
              <div>
                <p className="text-2xl font-semibold">{specialties.size}</p>
                <p className="text-xs text-muted-foreground">Specialties</p>
              </div>
            </CardContent>
          </Card>
          <Card className="rounded-lg py-4">
            <CardContent className="flex items-center gap-3 px-4">
              <PhoneCall className="h-5 w-5 text-muted-foreground" />
              <div>
                <p className="text-2xl font-semibold">Live</p>
                <p className="text-xs text-muted-foreground">Call monitor</p>
              </div>
            </CardContent>
          </Card>
        </section>

        {doctorsQuery.isPending ? (
          <Card className="rounded-lg">
            <CardContent className="p-6">
              <p className="text-sm text-muted-foreground">
                Loading doctors...
              </p>
            </CardContent>
          </Card>
        ) : null}

        {doctorsQuery.isError ? (
          <Card className="rounded-lg border-red-200">
            <CardContent className="p-6">
              <p className="text-sm text-red-600">
                Failed to load doctors from the backend.
              </p>
            </CardContent>
          </Card>
        ) : null}

        {doctorsQuery.isSuccess && doctors.length === 0 ? (
          <EmptyState
            title="No active doctors found"
            description="Add doctors in the backend seed data or admin tooling to populate the schedule directory."
          />
        ) : null}

        {doctors.length > 0 ? (
          <section className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
            {doctors.map((doctor) => (
              <Link
                key={doctor.id}
                href={`/doctors/${doctor.id}`}
                className="group block h-full"
              >
                <Card className="h-full rounded-lg transition hover:border-primary/60 hover:shadow-sm">
                  <CardHeader className="flex-row items-center gap-4 space-y-0">
                    {doctor.image_url ? (
                      <Image
                        src={doctor.image_url}
                        alt={doctor.full_name}
                        width={56}
                        height={56}
                        className="h-14 w-14 rounded-full object-cover"
                        unoptimized
                      />
                    ) : (
                      <div className="flex h-14 w-14 items-center justify-center rounded-full bg-muted">
                        <Stethoscope className="h-6 w-6 text-muted-foreground" />
                      </div>
                    )}
                    <CardTitle className="text-lg">
                      {doctor.full_name}
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="flex flex-1 flex-col gap-4">
                    <div className="flex flex-wrap gap-2">
                      {doctor.specialties.length > 0 ? (
                        doctor.specialties.map((specialty) => (
                          <span
                            key={specialty}
                            className="rounded-full bg-muted px-3 py-1 text-xs font-medium text-muted-foreground"
                          >
                            {specialty}
                          </span>
                        ))
                      ) : (
                        <span className="rounded-full border px-3 py-1 text-xs font-medium">
                          General Practice
                        </span>
                      )}
                    </div>

                    <div className="mt-auto flex items-center justify-between border-t pt-4 text-sm font-medium">
                      <span>Weekly availability</span>
                      <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
                    </div>
                  </CardContent>
                </Card>
              </Link>
            ))}
          </section>
        ) : null}
      </div>
    </DashboardShell>
  );
}
