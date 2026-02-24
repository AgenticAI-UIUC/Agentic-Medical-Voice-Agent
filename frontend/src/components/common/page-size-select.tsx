import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';

type PageSizeSelectProps = {
  value: number;
  onChange: (value: number) => void;
  options?: number[];
  label?: string;
  className?: string;
};

export function PageSizeSelect({
  value,
  onChange,
  options = [5, 10, 20],
  label = 'Rows:',
  className,
}: PageSizeSelectProps) {
  return (
    <div className="flex items-center gap-2 text-sm text-muted-foreground">
      <span>{label}</span>

      <Select value={String(value)} onValueChange={(v) => onChange(Number(v))}>
        <SelectTrigger className={className ?? 'h-8 w-[80px]'}>
          <SelectValue placeholder="Rows" />
        </SelectTrigger>
        <SelectContent>
          {options.map((option) => (
            <SelectItem key={option} value={String(option)}>
              {option}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}
