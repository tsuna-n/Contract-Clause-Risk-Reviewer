import { useState } from "react";

interface SidebarItem {
  label: string;
  icon?: string;
  href?: string;
  onClick?: () => void;
  children?: SidebarItem[];
}

interface SidebarProps {
  items: SidebarItem[];
  title?: string;
  collapsed?: boolean;
  onCollapse?: (collapsed: boolean) => void;
}

export default function Sidebar({
  items,
  title = "Menu",
  collapsed = false,
  onCollapse,
}: SidebarProps) {
  const [isCollapsed, setIsCollapsed] = useState(collapsed);
  const [expandedItems, setExpandedItems] = useState<Set<string>>(new Set());

  const toggleCollapse = () => {
    const newState = !isCollapsed;
    setIsCollapsed(newState);
    onCollapse?.(newState);
  };

  const toggleExpand = (label: string) => {
    const newExpanded = new Set(expandedItems);
    if (newExpanded.has(label)) {
      newExpanded.delete(label);
    } else {
      newExpanded.add(label);
    }
    setExpandedItems(newExpanded);
  };

  return (
    <aside
      className={`fixed left-0 top-0 h-screen bg-gradient-to-b from-slate-900 to-slate-800 text-white shadow-2xl transition-all duration-300 ease-in-out ${
        isCollapsed ? "w-20" : "w-64"
      }`}
    >
      {/* Header */}
      <div className="flex items-center justify-between border-b border-slate-700 px-4 py-6">
        {!isCollapsed && (
          <h1 className="text-xl font-bold tracking-wide">{title}</h1>
        )}
        <button
          onClick={toggleCollapse}
          className="rounded-lg p-2 hover:bg-slate-700 transition-colors"
          aria-label="Toggle sidebar"
        >
          {isCollapsed ? "→" : "←"}
        </button>
      </div>

      {/* Navigation Items */}
      <nav className="space-y-2 px-3 py-4">
        {items.map((item) => (
          <div key={item.label}>
            <button
              onClick={() => {
                item.onClick?.();
                if (item.children) {
                  toggleExpand(item.label);
                }
              }}
              className="w-full flex items-center justify-between rounded-lg px-4 py-3 text-left text-sm font-medium hover:bg-slate-700 transition-colors duration-200 hover:shadow-md"
            >
              <div className="flex items-center gap-3">
                {item.icon && (
                  <span className="text-lg">{item.icon}</span>
                )}
                {!isCollapsed && (
                  <span className="truncate">{item.label}</span>
                )}
              </div>
              {!isCollapsed && item.children && (
                <span
                  className={`transition-transform duration-300 ${
                    expandedItems.has(item.label) ? "rotate-90" : ""
                  }`}
                >
                  ›
                </span>
              )}
            </button>

            {/* Submenu */}
            {!isCollapsed && item.children && expandedItems.has(item.label) && (
              <div className="ml-4 space-y-1 border-l border-slate-600 pl-2">
                {item.children.map((child) => (
                  <button
                    key={child.label}
                    onClick={child.onClick}
                    className="w-full flex items-center gap-2 rounded-lg px-4 py-2 text-xs font-medium text-slate-300 hover:bg-slate-700 hover:text-white transition-colors duration-200"
                  >
                    {child.icon && <span>{child.icon}</span>}
                    <span className="truncate">{child.label}</span>
                  </button>
                ))}
              </div>
            )}
          </div>
        ))}
      </nav>
    </aside>
  );
}
