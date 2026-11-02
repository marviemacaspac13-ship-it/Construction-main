import { useState } from "react";
import { Eye, EyeOff } from "lucide-react";
import { useNavigate } from "react-router";
import { AuthInput, AuthLayout, authColors as C, authFonts } from "../components/AuthLeft";
import { supabase } from "../../lib/supabase";

const iconStyle = { stroke: "#6b7789", strokeWidth: 1.8, strokeLinecap: "round", strokeLinejoin: "round", fill: "none" } as const;

const lockIcon = (
  <svg width="15" height="15" viewBox="0 0 24 24" {...iconStyle}>
    <rect x="5" y="11" width="14" height="10" rx="2" />
    <path d="M8 11V7a4 4 0 0 1 8 0v4" />
  </svg>
);

export function SignUpScreen() {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [showPw, setShowPw] = useState(false);
  const [showCf, setShowCf] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleSignUp() {
    setError("");

    if (!email || !password) {
      setError("Enter your email and a password.");
      return;
    }
    if (password !== confirm) {
      setError("The two passwords don't match.");
      return;
    }
    if (password.length < 6) {
      setError("Use a password with at least 6 characters.");
      return;
    }

    setLoading(true);
    const { data, error: signUpError } = await supabase.auth.signUp({ email, password });
    setLoading(false);

    if (signUpError) {
      setError(signUpError.message);
      return;
    }

    // Email confirmation is disabled in the Supabase dashboard, so
    // signUp() returns an active session immediately — no verification step.
    if (data.session) {
      navigate("/dashboard");
    } else {
      // Fallback in case confirmation is ever re-enabled later
      navigate("/sign-in");
    }
  }

  return (
    <AuthLayout active="sign-up">
      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (!loading) void handleSignUp();
        }}
        noValidate
      >
        <h2 style={{ fontFamily: authFonts.display, fontSize: "26px", fontWeight: 600, color: C.text, margin: 0, lineHeight: 1.2, letterSpacing: "-0.02em" }}>
          Create your ARCE account
        </h2>
        <p style={{ fontSize: "14px", color: C.muted, margin: "8px 0 32px", lineHeight: 1.5 }}>One account keeps your projects and saved estimates together.</p>

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
          <AuthInput
            label="Password"
            name="new-password"
            type={showPw ? "text" : "password"}
            autoComplete="new-password"
            value={password}
            onChange={setPassword}
            placeholder="At least 6 characters"
            iconLeft={lockIcon}
            iconRight={showPw ? <EyeOff size={15} color="#8793a6" /> : <Eye size={15} color="#8793a6" />}
            iconRightLabel={showPw ? "Hide password" : "Show password"}
            onIconRight={() => setShowPw((v) => !v)}
          />
          <AuthInput
            label="Confirm password"
            name="confirm-password"
            type={showCf ? "text" : "password"}
            autoComplete="new-password"
            value={confirm}
            onChange={setConfirm}
            placeholder="Type it again"
            iconLeft={lockIcon}
            iconRight={showCf ? <EyeOff size={15} color="#8793a6" /> : <Eye size={15} color="#8793a6" />}
            iconRightLabel={showCf ? "Hide password" : "Show password"}
            onIconRight={() => setShowCf((v) => !v)}
          />
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
          {loading ? "Creating account…" : "Create account"}
        </button>

        {error && (
          <p role="alert" className="animate-pop-in" style={{ fontSize: "13px", lineHeight: 1.5, color: C.error, textAlign: "center", margin: "16px 0 0" }}>
            {error}
          </p>
        )}

        <p style={{ fontSize: "13px", color: C.muted, textAlign: "center", margin: "28px 0 0" }}>
          {"Already have an account? "}
          <button
            type="button"
            className="arce-link"
            onClick={() => navigate("/sign-in")}
            style={{ background: "none", border: "none", cursor: "pointer", fontSize: "13px", color: C.text, textDecoration: "underline", textUnderlineOffset: "3px", padding: 0, fontFamily: authFonts.body }}
          >
            Sign in
          </button>
        </p>
      </form>
    </AuthLayout>
  );
}
