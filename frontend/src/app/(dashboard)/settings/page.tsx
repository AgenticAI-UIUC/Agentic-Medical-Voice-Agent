'use client';

import { useMemo } from 'react';

import { PageHeader } from '@/components/common/page-header';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { ProfileForm } from '@/components/forms/profile-form';
import { ChangePasswordForm } from '@/components/forms/change-password-form';
import {
  useChangeMyPasswordMutation,
  useCurrentUserQuery,
  useUpdateMeMutation,
} from '@/hooks/use-auth';
import { ApiError } from '@/lib/api/client';
import { formatApiDetail } from '@/lib/api/errors';
import { toast } from 'sonner';

function getApiErrorMessage(error: unknown, fallback: string) {
  if (error instanceof ApiError) {
    if (
      typeof error.body === 'object' &&
      error.body !== null &&
      'detail' in error.body
    ) {
      return formatApiDetail((error.body as { detail?: unknown }).detail);
    }
    return error.message || fallback;
  }

  if (error instanceof Error) return error.message;
  return fallback;
}

export default function SettingsPage() {
  const meQuery = useCurrentUserQuery();
  const updateMeMutation = useUpdateMeMutation();
  const changePasswordMutation = useChangeMyPasswordMutation();

  const profileDefaults = useMemo(() => {
    if (!meQuery.data) {
      return {
        email: '',
        full_name: '',
      };
    }

    return {
      email: meQuery.data.email ?? '',
      full_name: meQuery.data.full_name ?? '',
    };
  }, [meQuery.data]);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Settings"
        description="Manage your profile and password."
      />

      {meQuery.isPending ? (
        <Card>
          <CardContent className="p-6">
            <p className="text-sm text-muted-foreground">Loading profile...</p>
          </CardContent>
        </Card>
      ) : null}

      {meQuery.isError ? (
        <Card>
          <CardContent className="p-6">
            <p className="text-sm text-destructive">
              Failed to load profile information.
            </p>
          </CardContent>
        </Card>
      ) : null}

      {meQuery.isSuccess ? (
        <>
          <Card>
            <CardHeader>
              <CardTitle>Profile</CardTitle>
            </CardHeader>
            <CardContent>
              <ProfileForm
                defaultValues={profileDefaults}
                isSubmitting={updateMeMutation.isPending}
                onSubmit={async (values) => {
                  try {
                    await updateMeMutation.mutateAsync({
                      email: values.email.trim(),
                      full_name: values.full_name.trim() || null,
                    });
                    toast.success('Profile updated');
                  } catch (error) {
                    toast.error(
                      getApiErrorMessage(error, 'Failed to update profile'),
                    );
                  }
                }}
              />
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Change password</CardTitle>
            </CardHeader>
            <CardContent>
              <ChangePasswordForm
                isSubmitting={changePasswordMutation.isPending}
                onSubmit={async (values) => {
                  try {
                    await changePasswordMutation.mutateAsync(values);
                    toast.success('Password updated');
                  } catch (error) {
                    toast.error(
                      getApiErrorMessage(error, 'Failed to change password'),
                    );
                  }
                }}
              />
            </CardContent>
          </Card>
        </>
      ) : null}
    </div>
  );
}
