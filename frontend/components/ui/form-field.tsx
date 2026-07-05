import type { InputHTMLAttributes, ReactNode, SelectHTMLAttributes, TextareaHTMLAttributes } from "react";

const formInputClassName =
  "w-full rounded-lg border border-zinc-200 bg-white px-3.5 py-2.5 text-sm text-zinc-900 shadow-sm transition-colors placeholder:text-zinc-400 focus:border-cdtm focus:outline-none focus:ring-2 focus:ring-cdtm/20 disabled:cursor-not-allowed disabled:bg-zinc-50 disabled:text-zinc-500";

type FieldProps = {
  id: string;
  label: string;
  hint?: string;
  optional?: boolean;
  children: ReactNode;
};

export function FormField({ id, label, hint, optional, children }: FieldProps) {
  return (
    <div>
      <label htmlFor={id} className="text-ui-title mb-1.5 block">
        {label}
        {optional && (
          <span className="ml-1.5 text-xs font-normal text-zinc-400">Optional</span>
        )}
      </label>
      {children}
      {hint && (
        <p id={`${id}-hint`} className="mt-1.5 text-xs leading-relaxed text-zinc-500">
          {hint}
        </p>
      )}
    </div>
  );
}

type TextInputProps = InputHTMLAttributes<HTMLInputElement> & {
  id: string;
};

export function FormTextInput({ className = "", ...props }: TextInputProps) {
  return <input className={`${formInputClassName} ${className}`} {...props} />;
}

type TextAreaProps = TextareaHTMLAttributes<HTMLTextAreaElement> & {
  id: string;
};

export function FormTextArea({ className = "", ...props }: TextAreaProps) {
  return <textarea className={`${formInputClassName} ${className}`} {...props} />;
}

type SelectProps = SelectHTMLAttributes<HTMLSelectElement> & {
  id: string;
};

export function FormSelect({ className = "", children, ...props }: SelectProps) {
  return (
    <select className={`${formInputClassName} ${className}`} {...props}>
      {children}
    </select>
  );
}

type CheckboxFieldProps = {
  id: string;
  name: string;
  label: string;
  hint?: string;
  disabled?: boolean;
};

export function FormCheckboxField({ id, name, label, hint, disabled }: CheckboxFieldProps) {
  return (
    <div className="flex items-start gap-3 rounded-lg border border-zinc-200 bg-zinc-50/60 px-3.5 py-3">
      <input
        id={id}
        name={name}
        type="checkbox"
        disabled={disabled}
        className="mt-0.5 size-4 rounded border-zinc-300 text-cdtm focus:ring-cdtm/20 disabled:opacity-50"
      />
      <div>
        <label htmlFor={id} className="text-sm font-medium text-zinc-800">
          {label}
        </label>
        {hint && <p className="mt-0.5 text-xs text-zinc-500">{hint}</p>}
      </div>
    </div>
  );
}
