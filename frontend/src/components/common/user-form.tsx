'use client';

import { zodResolver } from '@hookform/resolvers/zod';
import { useEffect } from 'react';
import { useForm } from 'react-hook-form';
import { z } from 'zod';

import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form';
import { Input } from '@/components/ui/input';

export const createUserSchema = z.object({
  email: z.email('Please enter a valid email'),
  full_name: z.string().max(255).optional().or(z.literal('')),
  password: z.string().min(8, 'Password must be at least 8 characters'),
  is_active: z.boolean(),
  is_superuser: z.boolean(),
});

export const updateUserSchema = z.object({
  email: z.email('Please enter a valid email'),
  full_name: z.string().max(255).optional().or(z.literal('')),
  password: z
    .string()
    .min(8, 'Password must be at least 8 characters')
    .optional()
    .or(z.literal('')),
  is_active: z.boolean(),
  is_superuser: z.boolean(),
});

export type CreateUserFormValues = z.infer<typeof createUserSchema>;
export type UpdateUserFormValues = z.infer<typeof updateUserSchema>;

type BaseProps<T> = {
  defaultValues?: Partial<T>;
  submitLabel: string;
  isSubmitting?: boolean;
  onSubmit: (values: T) => Promise<void> | void;
};

type CreateProps = BaseProps<CreateUserFormValues> & {
  mode: 'create';
};

type UpdateProps = BaseProps<UpdateUserFormValues> & {
  mode: 'update';
};

type Props = CreateProps | UpdateProps;

export function UserForm(props: Props) {
  const schema = props.mode === 'create' ? createUserSchema : updateUserSchema;

  const form = useForm<CreateUserFormValues | UpdateUserFormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      email: props.defaultValues?.email ?? '',
      full_name: props.defaultValues?.full_name ?? '',
      password: props.defaultValues?.password ?? '',
      is_active: props.defaultValues?.is_active ?? true,
      is_superuser: props.defaultValues?.is_superuser ?? false,
    },
  });

  useEffect(() => {
    form.reset({
      email: props.defaultValues?.email ?? '',
      full_name: props.defaultValues?.full_name ?? '',
      password: props.defaultValues?.password ?? '',
      is_active: props.defaultValues?.is_active ?? true,
      is_superuser: props.defaultValues?.is_superuser ?? false,
    });
  }, [props.defaultValues, form]);

  return (
    <Form {...form}>
      <form
        className="space-y-4"
        onSubmit={form.handleSubmit(async (values) => {
          await props.onSubmit(values as never);
        })}
      >
        <FormField
          control={form.control}
          name="email"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Email</FormLabel>
              <FormControl>
                <Input type="email" placeholder="user@example.com" {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        <FormField
          control={form.control}
          name="full_name"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Full name</FormLabel>
              <FormControl>
                <Input
                  placeholder="Jane Doe"
                  {...field}
                  value={field.value ?? ''}
                />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        <FormField
          control={form.control}
          name="password"
          render={({ field }) => (
            <FormItem>
              <FormLabel>
                {props.mode === 'create' ? 'Password' : 'Password (optional)'}
              </FormLabel>
              <FormControl>
                <Input
                  type="password"
                  placeholder={
                    props.mode === 'create'
                      ? 'password123'
                      : 'Leave blank to keep current'
                  }
                  {...field}
                  value={field.value ?? ''}
                />
              </FormControl>
              {props.mode === 'update' && (
                <FormDescription>
                  Leave blank if you don’t want to change the password.
                </FormDescription>
              )}
              <FormMessage />
            </FormItem>
          )}
        />

        <FormField
          control={form.control}
          name="is_active"
          render={({ field }) => (
            <FormItem className="flex flex-row items-center justify-between rounded-md border p-3">
              <div className="space-y-0.5">
                <FormLabel>Active user</FormLabel>
                <FormDescription>
                  User can sign in and use the app.
                </FormDescription>
              </div>
              <FormControl>
                <Checkbox
                  checked={field.value}
                  onCheckedChange={(v) => field.onChange(Boolean(v))}
                />
              </FormControl>
            </FormItem>
          )}
        />

        <FormField
          control={form.control}
          name="is_superuser"
          render={({ field }) => (
            <FormItem className="flex flex-row items-center justify-between rounded-md border p-3">
              <div className="space-y-0.5">
                <FormLabel>Admin (superuser)</FormLabel>
                <FormDescription>
                  Can manage all users.
                </FormDescription>
              </div>
              <FormControl>
                <Checkbox
                  checked={field.value}
                  onCheckedChange={(v) => field.onChange(Boolean(v))}
                />
              </FormControl>
            </FormItem>
          )}
        />

        <Button type="submit" className="w-full" disabled={props.isSubmitting}>
          {props.isSubmitting ? 'Saving...' : props.submitLabel}
        </Button>
      </form>
    </Form>
  );
}
