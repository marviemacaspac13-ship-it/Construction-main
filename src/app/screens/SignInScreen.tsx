import { useState } from "react";
import { Eye, EyeOff } from "lucide-react";
import { useNavigate } from "react-router";
import { AuthInput, AuthLayout, authColors as C, authFonts } from "../components/AuthLeft";
import { supabase } from "../../lib/supabase";

const iconStyle = { stroke: "#6b7789", strokeWidth: 1.8, strokeLinecap: "round", strokeLinejoin: "round", fill: "none" } as const;

export function SignInScreen() {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPw, setShowPw] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleSignIn() {
    setError("");

    if (!email || !password) {
      setError("Enter your email and password.");
      return;
    }

    setLoading(true);
    const { data, error: signInError } = await supabase.auth.signInWithPassword({ email, password });
    setLoading(false);

    if (signInError) {
      // Supabase returns the same message for "no such account" and "wrong password"
      // on purpose, so we can't tell the person which one it was.
      setError("Email or password is incorrect. If you're new to ARCE, create an account first.");
      return;
    }

    if (data.session) {
      navigate("/dashboard");
    }
  }

  return (
    <AuthLayout active="sign-in">
      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (!loading) void handleSignIn();
        }}
        noValidate
      >
        <h2 style={{ fontFamily: authFonts.display, fontSize: "26px", fontWeight: 600, color: C.text, margin: 0, lineHeight: 1.2, letterSpacing: "-0.02em" }}>
          Sign in to ARCE
        </h2>
        <p style={{ fontSize: "14px", color: C.muted, margin: "8px 0 32px", lineHeight: 1.5 }}>Open your projects and saved estimates.</p>

        <div style={{ display: "flex", flexDirection: "column", gap: "18px" }}>
          <AuthInput
            label="Email"
            name="email"
            type="email"
            autoComplete="email"
            value={email}
            onChange={setEmail}
            placeholder="you@example.com"
            iconLeft={
              <svg width="15" height="15" viewBox="0 0 24 24" {...iconStyle}>
                <rect x="2" y="4" width="20" height="16" rx="2" />
                <polyline points="2,4 12,13 22,4" />
              </svg>
            }
          />
          <div>
            <AuthInput
              label="Password"
              name="password"
              type={showPw ? "text" : "password"}
              autoComplete="current-password"
              value={password}
              onChange={setPassword}
              placeholder="Your password"
              iconLeft={
                <svg width="15" height="15" viewBox="0 0 24 24" {...iconStyle}>
                  <rect x="5" y="11" width="14" height="10" rx="2" />
                  <path d="M8 11V7a4 4 0 0 1 8 0v4" />
                </svg>
              }
              iconRight={showPw ? <EyeOff size={15} color="#8793a6" /> : <Eye size={15} color="#8793a6" />}
              iconRightLabel={showPw ? "Hide password" : "Show password"}
              onIconRight={() => setShowPw((v) => !v)}
            />
            <div style={{ display: "flex", justifyContent: "flex-end", marginTop: "10px" }}>
              <button type="button" className="arce-link" style={{ background: "none", border: "none", cursor: "pointer", fontSize: "12px", fontFamily: authFonts.body, color: C.muted, padding: 0 }}>
                Forgot password?
              </button>
            </div>
          </div>
        </div>

        <button
          type="submit"
          disabled={loading}
          className={`arce-primary ${loading ? "shimmer-surface" : ""}`}
          style={{
            width: "100%", height: "46px", marginTop: "26px", background: "#eef4ff", color: "#000", border: "none", borderRadius: "8px",
            fontSize: "14px", fontFamily: authFonts.body, fontWeight: 600, cursor: loading ? "default" : "pointer", opacity: loading ? 0.6 : 1,
          }}
        >
          {loading ? "Signing in…" : "Sign in"}
        </button>

        {error && (
          <p role="alert" className="animate-pop-in" style={{ fontSize: "13px", lineHeight: 1.5, color: C.error, textAlign: "center", margin: "16px 0 0" }}>
            {error}
          </p>
        )}

        <p style={{ fontSize: "13px", color: C.muted, textAlign: "center", margin: "28px 0 0" }}>
          {"New to ARCE? "}
          <button
            type="button"
            className="arce-link"
            onClick={() => navigate("/sign-up")}
            style={{ background: "none", border: "none", cursor: "pointer", fontSize: "13px", color: C.text, textDecoration: "underline", textUnderlineOffset: "3px", padding: 0, fontFamily: authFonts.body }}
          >
            Create an account
          </button>
        </p>
      </form>
    </AuthLayout>
  );
}
