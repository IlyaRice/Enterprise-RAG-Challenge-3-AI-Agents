import React from "react";
import { RunMeta } from "../types";
import { Cpu, Target, TrendingUp } from "lucide-react";

interface RunHeaderProps {
  meta: RunMeta;
}

const RunHeader: React.FC<RunHeaderProps> = ({ meta }) => {

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
