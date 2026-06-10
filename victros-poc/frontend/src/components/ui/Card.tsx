import type { HTMLAttributes } from 'react'

interface CardProps extends HTMLAttributes<HTMLDivElement> {
  selected?: boolean
  interactive?: boolean
}

export function Card({
  selected = false,
  interactive = false,
  className = '',
  children,
  ...props
}: CardProps) {
  return (
    <div
      className={[
        'rounded-xl border p-4 transition-colors duration-150',
        selected
          ? 'border-violet-500 bg-violet-950/40'
          : 'border-slate-700 bg-slate-900',
        interactive &&
          'cursor-pointer hover:border-violet-400 hover:bg-slate-800',
        className,
      ]
        .filter(Boolean)
        .join(' ')}
      {...props}
    >
      {children}
    </div>
  )
}
