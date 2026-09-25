import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router";
import { LayoutDashboard, FolderOpen, Clock, HelpCircle, User, LogOut, MessageSquare, Cpu, Shapes } from "lucide-react";
import { Mono, Btn } from "./ui";
import { supabase } from "../../lib/supabase";

export function AppShell({ children }: { children: React.ReactNode }) {
  const [menuOpen, setMenuOpen] = useState(false);
  const [email, setEmail] = useState<string | null>(null);
  const [avatarUrl, setAvatarUrl] = useState<string | null>(null);
  const { pathname } = useLocation();
  const navigate = useNavigate();

  useEffect(() => {
    supabase.auth.getUser().then(({ data }) => {
      setEmail(data.user?.email ?? null);
      setAvatarUrl((data.user?.user_metadata?.avatar_url as string | undefined) ?? null);
    });
    // supabase.auth.updateUser() (called from the Profile screen) fires a
    // USER_UPDATED event on this same client, so a new avatar or name shows
    // up here immediately without needing a shared store or a page reload.
    const { data: sub } = supabase.auth.onAuthStateChange((_event, session) => {
      setEmail(session?.user?.email ?? null);
      setAvatarUrl((session?.user?.user_metadata?.avatar_url as string | undefined) ?? null);
    });
    return () => sub.subscription.unsubscribe();
  }, []);

  // Shown before the @ — a reasonable stand-in for a username since this
  // project doesn't collect a separate display name at sign-up.
  const displayName = email ? email.split("@")[0] : "…";

  const handleLogout = async () => {
    setMenuOpen(false);
    await supabase.auth.signOut();
    navigate("/sign-in");
  };

  const navItems = [
    { path: "/dashboard",       Icon: LayoutDashboard, label: "Dashboard" },
    { path: "/projects",        Icon: FolderOpen,      label: "Projects"  },
    { path: "/history",         Icon: Clock,           label: "Estimation History" },
    { path: "/symbol-library",  Icon: Shapes,          label: "Symbol Library" },
    { path: "/train-model",     Icon: Cpu,             label: "Train Model" },
  ];

  const isActive = (path: string) =>
    pathname === path ||
    (path === "/projects" && ["/projects/details", "/upload", "/scanning", "/results"].includes(pathname));

  return (
    <div className="h-screen flex flex-col bg-background overflow-hidden" style={{ fontFamily: "'Sora','Inter',sans-serif" }}>
      <header className="h-[70px] flex items-center justify-between px-8 border-b border-border bg-background shrink-0 relative z-20">
        <div className="flex items-center gap-4">
          <span className="font-mono font-light text-foreground" style={{ letterSpacing: "12px", fontSize: "16px" }}>TRACE</span>
          <div className="w-px h-4 bg-border" />
          <Mono>{displayName}</Mono>
        </div>
        <div className="flex items-center gap-2">
          <Btn variant="ghost" onClick={() => navigate("/feedback")} icon={<MessageSquare size={12} />}>Feedback</Btn>
          <button
            onClick={() => navigate("/help")}
            className="w-8 h-8 flex items-center justify-center rounded-lg border border-border text-muted-foreground hover:text-foreground hover:bg-accent press-scale"
          >
            <HelpCircle size={14} />
          </button>
          <div className="relative">
            <button
              onClick={() => setMenuOpen((v) => !v)}
              className={`w-8 h-8 rounded-full border flex items-center justify-center overflow-hidden press-scale ${menuOpen ? "border-foreground/40 bg-muted" : "border-border bg-accent hover:bg-muted"}`}
            >
              {avatarUrl ? (
                <img src={avatarUrl} alt="" className="w-full h-full object-cover" />
              ) : (
                <User size={13} className="text-muted-foreground" />
              )}
            </button>
            {menuOpen && (
              <>
                <div className="fixed inset-0 z-40" onClick={() => setMenuOpen(false)} />
                <div className="absolute right-0 top-10 w-48 bg-popover border border-border rounded-lg overflow-hidden z-50 shadow-lg animate-pop-in origin-top-right">
                <div className="flex items-center gap-3 px-4 py-3 border-b border-border">
                  <div className="w-7 h-7 rounded-full bg-accent border border-border flex items-center justify-center overflow-hidden shrink-0">
                    {avatarUrl ? (
                      <img src={avatarUrl} alt="" className="w-full h-full object-cover" />
                    ) : (
                      <User size={11} className="text-muted-foreground" />
                    )}
                  </div>
                  <div className="min-w-0">
                    <p className="text-[11px] font-mono text-foreground leading-tight truncate">{displayName}</p>
                    <p className="text-[10px] font-mono text-muted-foreground truncate">{email ?? ""}</p>
                  </div>
                </div>
                <button
                  onClick={() => { setMenuOpen(false); navigate("/profile"); }}
                  className="w-full flex items-center gap-3 px-4 py-2.5 text-[11px] font-mono text-foreground hover:bg-accent hover:pl-5 transition-all duration-200 border-b border-border"
                >
                  <User size={11} className="text-muted-foreground" /> Profile
                </button>
                <button
                  onClick={handleLogout}
                  className="w-full flex items-center gap-3 px-4 py-2.5 text-[11px] font-mono text-muted-foreground hover:bg-accent hover:text-foreground hover:pl-5 transition-all duration-200"
                >
                  <LogOut size={11} className="text-muted-foreground" /> Logout
                </button>
              </div>
              </>
            )}
          </div>
        </div>
      </header>

      <div className="flex flex-1 overflow-hidden">
        <aside className="w-[220px] border-r border-border flex flex-col shrink-0 bg-background">
          {navItems.map(({ path, Icon, label }, i) => (
            <button
              key={path}
              onClick={() => navigate(path)}
              className={`
                relative flex items-center gap-3 h-10 px-6 text-[11px] font-mono tracking-[0.14em] uppercase transition-all duration-200 border-b border-border overflow-hidden animate-slide-left
                ${isActive(path)
                  ? "text-foreground bg-accent after:absolute after:left-0 after:top-0 after:h-full after:w-[2px] after:bg-foreground after:animate-scale-in"
                  : "text-muted-foreground hover:text-foreground hover:bg-accent/50 hover:pl-7"}
              `}
              style={{ animationDelay: `${i * 60}ms` }}
            >
              <Icon size={13} className="transition-transform duration-200" />
              {label}
            </button>
          ))}
        </aside>
        <main className="flex-1 overflow-y-auto" style={{ scrollbarWidth: "none" }}>{children}</main>
      </div>
    </div>
  );
}