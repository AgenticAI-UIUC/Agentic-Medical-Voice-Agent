'use client';

import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { useEffect } from 'react';

import { Button } from '@/components/ui/button';
import { logout, useCurrentUserQuery } from '@/hooks/use-auth';
import { getAccessToken } from '@/lib/api/auth';
import { ApiError } from '@/lib/api/client';
import { ThemeToggle } from '@/components/common/theme-toggle';
import { useHasMounted } from '@/hooks/use-has-mounted';

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
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
    <div className="min-h-screen">
      <header className="border-b">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-6 py-4">
          <div className="space-y-1">
            <p className="text-lg font-semibold">Dashboard</p>
            <p className="text-sm text-muted-foreground">
              {meQuery.isSuccess ? meQuery.data.email : 'Loading user...'}
            </p>
          </div>

          <div className="flex items-center gap-2">
            <Link
              href="/"
              className={
                pathname === '/' ? 'font-medium' : 'text-muted-foreground'
              }
            >
              Home
            </Link>
            <Link
              href="/users"
              className={
                pathname === '/users'
                  ? 'rounded px-2 py-1 text-sm font-medium bg-muted'
                  : 'rounded px-2 py-1 text-sm text-muted-foreground hover:text-foreground'
              }
            >
              Users
            </Link>
            <Link
              href="/settings"
              className={
                pathname === '/settings'
                  ? 'rounded bg-muted px-2 py-1 text-sm font-medium'
                  : 'rounded px-2 py-1 text-sm text-muted-foreground hover:text-foreground'
              }
            >
              Settings
            </Link>

            <ThemeToggle />
            <Button variant="outline" onClick={handleLogout}>
              Logout
            </Button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-5xl p-6">{children}</main>
    </div>
  );
}
