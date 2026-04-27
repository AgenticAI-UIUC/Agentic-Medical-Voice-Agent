'use client';

import { useQuery } from '@tanstack/react-query';
import { Stethoscope, LogOut } from 'lucide-react';
import Image from 'next/image';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useEffect } from 'react';

import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { logout } from '@/hooks/use-auth';
import { useHasMounted } from '@/hooks/use-has-mounted';
import { getAccessToken } from '@/lib/api/auth';
import { ApiError } from '@/lib/api/client';
import { getDoctors } from '@/lib/api/doctors';
import { ThemeToggle } from '@/components/common/theme-toggle';

export default function LandingPage() {
  const router = useRouter();
  const hasMounted = useHasMounted();
  const token = hasMounted ? getAccessToken() : null;

  const doctorsQuery = useQuery({
    queryKey: ['doctors'],
    queryFn: () => getDoctors(token ?? ''),
    enabled: hasMounted && !!token,
  });

  useEffect(() => {
    if (hasMounted && !token) {
      router.replace('/login');
    }
  }, [hasMounted, router, token]);

  useEffect(() => {
    if (
      doctorsQuery.error instanceof ApiError &&
      [401, 403].includes(doctorsQuery.error.status)
    ) {
      void logout().finally(() => router.replace('/login'));
    }
  }, [doctorsQuery.error, router]);

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
    <main className="mx-auto min-h-screen max-w-6xl p-6">
      <header className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-semibold">Find a doctor</h1>
          <p className="text-sm text-muted-foreground">
            Browse doctors and open their weekly availability.
          </p>
        </div>
        <div className="flex gap-2">
          <ThemeToggle />
          <Button
            variant="outline"
            onClick={async () => {
              await logout();
              router.replace('/login');
            }}
          >
            <LogOut className="mr-2 h-4 w-4" />
            Logout
          </Button>
        </div>
      </header>

      {doctorsQuery.isPending && (
        <p className="text-sm text-muted-foreground">Loading doctors...</p>
      )}

      {doctorsQuery.isSuccess && doctorsQuery.data.length === 0 && (
        <p className="text-sm text-muted-foreground">
          No active doctors found.
        </p>
      )}

      <section className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
        {doctorsQuery.data?.map((doctor) => (
          <Link key={doctor.id} href={`/doctors/${doctor.id}`}>
            <Card className="h-full transition hover:border-primary/60 hover:shadow-sm">
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
                <CardTitle className="text-lg">{doctor.full_name}</CardTitle>
              </CardHeader>
              <CardContent className="flex flex-wrap gap-2">
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
              </CardContent>
            </Card>
          </Link>
        ))}
      </section>
    </main>
  );
}
