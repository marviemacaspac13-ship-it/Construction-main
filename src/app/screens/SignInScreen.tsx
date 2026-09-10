import { useState } from "react";
import { Eye, EyeOff } from "lucide-react";
import { AuthLeft, AuthInput, RightPanelGrid } from "../components/AuthLeft";
import { DotWave } from "../components/DotWave";
import { useNavigate } from "react-router";
import { supabase } from "../../lib/supabase";

export function SignInScreen() {
  const navigate = useNavigate();
  const [email, setEmail]       = useState("");
  const [password, setPassword] = useState("");
  const [showPw, setShowPw]     = useState(false);
  const [loading, setLoading]   = useState(false);
  const [error, setError]       = useState("");

  async function handleLogIn() {
    setError("");

    if (!email || !password) {
      setError("Please enter your email and password.");
      return;
    }

    setLoading(true);
    const { data, error: signInError } = await supabase.auth.signInWithPassword({
      email,
      password,
    });
    setLoading(false);

    if (signInError) {
      // Supabase returns "Invalid login credentials" for both
      // "no such account" and "wrong password" (this is intentional,
      // so attackers can't tell which one is wrong).
      setError("Invalid email or password. Please sign up first if you don't have an account.");
      return;
    }

    if (data.session) {
      navigate("/dashboard");
    }
  }

  return (
    <div style={{ height: "100vh", background: "#000000", display: "flex", overflow: "hidden", fontFamily: "'Inter','Sora',sans-serif", position: "relative" }}>
      {/* Particle wave background — spans the full viewport width, behind both panels */}
      <div className="animate-fade-in" style={{ position: "absolute", left: 0, right: 0, bottom: 0, height: "280px", zIndex: 0, pointerEvents: "none", animationDuration: "1.1s" }}>
        <DotWave />
      </div>

      <AuthLeft />

      <div className="animate-slide-right" style={{ width: "30%", minWidth: 0, display: "flex", flexDirection: "column", position: "relative", borderLeft: "1px solid #2a2a2a", background: "rgba(0,0,0,0.55)" }}>
        <RightPanelGrid />

        {/* Tab bar */}
        <div style={{ display: "flex", alignItems: "center", justifyContent: "flex-end", gap: "32px", height: "64px", padding: "0 48px", borderBottom: "1px solid #1e1e1e", position: "relative", zIndex: 1, flexShrink: 0 }}>
          <div style={{ position: "relative", display: "flex", flexDirection: "column", alignItems: "center", gap: "6px" }}>
            <button style={{ background: "none", border: "none", cursor: "default", fontSize: "12px", letterSpacing: "0.07em", color: "#ffffff", fontFamily: "'Inter','Sora',sans-serif", padding: 0 }}>
              Sign in
            </button>
            <div className="animate-scale-in" style={{ width: "100%", height: "1px", background: "#ffffff", transformOrigin: "center" }} />
          </div>
          <button
            onClick={() => navigate("/sign-up")}
            className="underline-grow"
            style={{ background: "none", border: "none", cursor: "pointer", fontSize: "12px", letterSpacing: "0.07em", color: "#555", fontFamily: "'Inter','Sora',sans-serif", padding: 0, transition: "color 0.2s ease" }}
            onMouseEnter={(e) => (e.currentTarget.style.color = "#aaa")}
            onMouseLeave={(e) => (e.currentTarget.style.color = "#555")}
          >
            Sign up
          </button>
        </div>

        {/* Form */}
        <div className="animate-slide-right" style={{ flex: 1, display: "flex", flexDirection: "column", justifyContent: "center", padding: "0 48px 48px", position: "relative", zIndex: 1, animationDelay: "90ms" }}>
          <div style={{ marginBottom: "32px" }}>
            <h2 style={{ fontSize: "26px", fontWeight: 600, color: "#ffffff", margin: 0, lineHeight: 1.2, letterSpacing: "-0.02em" }}>Welcome back</h2>
            <p style={{ fontSize: "12px", color: "#555", marginTop: "8px", letterSpacing: "0.02em" }}>Log in to your account to continue</p>
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
            <AuthInput
              label="Email" type="email" value={email} onChange={setEmail} placeholder="you@example.com"
              iconLeft={<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#333" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><rect x="2" y="4" width="20" height="16" rx="2" /><polyline points="2,4 12,13 22,4" /></svg>}
            />
            <div>
              <AuthInput
                label="Password" type={showPw ? "text" : "password"} value={password} onChange={setPassword} placeholder="••••••••"
                iconLeft={<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#333" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><rect x="5" y="11" width="14" height="10" rx="2" /><path d="M8 11V7a4 4 0 0 1 8 0v4" /></svg>}
                iconRight={showPw ? <EyeOff size={14} color="#555" /> : <Eye size={14} color="#555" />}
                onIconRight={() => setShowPw((v) => !v)}
              />
              <div style={{ display: "flex", justifyContent: "flex-end", marginTop: "8px" }}>
                <button style={{ background: "none", border: "none", cursor: "pointer", fontSize: "10px", fontFamily: "monospace", color: "#555", letterSpacing: "0.05em", padding: 0 }}>
                  Forgot Password?
                </button>
              </div>
            </div>
          </div>

          <button
            onClick={handleLogIn}
            disabled={loading}
            className={`press-scale ${loading ? "shimmer-surface" : ""}`}
            style={{ width: "100%", height: "46px", marginTop: "24px", background: loading ? "rgba(255,255,255,0.5)" : "rgba(255,255,255,0.92)", color: "#000", border: "none", borderRadius: "10px", fontSize: "11px", fontFamily: "monospace", letterSpacing: "0.22em", textTransform: "uppercase", cursor: loading ? "default" : "pointer", fontWeight: 500 }}
          >
            {loading ? "Logging in..." : "Log In"}
          </button>

          {error && (
            <p className="animate-pop-in" style={{ fontSize: "11px", color: "#ff6b6b", textAlign: "center", marginTop: "14px" }}>{error}</p>
          )}

          <p className="animate-fade-in" style={{ fontSize: "11px", color: "#555", textAlign: "center", marginTop: "24px", animationDelay: "300ms" }}>
            {"Don't have an account? "}
            <button onClick={() => navigate("/sign-up")} style={{ background: "none", border: "none", cursor: "pointer", fontSize: "11px", color: "#fff", textDecoration: "underline", textUnderlineOffset: "3px", padding: 0, fontFamily: "'Inter','Sora',sans-serif" }}>
              Sign up
            </button>
          </p>
        </div>
      </div>
    </div>
  );
}