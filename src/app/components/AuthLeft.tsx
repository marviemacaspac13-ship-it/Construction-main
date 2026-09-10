import React, { useState } from "react";
import { FileText, Layers, Zap } from "lucide-react";
import { PixelLogo } from "./PixelLogo";

// ─── Auth input field used only on auth screens ───────────────────────────────
export function AuthInput({
  label,
  type = "text",
  value,
  onChange,
  placeholder,
  iconLeft,
  iconRight,
  onIconRight,
}: {
  label: string;
  type?: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  iconLeft: React.ReactNode;
  iconRight?: React.ReactNode;
  onIconRight?: () => void;
}) {
  const [focused, setFocused] = useState(false);
  return (
    <div>
      <p style={{ fontSize: "10px", fontFamily: "monospace", letterSpacing: "0.16em", textTransform: "uppercase", color: focused ? "#999" : "#666", marginBottom: "8px", transition: "color 0.2s ease" }}>
        {label}
      </p>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          height: "46px",
          background: "rgba(255,255,255,0.93)",
          borderRadius: "10px",
          padding: "0 14px",
          gap: "10px",
          transition: "box-shadow 0.22s ease, transform 0.22s ease",
          boxShadow: focused ? "0 0 0 3px rgba(255,255,255,0.14), 0 6px 20px -6px rgba(0,0,0,0.5)" : "0 0 0 0 rgba(255,255,255,0)",
          transform: focused ? "translateY(-1px)" : "translateY(0)",
        }}
      >
        <span style={{ flexShrink: 0, display: "flex", alignItems: "center" }}>{iconLeft}</span>
        <input
          type={type}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onFocus={() => setFocused(true)}
          onBlur={() => setFocused(false)}
          placeholder={placeholder}
          style={{ flex: 1, background: "transparent", border: "none", outline: "none", fontSize: "12px", fontFamily: "monospace", color: "#111" }}
        />
        {iconRight && (
          <button type="button" onClick={onIconRight} style={{ flexShrink: 0, background: "none", border: "none", cursor: "pointer", display: "flex", alignItems: "center", padding: 0, transition: "opacity 0.2s ease" }}>
            {iconRight}
          </button>
        )}
      </div>
    </div>
  );
}

// ─── Right panel subtle vertical grid lines ───────────────────────────────────
export function RightPanelGrid() {
  return (
    <div className="animate-fade-in" style={{ position: "absolute", inset: 0, pointerEvents: "none", display: "flex", justifyContent: "space-evenly" }}>
      {Array.from({ length: 5 }).map((_, i) => (
        <div key={i} style={{ width: "1px", height: "100%", background: "rgba(255,255,255,0.025)" }} />
      ))}
    </div>
  );
}

// ─── Shared 70% left panel for auth screens ───────────────────────────────────
export function AuthLeft() {
  const features = [
    { Icon: Zap,      title: "AI-Powered Analytics",              desc: "Detects and quantifies every element with high precision across all plan types." },
    { Icon: FileText, title: "Electrical Material Cost Estimation", desc: "Precise material breakdown with unit prices and total cost output per plan." },
    { Icon: Layers,   title: "Multi Plan Support",                 desc: "Floor, electrical, and plumbing plans — analyzed in one unified workflow." },
  ];

  return (
    <div className="relative overflow-hidden" style={{ width: "70%", minWidth: 0, display: "flex", flexDirection: "column", borderRight: "1px solid #2a2a2a" }}>
      <div style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", paddingLeft: "72px", paddingRight: "72px", paddingBottom: "48px" }}>
        <div className="animate-pop-in" style={{ textAlign: "center", marginBottom: "56px", width: "100%", display: "flex", flexDirection: "column", alignItems: "center" }}>
          <PixelLogo dotSize={11} gap={6} letterGap={24} />
          <p style={{ fontSize: "11px", letterSpacing: "0.38em", color: "#5a5a5a", fontFamily: "monospace", textTransform: "uppercase", marginTop: "20px" }}>
            Upload · Scan · Analyze · Estimate
          </p>
        </div>
        <div style={{ width: "100%", maxWidth: "460px", display: "flex", flexDirection: "column", gap: "36px" }}>
          {features.map(({ Icon, title, desc }, i) => (
            <div
              key={title}
              className="hover-lift animate-slide-left"
              style={{ display: "flex", gap: "20px", alignItems: "flex-start", animationDelay: `${180 + i * 110}ms`, borderRadius: "14px", padding: "6px" }}
            >
              <div className="hover-lift" style={{ width: "56px", height: "56px", border: "1px solid #2a2a2a", borderRadius: "14px", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0, background: "rgba(255,255,255,0.03)" }}>
                <Icon size={24} strokeWidth={1.3} color="#888" />
              </div>
              <div style={{ paddingTop: "3px" }}>
                <p style={{ fontSize: "18px", fontWeight: 600, color: "#ffffff", marginBottom: "8px", lineHeight: 1.3, letterSpacing: "-0.01em", fontFamily: "'Inter','Sora',sans-serif" }}>{title}</p>
                <p style={{ fontSize: "14px", color: "#606060", lineHeight: 1.7, fontFamily: "'Inter','Sora',sans-serif" }}>{desc}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}