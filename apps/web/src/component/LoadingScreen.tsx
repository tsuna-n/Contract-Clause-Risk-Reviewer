import { FileSearch, LoaderCircle } from "lucide-react";

export default function LoadingScreen({ message }: { message: string }) {
  return (
    <div className="state-page" role="status">
      <div className="state-card">
        <span className="brand-icon"><FileSearch size={24} /></span>
        <p className="eyebrow">URRISK WORKSPACE</p>
        <LoaderCircle size={24} className="animate-spin text-teal-300" />
        <p className="text-sm text-navy-200">{message}</p>
      </div>
    </div>
  );
}
