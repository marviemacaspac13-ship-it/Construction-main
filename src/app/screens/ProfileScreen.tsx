import { useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
import { Camera, LogOut, Check, X, Pencil, AtSign, UserRound, KeyRound, ShieldCheck, Loader2 } from "lucide-react";
import { SectionBar, Btn, Mono, TxtInput } from "../components/ui";
import { useNavigate } from "react-router";
import { supabase } from "../../lib/supabase";

function initialsOf(name: string) {
  const parts = name.trim().split(/[\s._-]+/).filter(Boolean);
  if (parts.length === 0) return "?";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[1][0]).toUpperCase();
}

function IconTag({ children }: { children: ReactNode }) {
  return (
    <span className="w-9 h-9 rounded-lg border border-border bg-accent flex items-center justify-center text-muted-foreground shrink-0">
      {children}
    </span>
  );
}

const MAX_AVATAR_BYTES = 5 * 1024 * 1024; // 5MB

export function ProfileScreen() {
  const navigate = useNavigate();
  const avatarInputRef = useRef<HTMLInputElement>(null);

  const [loading, setLoading]       = useState(true);
  const [userId, setUserId]         = useState("");
  const [userName, setUserName]     = useState("");
  const [email, setEmail]           = useState("");
  const [avatarUrl, setAvatarUrl]   = useState<string | null>(null);
  const [memberSince, setMemberSince] = useState<string | null>(null);
  const [draftName, setDraftName]   = useState("");
  const [draftEmail, setDraftEmail] = useState("");
  const [editing, setEditing]       = useState<"userName" | "email" | "password" | null>(null);
  const [savingField, setSavingField] = useState(false);
  const [fieldError, setFieldError]   = useState("");
  const [fieldNotice, setFieldNotice] = useState("");

  const [avatarUploading, setAvatarUploading] = useState(false);
  const [avatarError, setAvatarError]         = useState("");

  const [newPassword, setNewPassword]         = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [pwError, setPwError]   = useState("");
  const [pwSaving, setPwSaving] = useState(false);

  useEffect(() => {
    supabase.auth.getUser().then(({ data }) => {
      const u = data.user;
      const name = (u?.user_metadata?.username as string | undefined) ?? (u?.email ? u.email.split("@")[0] : "User");
      setUserId(u?.id ?? "");
      setUserName(name);
      setDraftName(name);
      setEmail(u?.email ?? "");
      setDraftEmail(u?.email ?? "");
      setAvatarUrl((u?.user_metadata?.avatar_url as string | undefined) ?? null);
      setMemberSince(u?.created_at ?? null);
      setLoading(false);
    });
  }, []);

  const initials = useMemo(() => initialsOf(userName || email || "User"), [userName, email]);

  function pickAvatarFile() {
    avatarInputRef.current?.click();
  }

  async function handleAvatarChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = ""; // allow re-selecting the same file later
    if (!file || !userId) return;

    setAvatarError("");

    if (!file.type.startsWith("image/")) {
      setAvatarError("Please choose an image file.");
      return;
    }
    if (file.size > MAX_AVATAR_BYTES) {
      setAvatarError("Image must be under 5MB.");
      return;
    }

    setAvatarUploading(true);
    try {
      const ext = (file.name.split(".").pop() || "jpg").toLowerCase();
      const path = `${userId}/avatar.${ext}`;

      const { error: uploadError } = await supabase.storage
        .from("avatars")
        .upload(path, file, { upsert: true, cacheControl: "3600" });
      if (uploadError) throw uploadError;

      const { data: pub } = supabase.storage.from("avatars").getPublicUrl(path);
      // Bust any cached copy of the previous avatar at this same path.
      const freshUrl = `${pub.publicUrl}?t=${Date.now()}`;

      const { error: updateError } = await supabase.auth.updateUser({ data: { avatar_url: freshUrl } });
      if (updateError) throw updateError;

      setAvatarUrl(freshUrl);
    } catch (err) {
      setAvatarError(err instanceof Error ? err.message : "Couldn't upload that image.");
    } finally {
      setAvatarUploading(false);
    }
  }

  async function saveUserName() {
    setFieldError(""); setFieldNotice(""); setSavingField(true);
    const { error } = await supabase.auth.updateUser({ data: { username: draftName } });
    setSavingField(false);
    if (error) { setFieldError(error.message); return; }
    setUserName(draftName);
    setEditing(null);
  }

  async function saveEmail() {
    setFieldError(""); setFieldNotice(""); setSavingField(true);
    const { error } = await supabase.auth.updateUser({ email: draftEmail });
    setSavingField(false);
    if (error) { setFieldError(error.message); return; }
    // Supabase sends a confirmation link to the new address before the
    // change actually takes effect, so the displayed email doesn't flip yet.
    setFieldNotice("Check your new email address to confirm the change.");
    setEditing(null);
  }

  function cancelEdit() {
    setDraftName(userName);
    setDraftEmail(email);
    setFieldError("");
    setEditing(null);
  }

  async function savePassword() {
    setPwError("");
    if (newPassword.length < 8) {
      setPwError("Password must be at least 8 characters.");
      return;
    }
    if (newPassword !== confirmPassword) {
      setPwError("Passwords don't match.");
      return;
    }
    setPwSaving(true);
    const { error } = await supabase.auth.updateUser({ password: newPassword });
    setPwSaving(false);
    if (error) { setPwError(error.message); return; }
    setNewPassword("");
    setConfirmPassword("");
    setEditing(null);
    setFieldNotice("Password updated.");
  }

  function cancelPassword() {
    setEditing(null);
    setNewPassword("");
    setConfirmPassword("");
    setPwError("");
  }

  async function handleLogout() {
    await supabase.auth.signOut();
    navigate("/sign-in");
  }

  if (loading) {
    return (
      <div className="p-10 animate-page-in">
        <SectionBar>Profile</SectionBar>
        <Mono>Loading…</Mono>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col p-10 animate-page-in">
      <SectionBar>Profile</SectionBar>

      <div className="flex-1 min-h-0 grid grid-cols-1 lg:grid-cols-[320px_1fr] gap-6">
        {/* ── Identity panel ─────────────────────────────────────── */}
        <aside className="border-beam border border-border rounded-lg bg-card flex flex-col items-center text-center px-8 py-10 animate-stagger">
          <input
            ref={avatarInputRef}
            type="file"
            accept="image/*"
            onChange={handleAvatarChange}
            className="hidden"
          />

          <div className="relative mb-5">
            <div className="w-24 h-24 rounded-full border border-border bg-accent flex items-center justify-center overflow-hidden">
              {avatarUrl ? (
                <img src={avatarUrl} alt="Profile" className="w-full h-full object-cover" />
              ) : (
                <span className="text-[22px] font-mono font-medium text-foreground tracking-wide">{initials}</span>
              )}
              {avatarUploading && (
                <div className="absolute inset-0 rounded-full bg-background/70 flex items-center justify-center">
                  <Loader2 size={18} className="text-foreground animate-spin" />
                </div>
              )}
            </div>
            <button
              onClick={pickAvatarFile}
              disabled={avatarUploading}
              className="absolute bottom-0 right-0 w-7 h-7 rounded-full bg-background border border-border flex items-center justify-center hover:bg-accent hover:border-foreground/30 transition-colors press-scale disabled:opacity-50 disabled:pointer-events-none"
            >
              <Camera size={10} className="text-muted-foreground" />
            </button>
          </div>

          <p className="text-[14px] font-mono text-foreground">{userName}</p>
          <p className="text-[10px] font-mono text-muted-foreground mt-1 truncate max-w-full">{email}</p>

          <button
            onClick={pickAvatarFile}
            disabled={avatarUploading}
            className="h-7 px-3 mt-4 border border-border rounded text-[10px] font-mono text-muted-foreground hover:text-foreground hover:bg-accent transition-colors disabled:opacity-50 disabled:pointer-events-none"
          >
            {avatarUploading ? "Uploading…" : "Change photo"}
          </button>
          {avatarError && (
            <p className="text-[10px] font-mono text-red-400 mt-2 animate-pop-in max-w-full">{avatarError}</p>
          )}

          <div className="w-full h-px bg-border my-7" />

          <div className="w-full space-y-3 text-left">
            <div className="flex items-center justify-between">
              <Mono className="text-[9px]">Member since</Mono>
              <span className="text-[11px] font-mono text-foreground">
                {memberSince ? new Date(memberSince).toLocaleDateString(undefined, { month: "short", year: "numeric" }) : "—"}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <Mono className="text-[9px]">Status</Mono>
              <span className="inline-flex items-center gap-1.5 text-[11px] font-mono text-foreground">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 shrink-0" />
                Active
              </span>
            </div>
          </div>

          <div className="flex-1" />

          <div className="w-full flex flex-col gap-2 mt-8">
            <Btn variant="secondary" full onClick={handleLogout} icon={<LogOut size={11} />}>Logout</Btn>
            <Btn variant="danger" full>Delete Account</Btn>
          </div>
        </aside>

        {/* ── Settings content ───────────────────────────────────── */}
        <div className="min-h-0 overflow-y-auto pr-1 space-y-7">
          {fieldNotice && (
            <p className="text-[10px] font-mono text-emerald-400 animate-pop-in">{fieldNotice}</p>
          )}

          {/* Account */}
          <section className="animate-stagger" style={{ animationDelay: "60ms" }}>
            <Mono className="text-[11px] block mb-3">Account</Mono>
            <div className="border border-border rounded-lg bg-card divide-y divide-border overflow-hidden">
              {/* Username row */}
              <div className="flex items-center gap-4 px-5 py-4">
                <IconTag><UserRound size={14} /></IconTag>
                <div className="flex-1 min-w-0">
                  <Mono className="block mb-0.5 text-[9px]">Username</Mono>
                  {editing === "userName" ? (
                    <input
                      value={draftName}
                      onChange={(e) => setDraftName(e.target.value)}
                      autoFocus
                      className="bg-transparent text-[12px] font-mono text-foreground focus:outline-none w-full"
                    />
                  ) : (
                    <p className="text-[12px] font-mono text-foreground truncate">{userName}</p>
                  )}
                </div>
                <div className="flex gap-1.5 shrink-0">
                  {editing === "userName" ? (
                    <>
                      <Btn variant="primary" onClick={saveUserName} icon={<Check size={11} />}>{savingField ? "Saving…" : "Save"}</Btn>
                      <Btn variant="ghost" onClick={cancelEdit} icon={<X size={11} />}>Cancel</Btn>
                    </>
                  ) : (
                    <Btn variant="ghost" onClick={() => { setEditing("userName"); setFieldError(""); setFieldNotice(""); }} icon={<Pencil size={11} />}>Edit</Btn>
                  )}
                </div>
              </div>

              {/* Email row */}
              <div className="flex items-center gap-4 px-5 py-4">
                <IconTag><AtSign size={14} /></IconTag>
                <div className="flex-1 min-w-0">
                  <Mono className="block mb-0.5 text-[9px]">Email</Mono>
                  {editing === "email" ? (
                    <input
                      value={draftEmail}
                      onChange={(e) => setDraftEmail(e.target.value)}
                      autoFocus
                      className="bg-transparent text-[12px] font-mono text-foreground focus:outline-none w-full"
                    />
                  ) : (
                    <p className="text-[12px] font-mono text-foreground truncate">{email}</p>
                  )}
                </div>
                <div className="flex gap-1.5 shrink-0">
                  {editing === "email" ? (
                    <>
                      <Btn variant="primary" onClick={saveEmail} icon={<Check size={11} />}>{savingField ? "Saving…" : "Save"}</Btn>
                      <Btn variant="ghost" onClick={cancelEdit} icon={<X size={11} />}>Cancel</Btn>
                    </>
                  ) : (
                    <Btn variant="ghost" onClick={() => { setEditing("email"); setFieldError(""); setFieldNotice(""); }} icon={<Pencil size={11} />}>Edit</Btn>
                  )}
                </div>
              </div>
            </div>
            {(editing === "userName" || editing === "email") && fieldError && (
              <p className="text-[10px] font-mono text-red-400 px-1 mt-2">{fieldError}</p>
            )}
          </section>

          {/* Security */}
          <section className="animate-stagger" style={{ animationDelay: "110ms" }}>
            <Mono className="text-[11px] block mb-3">Security</Mono>
            <div className="border border-border rounded-lg bg-card overflow-hidden">
              <div className="flex items-center gap-4 px-5 py-4">
                <IconTag><KeyRound size={14} /></IconTag>
                <div className="flex-1 min-w-0">
                  <Mono className="block mb-0.5 text-[9px]">Password</Mono>
                  <p className="text-[12px] font-mono text-foreground truncate">••••••••••</p>
                </div>
                {editing !== "password" && (
                  <Btn variant="ghost" onClick={() => { setEditing("password"); setPwError(""); setFieldNotice(""); }} icon={<Pencil size={11} />}>
                    Change
                  </Btn>
                )}
              </div>

              {editing === "password" && (
                <div className="px-5 pb-5 pt-1 space-y-3 border-t border-border animate-pop-in">
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-4">
                    <TxtInput type="password" value={newPassword} onChange={setNewPassword} placeholder="New password" />
                    <TxtInput type="password" value={confirmPassword} onChange={setConfirmPassword} placeholder="Confirm new password" />
                  </div>
                  {pwError && <p className="text-[10px] font-mono text-red-400">{pwError}</p>}
                  <div className="flex gap-1.5">
                    <Btn variant="primary" onClick={savePassword} icon={<Check size={11} />}>
                      {pwSaving ? "Saving…" : "Save password"}
                    </Btn>
                    <Btn variant="ghost" onClick={cancelPassword} icon={<X size={11} />}>Cancel</Btn>
                  </div>
                </div>
              )}
            </div>
            <p className="text-[10px] font-mono text-muted-foreground/50 mt-2 flex items-center gap-1.5">
              <ShieldCheck size={10} /> Use at least 8 characters — a mix of words is fine, no need for symbols.
            </p>
          </section>
        </div>
      </div>
    </div>
  );
}