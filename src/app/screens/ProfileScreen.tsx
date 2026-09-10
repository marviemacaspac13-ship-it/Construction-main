import { useState } from "react";
import { User, Camera, LogOut } from "lucide-react";
import { SectionBar, Btn, Mono } from "../components/ui";
import { useNavigate } from "react-router";

export function ProfileScreen() {
  const navigate = useNavigate();
  const [userName, setUserName] = useState("User");
  const [email, setEmail]       = useState("user@email.com");
  const [editing, setEditing]   = useState<string | null>(null);

  const fields = [
    { key: "userName", label: "Username", value: userName, set: setUserName },
    { key: "email",    label: "Email",    value: email,    set: setEmail },
    { key: "password", label: "Password", value: "••••••••", set: () => {} },
  ];

  return (
    <div className="p-10 max-w-md animate-page-in">
      <SectionBar>Profile</SectionBar>

      <div className="flex flex-col items-center py-8 mb-5 border border-border rounded-lg bg-card hover-lift animate-stagger">
        <div className="relative mb-4">
          <div className="w-20 h-20 rounded-full border-2 border-border bg-accent flex items-center justify-center">
            <User size={28} className="text-muted-foreground" strokeWidth={1.5} />
          </div>
          <button className="absolute bottom-0 right-0 w-6 h-6 rounded-full bg-background border border-border flex items-center justify-center hover:bg-accent transition-colors">
            <Camera size={9} className="text-muted-foreground" />
          </button>
        </div>
        <button className="h-7 px-3 border border-border rounded text-[10px] font-mono text-muted-foreground hover:text-foreground hover:bg-accent transition-colors mb-3">
          Change Image
        </button>
        <p className="text-[13px] font-mono text-foreground">{userName}</p>
        <p className="text-[10px] font-mono text-muted-foreground mt-0.5">{email}</p>
      </div>

      <div className="space-y-2 mb-6">
        {fields.map((f) => (
          <div key={f.key} className="border border-border rounded-lg px-4 py-3 bg-card flex items-center justify-between gap-4">
            <div className="flex-1 min-w-0">
              <Mono className="block mb-0.5">{f.label}</Mono>
              {editing === f.key && f.key !== "password" ? (
                <input
                  value={f.value}
                  onChange={(e) => f.set(e.target.value)}
                  autoFocus
                  className="bg-transparent text-[12px] font-mono text-foreground focus:outline-none w-full"
                />
              ) : (
                <p className="text-[12px] font-mono text-foreground truncate">{f.value}</p>
              )}
            </div>
            <div className="flex gap-1.5 shrink-0">
              {editing === f.key ? (
                <Btn variant="secondary" onClick={() => setEditing(null)}>Save</Btn>
              ) : (
                <>
                  <Btn variant="ghost" onClick={() => setEditing(f.key)}>Edit</Btn>
                  <Btn variant="ghost">Save</Btn>
                </>
              )}
            </div>
          </div>
        ))}
      </div>

      <div className="flex gap-2">
        <Btn variant="secondary" className="flex-1 justify-center" onClick={() => navigate("/sign-in")} icon={<LogOut size={11} />}>Logout</Btn>
        <Btn variant="danger" className="flex-1 justify-center">Delete Account</Btn>
      </div>
    </div>
  );
}
