import { useNavigate } from "react-router-dom";
import { Sidebar } from "../component/sidebar";
import { clearToken } from "../lib/auth";

/**
 * ManualPage — Welcome/onboarding page with instructions and document example.
 *
 * Layout:
 *   Sidebar (left)
 *   Container with dark background
 *     Left side: Bordered text box with instructions
 *     Right side: Document image preview
 *     Bottom: Start button (centered)
 */
export default function ManualPage() {
  const navigate = useNavigate();

  const menuItems = [
    {
      label: "Dashboard",
      icon: "📊",
      onClick: () => console.log("Dashboard clicked"),
    },
    {
      label: "Documents",
      icon: "📄",
      children: [
        {
          label: "Upload",
          icon: "📤",
          onClick: () => console.log("Upload clicked"),
        },
        {
          label: "My Files",
          icon: "📁",
          onClick: () => console.log("My Files clicked"),
        },
        {
          label: "Recent",
          icon: "🕐",
          onClick: () => console.log("Recent clicked"),
        },
      ],
    },
    {
      label: "Analysis",
      icon: "🔍",
      children: [
        {
          label: "Risk Assessment",
          onClick: () => console.log("Risk Assessment clicked"),
        },
        {
          label: "Reports",
          onClick: () => console.log("Reports clicked"),
        },
      ],
    },
    {
      label: "Settings",
      icon: "⚙️",
      onClick: () => console.log("Settings clicked"),
    },
    {
      label: "Help",
      icon: "❓",
      onClick: () => console.log("Help clicked"),
    },
    {
      label: "Logout",
      icon: "🚪",
      onClick: () => {
        clearToken();
        navigate("/login", { replace: true });
      },
    },
  ];

  return (
    <div className="flex">
      <Sidebar items={menuItems} title="Contract Reviewer" />
      <div className="ml-64 w-full min-h-screen bg-black flex flex-col items-center justify-center px-8 py-12">
      {/* Main Content Container */}
      <div className="w-full max-w-6xl flex gap-8 items-start mb-12">
        {/* Left: Text Content */}
        <div className="flex-1 max-w-md">
          <div className="border-2 border-white rounded-2xl p-8 bg-black">
            <p className="text-white text-sm leading-relaxed font-light">
              Welcome to the Contract Clause Risk Reviewer. This powerful tool helps you analyze and assess risks in contract clauses with precision and efficiency.
            </p>

            <p className="text-white text-sm leading-relaxed font-light mt-6">
              Simply upload your contract document, and our AI-powered system will automatically identify potential risks, highlight critical clauses, and provide detailed analysis to help you make informed decisions.
            </p>

            <p className="text-white text-sm leading-relaxed font-light mt-6">
              The system evaluates clauses across multiple risk categories including legal compliance, financial exposure, operational constraints, and liability concerns. Get instant insights with our comprehensive risk assessment reports.
            </p>

            <p className="text-white text-sm leading-relaxed font-light mt-6">
              To get started, click the Start button below and upload your first contract document. The entire analysis process takes just moments, providing you with actionable insights to protect your interests.
            </p>
          </div>
        </div>

        {/* Right: Document Preview Image */}
        <div className="flex-1 flex justify-center">
          <div className="bg-white rounded-lg shadow-2xl overflow-hidden max-w-sm w-full">
            <div className="aspect-video bg-gradient-to-br from-slate-200 to-slate-300 flex items-center justify-center p-4">
              <div className="text-center">
                <svg
                  className="w-16 h-16 text-slate-400 mx-auto mb-4"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                  />
                </svg>
                <p className="text-slate-600 text-sm font-medium">
                  Sample Contract Document
                </p>
              </div>
            </div>
            {/* Document header */}
            <div className="bg-slate-50 px-6 py-4 border-b border-slate-200">
              <h3 className="text-sm font-semibold text-slate-800">
                Contract Analysis Preview
              </h3>
              <p className="text-xs text-slate-500 mt-1">
                Upload your contract to see detailed risk analysis
              </p>
            </div>
            {/* Document content preview */}
            <div className="px-6 py-4 space-y-3">
              <div className="h-2 bg-slate-200 rounded w-3/4"></div>
              <div className="h-2 bg-slate-200 rounded w-full"></div>
              <div className="h-2 bg-slate-200 rounded w-4/5"></div>
              <div className="mt-4 pt-4 border-t border-slate-200">
                <div className="h-2 bg-slate-100 rounded w-1/2 mb-2"></div>
                <div className="h-2 bg-slate-100 rounded w-2/3"></div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Start Button */}
      <button
        onClick={() => navigate("/contract")}
        className="mt-8 px-16 py-4 border-2 border-white text-white text-lg font-medium rounded-full hover:bg-white hover:text-black transition-all duration-300 hover:shadow-xl"
      >
        Start
      </button>

      {/* Optional: Info text below button */}
      <p className="text-white text-xs mt-8 text-center max-w-md opacity-70">
        Get started in seconds. No credit card required.
      </p>
      </div>
    </div>
  );
}
