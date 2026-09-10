import React from "react";

export function Mono({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return (
    <span className={`text-[10px] font-mono tracking-[0.18em] uppercase text-muted-foreground ${className}`}>
      {children}
    </span>
  );
}

export function SectionBar({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex items-center gap-3 mb-7 animate-slide-left">
      <div className="w-px h-4 bg-foreground/35 animate-glow-pulse" />
      <Mono className="text-[11px]">{children}</Mono>
    </div>
  );
}

export function Btn({
  children,
  onClick,
  variant = "secondary",
  className = "",
  icon,
  full,
}: {
  children: React.ReactNode;
  onClick?: (e?: React.MouseEvent) => void;
  variant?: "primary" | "secondary" | "ghost" | "danger";
  className?: string;
  icon?: React.ReactNode;
  full?: boolean;
}) {
  const base = `h-8 px-4 rounded-lg text-[11px] font-mono tracking-[0.12em] uppercase flex items-center gap-2 press-scale cursor-pointer shrink-0 ${full ? "w-full justify-center" : ""}`;
  const vs = {
    primary:   "bg-foreground text-background border border-foreground hover:bg-foreground/85",
    secondary: "bg-background text-foreground border border-border hover:bg-accent",
    ghost:     "bg-transparent text-muted-foreground border border-transparent hover:border-border hover:text-foreground hover:bg-accent",
    danger:    "bg-background text-red-400 border border-red-900/50 hover:bg-red-950 hover:text-red-300",
  };
  return (
    <button onClick={onClick} className={`${base} ${vs[variant]} ${className}`}>
      {icon && <span className="shrink-0">{icon}</span>}
      {children}
    </button>
  );
}

export function FieldWrap({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1.5">
      <Mono>{label}</Mono>
      {hint && <p className="text-[10px] font-mono text-muted-foreground/60">{hint}</p>}
      {children}
    </div>
  );
}

export function TxtInput({
  type = "text",
  value,
  onChange,
  placeholder,
  right,
  dark,
}: {
  type?: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  right?: React.ReactNode;
  dark?: boolean;
}) {
  return (
    <div className={`flex items-center h-9 rounded-lg px-3 gap-2 transition-all duration-200 focus-within:shadow-[0_0_0_3px_rgba(255,255,255,0.06)] ${dark ? "bg-foreground/95" : "bg-background border border-border focus-within:border-foreground/30"}`}>
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className={`flex-1 bg-transparent text-[12px] font-mono focus:outline-none ${dark ? "text-background placeholder:text-background/35" : "text-foreground placeholder:text-muted-foreground/40"}`}
      />
      {right}
    </div>
  );
}

export function TxtArea({
  value,
  onChange,
  placeholder,
  rows = 4,
  maxLength,
}: {
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  rows?: number;
  maxLength?: number;
}) {
  return (
    <textarea
      value={value}
      onChange={(e) => onChange(e.target.value)}
      rows={rows}
      maxLength={maxLength}
      placeholder={placeholder}
      className="w-full bg-background border border-border rounded-lg px-3 py-2 text-[11px] font-mono text-foreground placeholder:text-muted-foreground/40 focus:outline-none focus:border-foreground/25 focus:shadow-[0_0_0_3px_rgba(255,255,255,0.06)] transition-all duration-200 resize-none"
    />
  );
}

export function TableHead({ cols }: { cols: string[] }) {
  return (
    <div className="grid px-5 py-3 bg-card border-b border-border" style={{ gridTemplateColumns: `repeat(${cols.length}, minmax(0, 1fr))` }}>
      {cols.map((h) => <Mono key={h}>{h}</Mono>)}
    </div>
  );
}

export function TableRow({ cells, cols, delay = 0 }: { cells: string[]; cols: number; delay?: number }) {
  return (
    <div
      className="grid px-5 py-3.5 border-b border-border last:border-0 hover:bg-accent/30 transition-colors animate-stagger"
      style={{ gridTemplateColumns: `repeat(${cols}, minmax(0, 1fr))`, animationDelay: `${delay}ms` }}
    >
      {cells.map((c, i) => (
        <span key={i} className={`text-[12px] font-mono ${i === 0 ? "text-foreground" : "text-muted-foreground"}`}>{c}</span>
      ))}
    </div>
  );
}
