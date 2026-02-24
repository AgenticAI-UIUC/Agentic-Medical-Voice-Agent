'use client';

import { useCallback } from 'react';
import { usePathname, useRouter, useSearchParams } from 'next/navigation';

const DEFAULT_PAGE = 1;
const DEFAULT_PAGE_SIZE = 5;
const ALLOWED_PAGE_SIZES = new Set([5, 10, 20]);

function parsePositiveInt(value: string | null, fallback: number): number {
  if (!value) return fallback;
  const parsed = Number(value);
  if (!Number.isInteger(parsed) || parsed <= 0) return fallback;
  return parsed;
}

export function usePaginationQueryParams() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const rawPage = searchParams.get('page');
  const rawPageSize = searchParams.get('pageSize');

  const page = parsePositiveInt(rawPage, DEFAULT_PAGE);

  const parsedPageSize = parsePositiveInt(rawPageSize, DEFAULT_PAGE_SIZE);
  const pageSize = ALLOWED_PAGE_SIZES.has(parsedPageSize)
    ? parsedPageSize
    : DEFAULT_PAGE_SIZE;

  const updateParams = useCallback(
    (next: { page?: number; pageSize?: number }) => {
      const params = new URLSearchParams(searchParams.toString());

      const nextPage = next.page ?? page;
      const nextPageSize = next.pageSize ?? pageSize;

      // Keep URL clean by omitting defaults
      if (nextPage <= DEFAULT_PAGE) {
        params.delete('page');
      } else {
        params.set('page', String(nextPage));
      }

      if (nextPageSize === DEFAULT_PAGE_SIZE) {
        params.delete('pageSize');
      } else {
        params.set('pageSize', String(nextPageSize));
      }

      const query = params.toString();
      router.replace(query ? `${pathname}?${query}` : pathname, {
        scroll: false,
      });
    },
    [router, pathname, searchParams, page, pageSize],
  );

  const setPage = useCallback(
    (nextPage: number) => {
      updateParams({ page: Math.max(1, nextPage) });
    },
    [updateParams],
  );

  const setPageSize = useCallback(
    (nextPageSize: number) => {
      const safePageSize = ALLOWED_PAGE_SIZES.has(nextPageSize)
        ? nextPageSize
        : DEFAULT_PAGE_SIZE;

      // Reset to page 1 when page size changes
      updateParams({ page: 1, pageSize: safePageSize });
    },
    [updateParams],
  );

  return {
    page,
    pageSize,
    setPage,
    setPageSize,
  };
}
