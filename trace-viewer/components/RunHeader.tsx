import React, { useRef } from "react";
import { RunMeta, RunResult } from "../types";
import { Upload, Cpu, Target, TrendingUp } from "lucide-react";

interface RunHeaderProps {
  meta: RunMeta;
  onDataLoaded: (data: RunResult) => void;
}

const RunHeader: React.FC<RunHeaderProps> = ({ meta, onDataLoaded }) => {
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (e) => {
      try {
        const json = JSON.parse(e.target?.result as string);
        // Validate new format
        if (json.results && Array.isArray(json.results) && json.meta) {
          onDataLoaded(json as RunResult);
        } else {
          alert("Invalid file format: expected RunResult with 'results' array and 'meta' object.");
        }
      } catch (error) {
        console.error("Error parsing JSON:", error);
        alert("Failed to parse JSON file.");
      }
    };
    reader.readAsText(file);
    event.target.value = "";
  };

  const handleUploadClick = () => {
    fileInputRef.current?.click();
  };

  return (
    <div className="bg-neutral-900 border-b border-neutral-800 px-6 py-3 flex items-center justify-between shadow-md z-10 relative">
      {/* Left: Run name and architecture */}
      <div className="flex items-center gap-4">
        <h1 className="text-lg font-semibold text-neutral-100">
          {meta.name}
        </h1>
        <span className="px-2.5 py-1 rounded text-xs font-bold bg-violet-950/50 text-violet-400 uppercase tracking-wider border border-violet-900/50 flex items-center gap-1.5">
          <Cpu className="w-3 h-3" />
          {meta.architecture}
        </span>
      </div>

      {/* Center: Stats */}
      <div className="flex items-center gap-6">
        <StatBadge
          icon={<Target className="w-3.5 h-3.5" />}
          label="Tasks"
          value={`${meta.num_tasks}`}
        />
        <StatBadge
          icon={<TrendingUp className="w-3.5 h-3.5" />}
          label="Avg Score"
          value={meta.avg_score.toFixed(2)}
          highlight={meta.avg_score >= 0.8}
        />
        <StatBadge
          icon={null}
          label="Total"
          value={meta.total_score.toFixed(1)}
        />
      </div>

      {/* Right: Upload button */}
      <div>
        <input
          type="file"
          accept=".json"
          ref={fileInputRef}
          className="hidden"
          onChange={handleFileChange}
        />
        <button
          onClick={handleUploadClick}
          className="flex items-center gap-2 px-3 py-2 bg-neutral-800 hover:bg-neutral-700 text-neutral-200 rounded border border-neutral-700 transition-colors text-sm font-medium"
        >
          <Upload className="w-4 h-4" />
          Upload Run
        </button>
      </div>
    </div>
  );
};

const StatBadge: React.FC<{
  icon: React.ReactNode;
  label: string;
  value: string;
  highlight?: boolean;
}> = ({ icon, label, value, highlight }) => (
  <div className="flex items-center gap-2">
    {icon && <span className="text-neutral-500">{icon}</span>}
    <div className="text-right">
      <div className="text-[10px] text-neutral-500 uppercase tracking-wider font-medium">
        {label}
      </div>
      <div
        className={`text-lg font-bold leading-none ${
          highlight ? "text-emerald-400" : "text-neutral-100"
        }`}
      >
        {value}
      </div>
    </div>
  </div>
);

export default RunHeader;
