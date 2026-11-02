import React, { useState } from "react";
import { useNavigate } from "react-router";
import { PixelLogo } from "./PixelLogo";
import { PlanScene, type LayerKey, type LayerState } from "./PlanScene";

// ─── Tokens ───────────────────────────────────────────────────────────────────
const C = {
  bg: "#000000",
  line: "#1a222e",
  fieldBorder: "#263040",
  text: "#f2f6fc",
  muted: "#8793a6",
  faint: "#5d6878",
  floor: "#dfe8f5",
  electrical: "#2fe3c0",
  plumbing: "#2f7bff",
  focus: "#5ea2ff",
  error: "#ff8a8a",
};
const BODY = "'Inter','Sora',sans-serif";
const DISPLAY = "'Sora','Inter',sans-serif";

// ─── Page-level CSS (media queries and pseudo-classes can't live in inline styles) ──
const AUTH_CSS = `
  .arce-auth { height: 100vh; display: flex; background: ${C.bg}; overflow: hidden; font-family: ${BODY}; color: ${C.text}; }
  .arce-hero { position: relative; flex: 1 1 auto; min-width: 0; overflow: hidden; border-right: 1px solid ${C.line}; }
  .arce-side { flex: 0 0 clamp(380px, 30%, 520px); display: flex; flex-direction: column; background: ${C.bg}; position: relative; }
  .arce-input::placeholder { color: ${C.faint}; }
  .arce-input:-webkit-autofill { -webkit-text-fill-color: ${C.text}; box-shadow: 0 0 0 40px #0b1018 inset; }
  .arce-layer { display: flex; align-items: flex-start; gap: 12px; text-align: left; cursor: pointer; font-family: ${BODY};
    background: rgba(0,0,0,0.55); border: 1px solid ${C.line}; border-radius: 10px; padding: 10px 14px; min-width: 0;
    transition: border-color .2s ease, background .2s ease, opacity .2s ease; color: ${C.text}; }
  .arce-layer:hover { border-color: #33415a; background: rgba(12,18,28,0.8); }
  .arce-layer[aria-pressed="false"] { opacity: .55; }
  .arce-layer:focus-visible, .arce-primary:focus-visible, .arce-link:focus-visible, .arce-tab:focus-visible {
    outline: 2px solid ${C.focus}; outline-offset: 3px; }
  .arce-primary { transition: background .2s ease, transform .1s ease, opacity .2s ease; }
  .arce-primary:hover:not(:disabled) { background: #ffffff; }
  .arce-primary:active:not(:disabled) { transform: scale(0.985); }
  .arce-link:hover { color: ${C.text}; }
  .arce-tab { transition: color .2s ease; }
  .arce-tab:hover { color: ${C.text}; }

  @media (max-width: 900px) {
    .arce-auth { height: auto; min-height: 100vh; flex-direction: column; overflow: visible; }
    .arce-hero { flex: none; height: 62vh; min-height: 400px; border-right: none; border-bottom: 1px solid ${C.line}; }
    .arce-side { flex: none; width: 100%; }
    .arce-copy-extra, .arce-layer-desc, .arce-hint { display: none; }
    .arce-headline { font-size: 22px !important; }
    .arce-layers { gap: 8px !important; }
    .arce-layer { padding: 8px 10px; }
  }
`;

// ─── Auth input ───────────────────────────────────────────────────────────────
export function AuthInput({
  label,
  type = "text",
  value,
  onChange,
  placeholder,
  iconLeft,
  iconRight,
  onIconRight,
  iconRightLabel,
  autoComplete,
  name,
}: {
  label: string;
  type?: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  iconLeft: React.ReactNode;
  iconRight?: React.ReactNode;
  onIconRight?: () => void;
  iconRightLabel?: string;
  autoComplete?: string;
  name?: string;
}) {
  const [focused, setFocused] = useState(false);
  const id = React.useId();
  return (
    <div>
      <label
        htmlFor={id}
        style={{ display: "block", fontSize: "12px", fontWeight: 500, color: focused ? "#c9d4e5" : C.muted, marginBottom: "8px", transition: "color 0.2s ease" }}
      >
        {label}
      </label>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          height: "46px",
          background: "rgba(255,255,255,0.04)",
          border: `1px solid ${focused ? C.focus : C.fieldBorder}`,
          borderRadius: "8px",
          padding: "0 14px",
          gap: "10px",
          transition: "border-color 0.2s ease, box-shadow 0.2s ease",
          boxShadow: focused ? "0 0 0 3px rgba(94,162,255,0.18)" : "0 0 0 0 rgba(94,162,255,0)",
        }}
      >
        <span style={{ flexShrink: 0, display: "flex", alignItems: "center" }}>{iconLeft}</span>
        <input
          id={id}
          name={name}
          className="arce-input"
          type={type}
          value={value}
          autoComplete={autoComplete}
          onChange={(e) => onChange(e.target.value)}
          onFocus={() => setFocused(true)}
          onBlur={() => setFocused(false)}
          placeholder={placeholder}
          style={{ flex: 1, minWidth: 0, background: "transparent", border: "none", outline: "none", fontSize: "14px", fontFamily: BODY, color: C.text }}
        />
        {iconRight && (
          <button
            type="button"
            onClick={onIconRight}
            aria-label={iconRightLabel}
            style={{ flexShrink: 0, background: "none", border: "none", cursor: "pointer", display: "flex", alignItems: "center", padding: 0 }}
          >
            {iconRight}
          </button>
        )}
      </div>
    </div>
  );
}

