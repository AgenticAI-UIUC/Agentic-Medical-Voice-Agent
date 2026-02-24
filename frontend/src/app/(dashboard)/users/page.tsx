'use client';

import { useEffect, useMemo, useState } from 'react';

import { toast } from 'sonner';

import { UserForm } from '@/components/common/user-form';
import { Button } from '@/components/ui/button';
import { ApiError } from '@/lib/api/client';
import type { UserPublic } from '@/lib/api/users';
import {
  useCreateUserMutation,
  useDeleteUserMutation,
  useUpdateUserMutation,
  useUsersQuery,
} from '@/hooks/use-users';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/components/ui/alert-dialog';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { formatApiDetail } from '@/lib/api/errors';
import { PageHeader } from '@/components/common/page-header';
import { PaginationControls } from '@/components/common/pagination-controls';
import { usePaginationQueryParams } from '@/hooks/use-pagination-query-params';
import { EmptyState } from '@/components/common/empty-state';

export default function UsersPage() {
  const { page, pageSize, setPage, setPageSize } = usePaginationQueryParams();

  const skip = (page - 1) * pageSize;
  const usersQuery = useUsersQuery({ skip, limit: pageSize });

  const createMutation = useCreateUserMutation();
  const updateMutation = useUpdateUserMutation();
  const deleteMutation = useDeleteUserMutation();

  const [createOpen, setCreateOpen] = useState(false);
  const [editingUser, setEditingUser] = useState<UserPublic | null>(null);

  const users = usersQuery.data?.data ?? [];

  const combinedError =
    usersQuery.error ??
    createMutation.error ??
    updateMutation.error ??
    deleteMutation.error;

  const totalCount = usersQuery.data?.count ?? 0;
  const totalPages = Math.max(1, Math.ceil(totalCount / pageSize));
  useEffect(() => {
    if (totalPages > 0 && page > totalPages) {
      setPage(totalPages);
    }
  }, [page, totalPages, setPage]);

  const errorDetail = useMemo(() => {
    if (!combinedError) return null;

    if (combinedError instanceof ApiError) {
      if (
        typeof combinedError.body === 'object' &&
        combinedError.body !== null &&
        'detail' in combinedError.body
      ) {
        return formatApiDetail(
          (combinedError.body as { detail?: unknown }).detail,
        );
      }
      return combinedError.message;
    }

    return combinedError instanceof Error
      ? combinedError.message
      : 'Something went wrong';
  }, [combinedError]);

  const isForbidden =
    usersQuery.error instanceof ApiError && usersQuery.error.status === 403;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Users"
        description="Admin user management (superuser only)."
        action={
          <Dialog open={createOpen} onOpenChange={setCreateOpen}>
            <DialogTrigger asChild>
              <Button disabled={isForbidden}>Create user</Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Create user</DialogTitle>
                <DialogDescription>Add a new user account.</DialogDescription>
              </DialogHeader>

              <UserForm
                mode="create"
                submitLabel="Create user"
                isSubmitting={createMutation.isPending}
                onSubmit={async (values) => {
                  await createMutation.mutateAsync({
                    email: values.email.trim(),
                    full_name: values.full_name?.trim() || null,
                    password: values.password,
                    is_active: values.is_active,
                    is_superuser: values.is_superuser,
                  });
                  setPage(1);
                  toast.success('User created');
                  setCreateOpen(false);
                }}
              />
            </DialogContent>
          </Dialog>
        }
      />

      {isForbidden ? (
        <Card className="border-amber-200">
          <CardHeader>
            <CardTitle>Access denied</CardTitle>
            <CardDescription>
              This page is for admin users only.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-amber-700">
              Your backend returned 403 (forbidden) when requesting the users
              list.
            </p>
          </CardContent>
        </Card>
      ) : null}

      {errorDetail && !isForbidden ? (
        <Card className="border-red-200">
          <CardContent className="pt-6">
            <p className="text-sm text-red-600">{errorDetail}</p>
          </CardContent>
        </Card>
      ) : null}

      <Card>
        <CardHeader>
          <CardTitle>All users</CardTitle>
          <CardDescription>
            Total: {usersQuery.data?.count ?? 0}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {usersQuery.isPending ? (
            <p>Loading users...</p>
          ) : isForbidden ? (
            <p className="text-sm text-muted-foreground">
              Sign in as admin to manage users.
            </p>
          ) : usersQuery.isError ? (
            <p className="text-sm text-red-600">Failed to load users.</p>
          ) : users.length === 0 ? (
            <EmptyState
              title="No users found"
              description="Create a user to get started."
              action={
                <Button
                  disabled={isForbidden}
                  onClick={() => setCreateOpen(true)}
                >
                  Create user
                </Button>
              }
            />
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Email</TableHead>
                    <TableHead>Full name</TableHead>
                    <TableHead>Active</TableHead>
                    <TableHead>Admin</TableHead>
                    <TableHead>Created</TableHead>
                    <TableHead className="w-[180px] text-right">
                      Actions
                    </TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {users.map((user) => (
                    <TableRow key={user.id}>
                      <TableCell className="font-medium">
                        {user.email}
                      </TableCell>
                      <TableCell>{user.full_name ?? '-'}</TableCell>
                      <TableCell>{user.is_active ? 'Yes' : 'No'}</TableCell>
                      <TableCell>{user.is_superuser ? 'Yes' : 'No'}</TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        {new Date(user.created_at).toLocaleString()}
                      </TableCell>
                      <TableCell>
                        <div className="flex justify-end gap-2">
                          <Dialog
                            open={editingUser?.id === user.id}
                            onOpenChange={(open) => {
                              if (!open) setEditingUser(null);
                            }}
                          >
                            <DialogTrigger asChild>
                              <Button
                                variant="outline"
                                size="sm"
                                onClick={() => setEditingUser(user)}
                              >
                                Edit
                              </Button>
                            </DialogTrigger>
                            <DialogContent>
                              <DialogHeader>
                                <DialogTitle>Edit user</DialogTitle>
                                <DialogDescription>
                                  Update user fields and permissions.
                                </DialogDescription>
                              </DialogHeader>

                              <UserForm
                                mode="update"
                                submitLabel="Save changes"
                                isSubmitting={updateMutation.isPending}
                                defaultValues={{
                                  email: user.email,
                                  full_name: user.full_name ?? '',
                                  password: '',
                                  is_active: user.is_active,
                                  is_superuser: user.is_superuser,
                                }}
                                onSubmit={async (values) => {
                                  await updateMutation.mutateAsync({
                                    userId: user.id,
                                    input: {
                                      email: values.email.trim(),
                                      full_name:
                                        values.full_name?.trim() || null,
                                      is_active: values.is_active,
                                      is_superuser: values.is_superuser,
                                      ...(values.password
                                        ? { password: values.password }
                                        : {}),
                                    },
                                  });
                                  toast.success('User updated');
                                  setEditingUser(null);
                                }}
                              />
                            </DialogContent>
                          </Dialog>

                          <AlertDialog>
                            <AlertDialogTrigger asChild>
                              <Button
                                variant="destructive"
                                size="sm"
                                disabled={deleteMutation.isPending}
                              >
                                Delete
                              </Button>
                            </AlertDialogTrigger>
                            <AlertDialogContent>
                              <AlertDialogHeader>
                                <AlertDialogTitle>
                                  Delete user?
                                </AlertDialogTitle>
                                <AlertDialogDescription>
                                  This will permanently remove{' '}
                                  <span className="font-medium">
                                    {user.email}
                                  </span>
                                  .
                                </AlertDialogDescription>
                              </AlertDialogHeader>
                              <AlertDialogFooter>
                                <AlertDialogCancel>Cancel</AlertDialogCancel>
                                <AlertDialogAction
                                  onClick={async () => {
                                    await deleteMutation.mutateAsync(user.id);
                                    toast.success('User deleted');
                                  }}
                                >
                                  {deleteMutation.isPending
                                    ? 'Deleting...'
                                    : 'Delete'}
                                </AlertDialogAction>
                              </AlertDialogFooter>
                            </AlertDialogContent>
                          </AlertDialog>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
          {!usersQuery.isPending && !usersQuery.isError ? (
            <PaginationControls
              page={page}
              totalPages={totalPages}
              totalCount={totalCount}
              pageSize={pageSize}
              onPageChange={setPage}
              onPageSizeChange={setPageSize}
              isDisabled={usersQuery.isFetching}
            />
          ) : null}
        </CardContent>
      </Card>
    </div>
  );
}
