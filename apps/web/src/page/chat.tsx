import { useCallback, useRef, useState, type DragEvent, type ChangeEvent, type KeyboardEvent } from "react";
import { UploadCloud, File as FileIcon, X, CheckCircle2, Image as ImageIcon, FileText } from "lucide-react";

// ---- types --------------------------------------------------------------

interface FileEntry {
  id: number;
  file: File;
  progress: number;
  done: boolean;
  preview: string | null;
}

// ---- helpers -------------------------------------------------------------

function formatBytes(bytes: number): string {
  if (bytes === 0) return "0 KB";
  const units = ["B", "KB", "MB", "GB"];
  const i = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  return `${(bytes / Math.pow(1024, i)).toFixed(i === 0 ? 0 : 1)} ${units[i]}`;
}

function iconFor(type: string) {
  if (type.startsWith("image/")) return ImageIcon;
  if (type === "application/pdf" || type.startsWith("text/")) return FileText;
  return FileIcon;
}

let idCounter = 0;

export default function FileUploadPage() {
  const [entries, setEntries] = useState<FileEntry[]>([]);
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const ingest = useCallback((fileList: FileList) => {
    const files = Array.from(fileList);
    const newEntries: FileEntry[] = files.map((file) => ({
      id: ++idCounter,
      file,
      progress: 0,
      done: false,
      preview: file.type.startsWith("image/") ? URL.createObjectURL(file) : null,
    }));
    setEntries((prev) => [...newEntries, ...prev]);

    newEntries.forEach((entry) => {
      const tick = () => {
        setEntries((prev) =>
          prev.map((e) => {
            if (e.id !== entry.id || e.done) return e;
            const next = Math.min(e.progress + 8 + Math.random() * 14, 100);
            return { ...e, progress: next, done: next >= 100 };
          })
        );
      };
      const interval = setInterval(tick, 180);
      setTimeout(() => clearInterval(interval), 3000);
    });

    // Fetch POST TO FASTAPI

  }, []);

  const onDrop = useCallback(
    (e: DragEvent<HTMLDivElement>) => {
      e.preventDefault();
      setDragging(false);
      if (e.dataTransfer.files?.length) ingest(e.dataTransfer.files);
    },
    [ingest]
  );

  const removeEntry = (id: number) => setEntries((prev) => prev.filter((e) => e.id !== id));

  return (
    <div className="h-full w-full bg-black text-white font-sans flex flex-col items-center justify-center px-6 py-8 overflow-y-auto">
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap');
        .font-display { font-family: 'Space Grotesk', sans-serif; }
        .font-sans { font-family: 'Inter', ui-sans-serif, system-ui, sans-serif; }
        .font-mono-tix { font-family: 'JetBrains Mono', monospace; }
        .manifest-item { animation: slideIn 0.35s ease both; }
        @keyframes slideIn {
          from { opacity: 0; transform: translateY(-6px); }
          to { opacity: 1; transform: translateY(0); }
        }
      `}</style>

      <div className="w-full max-w-[560px] flex flex-col items-center">
        {/* Upload zone */}
        <div
          role="button"
          tabIndex={0}
          onClick={() => inputRef.current?.click()}
          onKeyDown={(e: KeyboardEvent<HTMLDivElement>) =>
            (e.key === "Enter" || e.key === " ") && inputRef.current?.click()
          }
          onDragOver={(e: DragEvent<HTMLDivElement>) => {
            e.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
          className={`w-full shrink-0 rounded-2xl border-2 border-dashed px-8 py-10 text-center cursor-pointer transition-colors duration-200 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-[#7C5CFC]
            ${dragging ? "border-[#7C5CFC] bg-[#7C5CFC]/[0.08]" : "border-[#3A3D47] bg-[#111114] hover:border-[#4A4D57]"}`}
        >
          <input
            ref={inputRef}
            type="file"
            multiple
            hidden
            onChange={(e: ChangeEvent<HTMLInputElement>) => e.target.files?.length && ingest(e.target.files)}
          />
          <div className="w-11 h-11 mx-auto mb-4 rounded-[10px] bg-[#1A1A1E] border border-[#2A2C33] flex items-center justify-center">
            <UploadCloud size={20} className={dragging ? "text-[#7C5CFC]" : "text-[#9A9DA6]"} strokeWidth={1.75} />
          </div>
          <div className="text-[15px]">
            <span className="text-[#A78BFA] font-semibold">Click to upload</span>
            <span className="text-white"> or drag and drop</span>
          </div>
          <div className="text-[13px] text-[#8A8D96] mt-1.5">
            SVG, PNG, JPG or GIF (max. 800×400px)
          </div>
        </div>

        {/* Manifest list */}
        {entries.length > 0 && (
          <div className="w-full mt-6 max-h-[40vh] overflow-y-auto pr-1">
            <div className="font-mono-tix text-[11px] tracking-[0.1em] text-[#8A8D96] uppercase mb-3 flex justify-between">
              <span>Manifest</span>
              <span>{entries.length} item{entries.length > 1 ? "s" : ""}</span>
            </div>

            <div className="flex flex-col gap-2.5">
              {entries.map((entry, idx) => {
                const Icon = iconFor(entry.file.type);
                return (
                  <div
                    key={entry.id}
                    className="manifest-item flex items-center bg-[#111114] border border-[#2A2C33] rounded-xl overflow-hidden"
                  >
                    {/* sequence stub */}
                    <div className="w-11 self-stretch flex items-center justify-center font-mono-tix text-xs text-[#6A6D76] border-r border-dashed border-[#2A2C33]">
                      {String(entries.length - idx).padStart(2, "0")}
                    </div>

                    {/* thumb / icon */}
                    <div className="w-10 h-10 m-3.5 rounded-lg bg-[#1A1A1E] border border-[#2A2C33] flex-shrink-0 flex items-center justify-center overflow-hidden">
                      {entry.preview ? (
                        <img src={entry.preview} alt="" className="w-full h-full object-cover" />
                      ) : (
                        <Icon size={18} className="text-[#9A9DA6]" strokeWidth={1.75} />
                      )}
                    </div>

                    {/* meta */}
                    <div className="flex-1 min-w-0 py-2.5">
                      <div className="text-sm font-medium text-white overflow-hidden text-ellipsis whitespace-nowrap">
                        {entry.file.name}
                      </div>
                      <div className="font-mono-tix text-[11.5px] text-[#8A8D96] mt-0.5">
                        {formatBytes(entry.file.size)}
                      </div>
                      {!entry.done && (
                        <div className="h-[3px] rounded-full bg-[#22242B] mt-2 mr-4 overflow-hidden">
                          <div
                            className="h-full bg-[#7C5CFC] transition-[width] duration-150 ease-out"
                            style={{ width: `${entry.progress}%` }}
                          />
                        </div>
                      )}
                    </div>

                    {/* status / remove */}
                    <div className="flex items-center gap-2.5 px-3.5 flex-shrink-0">
                      {entry.done && <CheckCircle2 size={16} className="text-[#34D399]" strokeWidth={2} />}
                      <button
                        onClick={() => removeEntry(entry.id)}
                        aria-label={`Remove ${entry.file.name}`}
                        className="bg-transparent border-none text-[#8A8D96] cursor-pointer p-1 flex rounded-md hover:text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#7C5CFC]"
                      >
                        <X size={15} strokeWidth={2} />
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}