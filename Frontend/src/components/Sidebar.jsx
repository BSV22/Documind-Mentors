import { useState } from "react";

const sidebarItems = [
  { id: "history", label: "Chat History" },
  { id: "profile", label: "Profile" },
  { id: "settings", label: "Settings" },
];

const historyItems = [
  {
    title: "New project plan",
    subtitle: "You asked about roadmap ideas",
    time: "2m ago",
  },
  {
    title: "API integration",
    subtitle: "You discussed backend connection",
    time: "1h ago",
  },
  {
    title: "Design review",
    subtitle: "You requested UI suggestions",
    time: "Yesterday",
  },
];

export default function Sidebar({ isOpen = true }) {
  const [activePanel, setActivePanel] = useState("history");

  return (
    <aside
      className={`flex-none flex flex-col h-full rounded-3xl bg-gray-900 p-3 shadow-xl overflow-hidden transition-all duration-700 ease-out ${
        isOpen ? "border border-gray-700 opacity-100 scale-100" : "border-0 opacity-0 scale-95 pointer-events-none"
      }`}
      style={{
        width: isOpen ? "380px" : "0px",
        minWidth: isOpen ? "380px" : "0px",
        padding: isOpen ? undefined : "0px",
      }}
    >
      <div className="mb-5 px-3 py-3 rounded-3xl bg-gray-900 border border-gray-700">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-xs uppercase tracking-[0.22em] text-cyan-300 font-semibold">
              Sidebar
            </p>
            <h2 className="mt-2 text-white text-xl font-semibold">Workspace</h2>
          </div>
          <span className="inline-flex h-9 w-9 items-center justify-center rounded-2xl bg-cyan-500 text-gray-950 font-bold">
            W
          </span>
        </div>

        <div className="mt-4 grid gap-2">
          {sidebarItems.map((item) => (
            <button
              key={item.id}
              onClick={() => setActivePanel(item.id)}
              className={`w-full text-left rounded-2xl px-3 py-2 transition-all ${
                activePanel === item.id
                  ? "bg-cyan-500 text-gray-950 shadow-lg"
                  : "bg-gray-800 text-gray-300 hover:bg-gray-700"
              }`}
            >
              {item.label}
            </button>
          ))}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-0 py-2">
        {activePanel === "history" && (
          <div className="space-y-4 px-3 py-3 rounded-3xl bg-gray-900 border border-gray-700">
            <div className="mb-3">
              <h3 className="text-base font-semibold text-white">Recent chats</h3>
              <p className="text-sm text-gray-400">Open or revisit your latest conversations.</p>
            </div>
            <div className="space-y-2">
              {historyItems.map((item) => (
                <div key={item.title} className="rounded-3xl border border-gray-800 bg-gray-800 p-3">
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <h4 className="text-white font-semibold text-sm">{item.title}</h4>
                      <p className="text-sm text-gray-400">{item.subtitle}</p>
                    </div>
                    <span className="text-[11px] text-gray-500">{item.time}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {activePanel === "profile" && (
          <div className="space-y-4 px-3 py-3 rounded-3xl bg-gray-900 border border-gray-700">
            <div className="flex items-center gap-3">
              <div className="h-14 w-14 rounded-3xl bg-cyan-500 flex items-center justify-center text-xl font-bold text-gray-950">
                B
              </div>
              <div>
                <h3 className="text-white text-lg font-semibold">Basava</h3>
                <p className="text-sm text-gray-400">Admin</p>
              </div>
            </div>
            <div className="space-y-2 rounded-3xl border border-gray-800 bg-gray-800 p-3">
              <div className="flex items-center justify-between text-sm text-gray-300">
                <span>Email</span>
                <span className="text-xs">basava@example.com</span>
              </div>
              <div className="flex items-center justify-between text-sm text-gray-300">
                <span>Workspace</span>
                <span className="text-xs">Documind</span>
              </div>
              <div className="flex items-center justify-between text-sm text-gray-300">
                <span>Plan</span>
                <span className="text-xs">Pro</span>
              </div>
            </div>
          </div>
        )}

        {activePanel === "settings" && (
          <div className="space-y-4 px-3 py-3 rounded-3xl bg-gray-900 border border-gray-700">
            <div>
              <h3 className="text-base font-semibold text-white">Preferences</h3>
              <p className="text-sm text-gray-400">Adjust your workspace settings and quick actions.</p>
            </div>
            <div className="space-y-2 rounded-3xl border border-gray-800 bg-gray-800 p-3">
              <div className="flex items-center justify-between gap-3 text-sm text-gray-300">
                <span>Dark mode</span>
                <span className="rounded-full bg-gray-700 px-3 py-1 text-[10px]">Enabled</span>
              </div>
              <div className="flex items-center justify-between gap-3 text-sm text-gray-300">
                <span>Notifications</span>
                <span className="rounded-full bg-gray-700 px-3 py-1 text-[10px]">On</span>
              </div>
              <div className="flex items-center justify-between gap-3 text-sm text-gray-300">
                <span>Auto-save</span>
                <span className="rounded-full bg-gray-700 px-3 py-1 text-[10px]">Off</span>
              </div>
            </div>
            <div className="rounded-3xl border border-dashed border-gray-700 bg-gray-800 p-3 text-sm text-gray-400">
              Tamplate
            </div>
          </div>
        )}
      </div>
    </aside>
  );
}
