import { Button } from '@/components/ui/button';
import { PageSizeSelect } from '@/components/common/page-size-select';

type PaginationControlsProps = {
  page: number;
  totalPages: number;
  totalCount: number;
  pageSize: number;
  onPageChange: (page: number) => void;
  onPageSizeChange: (pageSize: number) => void;
  isDisabled?: boolean;
  className?: string;
};

export function PaginationControls({
  page,
  totalPages,
  totalCount,
  pageSize,
  onPageChange,
  onPageSizeChange,
  isDisabled = false,
  className,
}: PaginationControlsProps) {
  const canGoPrev = page > 1 && !isDisabled;
  const canGoNext = page < totalPages && !isDisabled;

  return (
    <div
      className={
        className ??
        'mt-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between'
      }
    >
      <div className="flex items-center gap-3">
        <p className="text-sm text-muted-foreground">
          Page {page} of {totalPages} · {totalCount} total
        </p>

        <PageSizeSelect value={pageSize} onChange={onPageSizeChange} />
      </div>

      <div className="flex items-center gap-2">
        <Button
          variant="outline"
          size="sm"
          onClick={() => onPageChange(Math.max(1, page - 1))}
          disabled={!canGoPrev}
        >
          Previous
        </Button>
        <Button
          variant="outline"
          size="sm"
          onClick={() => onPageChange(page + 1)}
          disabled={!canGoNext}
        >
          Next
        </Button>
      </div>
    </div>
  );
}
