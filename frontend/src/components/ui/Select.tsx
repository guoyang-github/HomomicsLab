import { clsx } from 'clsx'
import {
  Select as ShadcnSelect,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from './shadcn/select'

// Radix Select reserves the empty string for "no selection", so legacy
// options with value "" are mapped to an internal sentinel.
const EMPTY_VALUE = '__homomics_select_empty__'

export interface SelectProps {
  error?: string
  options: Array<{ value: string; label: string; disabled?: boolean }>
  value?: string
  defaultValue?: string
  onChange?: (e: React.ChangeEvent<HTMLSelectElement>) => void
  disabled?: boolean
  name?: string
  required?: boolean
  id?: string
  placeholder?: string
  className?: string
  children?: React.ReactNode
  'aria-label'?: string
}

// Adapter: legacy native-select API (options prop + onChange event) on top of
// the shadcn (radix) Select so existing call sites stay unchanged.
export function Select({
  className,
  error,
  options,
  children,
  value,
  defaultValue,
  onChange,
  disabled,
  name,
  required,
  id,
  placeholder,
  'aria-label': ariaLabel,
}: SelectProps) {
  const toInternal = (v: string) => (v === '' ? EMPTY_VALUE : v)
  const toExternal = (v: string) => (v === EMPTY_VALUE ? '' : v)

  return (
    <div className="w-full">
      <ShadcnSelect
        value={value !== undefined ? toInternal(value) : undefined}
        defaultValue={defaultValue !== undefined ? toInternal(defaultValue) : undefined}
        onValueChange={(next) => {
          onChange?.({
            target: { value: toExternal(next), name: name ?? '' },
          } as React.ChangeEvent<HTMLSelectElement>)
        }}
        disabled={disabled}
        name={name}
        required={required}
      >
        <SelectTrigger
          id={id}
          aria-label={ariaLabel}
          className={clsx('h-10 bg-card', error && 'border-error focus:ring-error', className)}
        >
          <SelectValue placeholder={placeholder} />
        </SelectTrigger>
        <SelectContent>
          {children}
          {options.map((option) => (
            <SelectItem
              key={option.value === '' ? EMPTY_VALUE : option.value}
              value={toInternal(option.value)}
              disabled={option.disabled}
            >
              {option.label}
            </SelectItem>
          ))}
        </SelectContent>
      </ShadcnSelect>
      {error && <p className="mt-1 text-xs text-error">{error}</p>}
    </div>
  )
}
