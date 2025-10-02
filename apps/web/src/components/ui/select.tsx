import * as React from 'react';
import { cn } from '@/lib/utils';

interface SelectContextValue {
  value: string;
  onValueChange: (value: string) => void;
  open: boolean;
  setOpen: (open: boolean) => void;
}

const SelectContext = React.createContext<SelectContextValue | undefined>(undefined);

interface SelectProps {
  value: string;
  onValueChange: (value: string) => void;
  children: React.ReactNode;
}

const Select = ({ value, onValueChange, children }: SelectProps) => {
  const [open, setOpen] = React.useState(false);

  return (
    <SelectContext.Provider value={{ value, onValueChange, open, setOpen }}>
      <div className="relative">
        {children}
      </div>
    </SelectContext.Provider>
  );
};

const SelectTrigger = React.forwardRef<
  HTMLButtonElement,
  React.ButtonHTMLAttributes<HTMLButtonElement>
>(({ className, children, ...props }, ref) => {
  const context = React.useContext(SelectContext);
  if (!context) throw new Error('SelectTrigger must be used within Select');

  return (
    <button
      ref={ref}
      className={cn(
        'flex h-10 w-full items-center justify-between rounded-md border border-gray-300 bg-white px-3 py-2 text-sm placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50',
        className
      )}
      onClick={() => context.setOpen(!context.open)}
      type="button"
      {...props}
    >
      {children}
      <svg
        className="h-4 w-4 opacity-50"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        viewBox="0 0 24 24"
      >
        <path d="M6 9l6 6 6-6" />
      </svg>
    </button>
  );
});
SelectTrigger.displayName = 'SelectTrigger';

const SelectValue = () => {
  const context = React.useContext(SelectContext);
  if (!context) throw new Error('SelectValue must be used within Select');

  return <span>{context.value}</span>;
};

const SelectContent = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, children, ...props }, ref) => {
  const context = React.useContext(SelectContext);
  if (!context) throw new Error('SelectContent must be used within Select');

  if (!context.open) return null;

  return (
    <div
      ref={ref}
      className={cn(
        'absolute z-50 mt-1 w-full rounded-md border border-gray-300 bg-white py-1 shadow-lg',
        className
      )}
      {...props}
    >
      {children}
    </div>
  );
});
SelectContent.displayName = 'SelectContent';

interface SelectItemProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  value: string;
}

const SelectItem = React.forwardRef<HTMLButtonElement, SelectItemProps>(
  ({ className, value, children, ...props }, ref) => {
    const context = React.useContext(SelectContext);
    if (!context) throw new Error('SelectItem must be used within Select');

    const isSelected = context.value === value;

    return (
      <button
        ref={ref}
        className={cn(
          'relative w-full cursor-pointer select-none px-3 py-2 text-left text-sm hover:bg-gray-100 focus:bg-gray-100 focus:outline-none',
          isSelected && 'bg-gray-50 font-medium',
          className
        )}
        onClick={() => {
          context.onValueChange(value);
          context.setOpen(false);
        }}
        type="button"
        {...props}
      >
        {children}
      </button>
    );
  }
);
SelectItem.displayName = 'SelectItem';

export { Select, SelectTrigger, SelectValue, SelectContent, SelectItem };