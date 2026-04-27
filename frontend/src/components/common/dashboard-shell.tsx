'use client';

import {
  CalendarDays,
  LogOut,
  PhoneCall,
  Settings,
  Stethoscope,
  Users,
} from 'lucide-react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { useEffect } from 'react';
import type { ReactNode } from 'react';

import { ThemeToggle } from '@/components/common/theme-toggle';
import { Button } from '@/components/ui/button';
import { logout, useCurrentUserQuery } from '@/hooks/use-auth';
import { useHasMounted } from '@/hooks/use-has-mounted';
import { getAccessToken } from '@/lib/api/auth';
import { ApiError } from '@/lib/api/client';
import { cn } from '@/lib/utils';

const navItems = [
  { href: '/', label: 'Doctors', icon: Stethoscope },
  { href: '/calls', label: 'Calls', icon: PhoneCall },
  { href: '/patients', label: 'Patients', icon: Users },
  { href: '/settings', label: 'Settings', icon: Settings },
];

export function DashboardShell({ children }: { children: ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const hasMounted = useHasMounted();
  const token = hasMounted ? getAccessToken() : null;

  const meQuery = useCurrentUserQuery({ enabled: hasMounted && !!token });

  useEffect(() => {
    if (hasMounted && !token) {
      router.replace('/login');
    }
  }, [hasMounted, token, router]);

  useEffect(() => {
    if (
      meQuery.error instanceof ApiError &&
      [401, 403].includes(meQuery.error.status)
    ) {
      void logout().finally(() => router.replace('/login'));
    }
  }, [meQuery.error, router]);

  const handleLogout = async () => {
    await logout();
    router.replace('/login');
  };

  if (!hasMounted) {
    return (
      <div className="flex min-h-screen items-center justify-center p-6">
        <p className="text-sm text-muted-foreground">Loading app...</p>
      </div>
    );
  }

  if (!token) {
    return (
      <div className="flex min-h-screen items-center justify-center p-6">
        <p className="text-sm text-muted-foreground">Redirecting to login...</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-muted/10">
      <header className="border-b bg-background">
        <div className="mx-auto flex max-w-7xl flex-col gap-4 px-4 py-4 sm:px-6 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex min-w-0 items-center gap-3">
            <div className="flex size-10 shrink-0 items-center justify-center rounded-lg border bg-muted">
              <CalendarDays className="h-5 w-5 text-muted-foreground" />
            </div>
            <div className="min-w-0">
              <p className="truncate text-base font-semibold">
                Medical Voice Agent
              </p>
              <p className="truncate text-sm text-muted-foreground">
                {meQuery.isSuccess ? meQuery.data.email : 'Loading user...'}
              </p>
            </div>
          </div>

          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between lg:justify-end">
            <nav className="flex min-w-0 flex-wrap items-center gap-1">
              {navItems.map((item) => {
                const Icon = item.icon;
                const isActive =
                  item.href === '/'
                    ? pathname === '/'
                    : pathname.startsWith(item.href);

                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={cn(
                      'inline-flex h-9 items-center gap-2 rounded-md px-3 text-sm font-medium transition-colors hover:bg-muted hover:text-foreground',
                      isActive
                        ? 'bg-muted text-foreground'
                        : 'text-muted-foreground',
                    )}
                  >
                    <Icon className="h-4 w-4" />
                    {item.label}
                  </Link>
                );
              })}
            </nav>

            <div className="flex items-center gap-2">
              <ThemeToggle />
              <Button variant="outline" onClick={handleLogout}>
                <LogOut className="h-4 w-4" />
                Logout
              </Button>
            </div>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-7xl p-4 sm:p-6">{children}</main>
    </div>
  );
}