// ─── Hero panel: logo, one-line pitch, the 3D building and its layer toggles ───
const LAYER_INFO: { key: LayerKey; title: string; desc: string; color: string }[] = [
  { key: "floor", title: "Floor plan", desc: "Walls, rooms and dimensions", color: C.floor },
  { key: "electrical", title: "Electrical plan", desc: "Lights, outlets and switches", color: C.electrical },
  { key: "plumbing", title: "Plumbing plan", desc: "Fixtures and pipe runs", color: C.plumbing },
];

export function AuthLeft() {
  const [layers, setLayers] = useState<LayerState>({ floor: true, electrical: true, plumbing: true });
  const [focus, setFocus] = useState<LayerKey | null>(null);

  return (
    <section className="arce-hero" aria-label="ARCE overview">
      <PlanScene layers={layers} focus={focus} />

      {/* Top-left: wordmark and pitch. Pointer events pass through so the scene stays draggable. */}
      <div style={{ position: "absolute", top: 0, left: 0, padding: "clamp(24px, 4vw, 56px)", pointerEvents: "none", maxWidth: "min(520px, 100%)" }}>
        <PixelLogo dotSize={7} gap={3.5} letterGap={16} round />
        <h1
          className="arce-headline"
          style={{ fontFamily: DISPLAY, fontSize: "34px", fontWeight: 600, lineHeight: 1.15, letterSpacing: "-0.02em", margin: "28px 0 0", color: C.text }}
        >
          Turn your plans into material costs
        </h1>
        <p className="arce-copy-extra" style={{ fontSize: "15px", lineHeight: 1.65, color: C.muted, margin: "14px 0 0", maxWidth: "400px" }}>
          Upload a floor, electrical or plumbing plan. ARCE reads it and prices every material in pesos.
        </p>
      </div>

      {/* Bottom: layer toggles */}
      <div
        className="arce-layers"
        role="group"
        aria-label="Show or hide plan layers"
        style={{ position: "absolute", left: 0, right: 0, bottom: 0, padding: "clamp(20px, 3vw, 40px) clamp(24px, 4vw, 56px)", display: "flex", gap: "12px", flexWrap: "wrap" }}
      >
        {LAYER_INFO.map(({ key, title, desc, color }) => {
          const on = layers[key];
          return (
            <button
              key={key}
              type="button"
              className="arce-layer"
              aria-pressed={on}
              onClick={() => setLayers((s) => ({ ...s, [key]: !s[key] }))}
              onMouseEnter={() => setFocus(key)}
              onMouseLeave={() => setFocus(null)}
              onFocus={() => setFocus(key)}
              onBlur={() => setFocus(null)}
              style={{ flex: "0 1 210px" }}
            >
              <span
                aria-hidden="true"
                style={{
                  width: "20px", height: "3px", borderRadius: "2px", marginTop: "8px", flexShrink: 0,
                  background: on ? color : "transparent",
                  boxShadow: on ? `0 0 10px ${color}` : "none",
                  border: on ? "none" : `1px solid ${color}`,
                  transition: "background .2s ease, box-shadow .2s ease",
                }}
              />
              <span style={{ minWidth: 0 }}>
                <span style={{ display: "block", fontSize: "14px", fontWeight: 600, lineHeight: 1.3 }}>{title}</span>
                <span className="arce-layer-desc" style={{ display: "block", fontSize: "12px", color: C.muted, marginTop: "2px", lineHeight: 1.4 }}>{desc}</span>
              </span>
            </button>
          );
        })}
      </div>

      <p className="arce-hint" style={{ position: "absolute", right: "clamp(24px, 4vw, 56px)", top: "clamp(24px, 4vw, 56px)", margin: 0, fontSize: "12px", color: C.faint, pointerEvents: "none" }}>
        Drag to rotate
      </p>
    </section>
  );
}

// ─── Shared layout for sign in and sign up ────────────────────────────────────
export function AuthLayout({ active, children }: { active: "sign-in" | "sign-up"; children: React.ReactNode }) {
  const navigate = useNavigate();

  const tab = (id: "sign-in" | "sign-up", text: string) => {
    const isActive = active === id;
    return (
      <button
        type="button"
        className="arce-tab"
        aria-current={isActive ? "page" : undefined}
        onClick={isActive ? undefined : () => navigate(`/${id}`)}
        style={{
          background: "none", border: "none", padding: "0 2px", height: "100%", marginBottom: "-1px", fontSize: "13px", fontFamily: BODY,
          cursor: isActive ? "default" : "pointer", color: isActive ? C.text : C.faint,
          borderBottom: `1px solid ${isActive ? C.text : "transparent"}`,
        }}
      >
        {text}
      </button>
    );
  };

  return (
    <div className="arce-auth">
      <style>{AUTH_CSS}</style>
      <AuthLeft />
      <main className="arce-side animate-fade-in">
        <nav aria-label="Account" style={{ display: "flex", alignItems: "stretch", justifyContent: "flex-end", gap: "28px", height: "60px", padding: "0 48px", borderBottom: `1px solid ${C.line}`, flexShrink: 0 }}>
          {tab("sign-in", "Sign in")}
          {tab("sign-up", "Sign up")}
        </nav>
        <div style={{ flex: 1, display: "flex", flexDirection: "column", justifyContent: "center", padding: "40px 48px 56px" }}>{children}</div>
      </main>
    </div>
  );
}

// ─── Small pieces the screens share ───────────────────────────────────────────
export const authColors = C;
export const authFonts = { body: BODY, display: DISPLAY };
