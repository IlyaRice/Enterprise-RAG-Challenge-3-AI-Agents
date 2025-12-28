import React, { useState, useEffect, useRef } from "react";
import { TaskResult, RunMeta, RunResult } from "../types";
import {
  ChevronLeft,
  ChevronRight,
  ChevronDown,
  ChevronUp,
  CheckCircle,
  XCircle,
  Clock,
  Calendar,
  Layers,
  FolderOpen,
  List,
  Folder,
} from "lucide-react";
import FileBrowser, { FileInfo } from "./FileBrowser";

type SidebarTab = "tasks" | "files";

interface TaskSidebarProps {
  tasks: TaskResult[];
  meta: RunMeta;
  selectedTaskIndex: number;
  onSelectTask: (index: number) => void;
  isCollapsed: boolean;
  onToggleCollapse: () => void;
  onFileLoaded: (data: RunResult) => void;
}

const TaskSidebar: React.FC<TaskSidebarProps> = ({
  tasks,
  meta,
  selectedTaskIndex,
  onSelectTask,
  isCollapsed,
  onToggleCollapse,
  onFileLoaded,
}) => {
  const [isMetaExpanded, setIsMetaExpanded] = useState(false);
  const [activeTab, setActiveTab] = useState<SidebarTab>("tasks");
  
  // FileBrowser state - lifted up to persist across tab switches
  const [dirHandle, setDirHandle] = useState<FileSystemDirectoryHandle | null>(null);
  const [files, setFiles] = useState<FileInfo[]>([]);
  const [folderName, setFolderName] = useState<string>("");
  const [selectedFileIndex, setSelectedFileIndex] = useState<number>(0);

  // Hover state for eval_logs tooltip (similar to TreeVisualizer)
  const [hoveredTask, setHoveredTask] = useState<{ task: TaskResult; x: number; y: number } | null>(null);
  const hideTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const sidebarRef = useRef<HTMLDivElement>(null);

  // Helper to clear any pending hide timeout
  const clearHideTimeout = () => {
    if (hideTimeoutRef.current) {
      clearTimeout(hideTimeoutRef.current);
      hideTimeoutRef.current = null;
    }
  };

  // Helper to schedule hiding the tooltip with a small delay
  const scheduleHide = () => {
    clearHideTimeout();
    hideTimeoutRef.current = setTimeout(() => {
      setHoveredTask(null);
    }, 300); // 300ms delay to allow moving to tooltip
  };

  // Cleanup timeout on unmount
  useEffect(() => {
    return () => clearHideTimeout();
  }, []);

  // Keyboard navigation for tasks and files
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Only handle arrow keys when sidebar is focused or no input element is focused
      if (document.activeElement?.tagName === 'INPUT' || document.activeElement?.tagName === 'TEXTAREA') {
        return;
      }

      if (activeTab === "tasks") {
        if (e.key === "ArrowDown") {
          e.preventDefault();
          const nextIndex = Math.min(selectedTaskIndex + 1, tasks.length - 1);
          if (nextIndex !== selectedTaskIndex) {
            onSelectTask(nextIndex);
          }
        } else if (e.key === "ArrowUp") {
          e.preventDefault();
          const prevIndex = Math.max(selectedTaskIndex - 1, 0);
          if (prevIndex !== selectedTaskIndex) {
            onSelectTask(prevIndex);
          }
        }
      } else if (activeTab === "files" && files.length > 0) {
        if (e.key === "ArrowDown") {
          e.preventDefault();
          const nextIndex = Math.min(selectedFileIndex + 1, files.length - 1);
          setSelectedFileIndex(nextIndex);
        } else if (e.key === "ArrowUp") {
          e.preventDefault();
          const prevIndex = Math.max(selectedFileIndex - 1, 0);
          setSelectedFileIndex(prevIndex);
        } else if (e.key === "Enter") {
          e.preventDefault();
          // Load the currently selected file
          const selectedFile = files[selectedFileIndex];
          if (selectedFile) {
            handleFileLoaded(selectedFile);
          }
        }
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [activeTab, selectedTaskIndex, tasks.length, onSelectTask, files, selectedFileIndex]);

  const handleFileLoaded = async (fileInfo: FileInfo) => {
    try {
      const file = await fileInfo.handle.getFile();
      const text = await file.text();
      const data = JSON.parse(text) as RunResult;
      onFileLoaded(data);
    } catch (e) {
      console.error("Failed to load file:", e);
    }
  };

  const getStatusIcon = (code: TaskResult["code"]) => {
    switch (code) {
      case "completed":
        return <CheckCircle className="w-3.5 h-3.5 text-emerald-500" />;
      case "refused":
        return <XCircle className="w-3.5 h-3.5 text-rose-500" />;
      case "timeout":
        return <Clock className="w-3.5 h-3.5 text-amber-500" />;
    }
  };

  const formatTimestamp = (iso: string) => {
    const date = new Date(iso);
    return date.toLocaleString("en-US", {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  const truncateText = (text: string, maxLength: number) => {
    if (text.length <= maxLength) return text;
    return text.slice(0, maxLength).trim() + "…";
  };

  const handleFileLoadedFromBrowser = (data: RunResult, _fileName: string) => {
    onFileLoaded(data);
    // Keep user on Files tab for quick file browsing
  };

  // Collapsed state - just show toggle button
  if (isCollapsed) {
    return (
      <div className="h-full flex flex-col bg-neutral-900 border-r border-neutral-800">
        <button
          onClick={onToggleCollapse}
          className="p-3 hover:bg-neutral-800 transition-colors"
          title="Expand sidebar"
        >
          <ChevronRight className="w-5 h-5 text-neutral-400" />
        </button>
      </div>
    );
  }

  return (
    <div ref={sidebarRef} className="h-full flex flex-col bg-neutral-900 border-r border-neutral-800 w-72 flex-shrink-0 relative">
      {/* Header with tabs and collapse button */}
      <div className="flex items-center justify-between px-2 py-2 border-b border-neutral-800">
        {/* Tab buttons */}
        <div className="flex items-center gap-1">
          <button
            onClick={() => setActiveTab("tasks")}
            className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded text-xs font-medium transition-colors ${
              activeTab === "tasks"
                ? "bg-neutral-800 text-neutral-200"
                : "text-neutral-500 hover:text-neutral-300 hover:bg-neutral-800/50"
            }`}
          >
            <List className="w-3.5 h-3.5" />
            Tasks
          </button>
          <button
            onClick={() => setActiveTab("files")}
            className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded text-xs font-medium transition-colors ${
              activeTab === "files"
                ? "bg-neutral-800 text-neutral-200"
                : "text-neutral-500 hover:text-neutral-300 hover:bg-neutral-800/50"
            }`}
          >
            <Folder className="w-3.5 h-3.5" />
            Files
          </button>
        </div>

        {/* Collapse button */}
        <button
          onClick={onToggleCollapse}
          className="p-1 hover:bg-neutral-800 rounded transition-colors"
          title="Collapse sidebar"
        >
          <ChevronLeft className="w-4 h-4 text-neutral-400" />
        </button>
      </div>

      {/* Tab Content */}
      {activeTab === "tasks" ? (
        <>
          {/* Run Metadata Section (Collapsible) */}
          <div className="border-b border-neutral-800">
            <button
              onClick={() => setIsMetaExpanded(!isMetaExpanded)}
              className="w-full flex items-center justify-between px-4 py-2.5 hover:bg-neutral-800/50 transition-colors"
            >
              <span className="text-xs font-medium text-neutral-500">
                Run Details
              </span>
              {isMetaExpanded ? (
                <ChevronUp className="w-3.5 h-3.5 text-neutral-500" />
              ) : (
                <ChevronDown className="w-3.5 h-3.5 text-neutral-500" />
              )}
            </button>

            {isMetaExpanded && (
              <div className="px-4 pb-3 space-y-2 animate-in fade-in slide-in-from-top-1 duration-150">
                <MetaItem
                  icon={<Calendar className="w-3.5 h-3.5" />}
                  label="Started"
                  value={formatTimestamp(meta.started_at)}
                />
                <MetaItem
                  icon={<FolderOpen className="w-3.5 h-3.5" />}
                  label="Workspace"
                  value={meta.workspace}
                />
                <MetaItem
                  icon={<Layers className="w-3.5 h-3.5" />}
                  label="Benchmark"
                  value={meta.benchmark}
                />
                {meta.session_id && (
                  <MetaItem
                    icon={null}
                    label="Session"
                    value={meta.session_id}
                    mono
                  />
                )}
              </div>
            )}
          </div>

          {/* Task List */}
          <div className="flex-1 overflow-y-auto scrollbar-thin scrollbar-thumb-neutral-700 scrollbar-track-transparent">
            {tasks.map((task, index) => {
              const isSelected = index === selectedTaskIndex;
              return (
                <button
                  key={task.task_id}
                  onClick={() => onSelectTask(index)}
                  className={`w-full text-left px-4 py-3 border-b border-neutral-800/50 transition-colors ${
                    isSelected
                      ? "bg-neutral-800 border-l-2 border-l-blue-500"
                      : "hover:bg-neutral-800/50 border-l-2 border-l-transparent"
                  }`}
                >
                  <div className="flex items-start gap-2">
                    <span className="text-neutral-500 text-sm font-mono w-5 flex-shrink-0">
                      {index + 1}.
                    </span>
                    <div className="flex-1 min-w-0">
                      <p
                        className={`text-sm leading-snug ${
                          isSelected ? "text-neutral-100" : "text-neutral-300"
                        }`}
                      >
                        {truncateText(task.task_text, 50)}
                      </p>
                      <div className="flex items-center gap-2 mt-1.5">
                        <span
                          onMouseEnter={(e) => {
                            clearHideTimeout();
                            const rect = sidebarRef.current?.getBoundingClientRect();
                            if (rect) {
                              setHoveredTask({
                                task,
                                x: e.clientX - rect.left,
                                y: e.clientY - rect.top,
                              });
                            }
                          }}
                          onMouseLeave={() => {
                            scheduleHide();
                          }}
                          className="cursor-help"
                        >
                          {getStatusIcon(task.code)}
                        </span>
                        {task.score !== null && (
                          <span
                            className={`text-xs font-medium px-1.5 py-0.5 rounded ${
                              task.score >= 0.8
                                ? "bg-emerald-950/50 text-emerald-400"
                                : task.score >= 0.5
                                ? "bg-amber-950/50 text-amber-400"
                                : "bg-rose-950/50 text-rose-400"
                            }`}
                          >
                            {task.score.toFixed(2)}
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                </button>
              );
            })}
          </div>
        </>
      ) : (
        /* Files Tab */
        <FileBrowser 
          onFileLoaded={handleFileLoadedFromBrowser}
          dirHandle={dirHandle}
          setDirHandle={setDirHandle}
          files={files}
          setFiles={setFiles}
          folderName={folderName}
          setFolderName={setFolderName}
          selectedFileIndex={selectedFileIndex}
          setSelectedFileIndex={setSelectedFileIndex}
        />
      )}

      {/* Eval logs tooltip */}
      {hoveredTask && (() => {
        const sidebarHeight = sidebarRef.current?.clientHeight || 0;
        const sidebarWidth = sidebarRef.current?.clientWidth || 0;
        
        // Estimate tooltip dimensions
        const tooltipWidth = 384; // max-w-md = 28rem = 448px, but we'll use a safer estimate
        const tooltipMaxHeight = 256; // max-h-64 = 16rem = 256px
        
        // Calculate position
        let left = hoveredTask.x + 20;
        let top = hoveredTask.y - 10;
        
        // Check if tooltip would overflow bottom
        if (top + tooltipMaxHeight > sidebarHeight) {
          // Position above the cursor instead
          top = hoveredTask.y - tooltipMaxHeight - 20;
          // Make sure it doesn't go above the top
          if (top < 0) {
            top = 10; // Small padding from top
          }
        }
        
        // Check if tooltip would overflow right edge
        if (left + tooltipWidth > sidebarWidth) {
          // Position to the left of cursor instead
          left = hoveredTask.x - tooltipWidth - 20;
          // Make sure it doesn't go off the left edge
          if (left < 0) {
            left = 10; // Small padding from left
          }
        }
        
        return (
          <div
            className="absolute z-50 bg-neutral-900 border border-neutral-700 rounded-lg shadow-xl p-3 max-w-md pointer-events-auto"
            style={{
              left: `${left}px`,
              top: `${top}px`,
            }}
            onMouseEnter={clearHideTimeout}
            onMouseLeave={scheduleHide}
          >
            <div className="text-xs font-bold text-neutral-400 uppercase mb-2">
              Evaluation Logs
            </div>
            {hoveredTask.task.eval_logs ? (
              <pre className="font-mono text-xs bg-neutral-950 p-2 rounded border border-neutral-800 text-neutral-300 overflow-auto max-h-64 whitespace-pre-wrap break-words">
                {hoveredTask.task.eval_logs}
              </pre>
            ) : (
              <div className="text-xs text-neutral-500 italic">
                No evaluation logs available
              </div>
            )}
          </div>
        );
      })()}
    </div>
  );
};

const MetaItem: React.FC<{
  icon: React.ReactNode;
  label: string;
  value: string;
  mono?: boolean;
}> = ({ icon, label, value, mono }) => (
  <div className="flex items-center gap-2 text-xs">
    {icon && <span className="text-neutral-500">{icon}</span>}
    <span className="text-neutral-500">{label}:</span>
    <span
      className={`text-neutral-300 truncate ${mono ? "font-mono text-[11px]" : ""}`}
      title={value}
    >
      {value}
    </span>
  </div>
);

export default TaskSidebar;
