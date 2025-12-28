import React, { useState, useEffect, useMemo } from "react";
import TreeVisualizer from "./components/TreeVisualizer";
import DetailPanel from "./components/DetailPanel";
import RunHeader from "./components/RunHeader";
import TaskSidebar from "./components/TaskSidebar";
import { TraceEvent, RunResult } from "./types";
import { normalizeTraceEvents, buildValidatorLookup } from "./utils";
import sampleData from "./samples/store benchmark agent traces demo.json";

const App: React.FC = () => {
  // Initialize with sample data
  const [data, setData] = useState<RunResult>(sampleData as RunResult);
  const [selectedTaskIndex, setSelectedTaskIndex] = useState<number>(0);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [sidebarCollapsed, setSidebarCollapsed] = useState<boolean>(false);

  // Get the currently selected task
  const selectedTask = data.results[selectedTaskIndex];
  
  // Normalize trace events for backward compatibility
  const normalizedTrace = useMemo(
    () => (selectedTask ? normalizeTraceEvents(selectedTask.trace) : []),
    [selectedTask]
  );
  
  // Build validator lookup
  const validatorLookup = useMemo(
    () => buildValidatorLookup(normalizedTrace),
    [normalizedTrace]
  );
  
  // Find selected node in current task's trace
  const selectedNode = normalizedTrace.find((n) => n.node_id === selectedNodeId) || null;
  
  // Find validator for selected node
  const selectedValidator = selectedNode && selectedNodeId 
    ? validatorLookup.get(selectedNodeId) || null 
    : null;

  const handleSelectNode = (node: TraceEvent) => {
    setSelectedNodeId(node.node_id);
  };

  const handleSelectTask = (index: number) => {
    setSelectedTaskIndex(index);
    setSelectedNodeId(null); // Reset node selection when switching tasks
  };

  const handleDataLoaded = (newData: RunResult) => {
    setData(newData);
    setSelectedTaskIndex(0);
    setSelectedNodeId(null);
  };

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setSelectedNodeId(null);
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  return (
    <div className="flex flex-col h-screen bg-neutral-950 text-neutral-200">
      <RunHeader meta={data.meta} />

      <div className="flex-1 flex overflow-hidden">
        {/* Left Sidebar - Task List */}
        <TaskSidebar
          tasks={data.results}
          meta={data.meta}
          selectedTaskIndex={selectedTaskIndex}
          onSelectTask={handleSelectTask}
          isCollapsed={sidebarCollapsed}
          onToggleCollapse={() => setSidebarCollapsed(!sidebarCollapsed)}
          onFileLoaded={handleDataLoaded}
        />

        {/* Main Content - Tree Visualizer */}
        <div className="flex-1 relative bg-black">
          {selectedTask && (
            <TreeVisualizer
              data={normalizedTrace}
              onSelectNode={handleSelectNode}
              selectedNodeId={selectedNodeId}
              onBackgroundClick={() => setSelectedNodeId(null)}
            />
          )}
        </div>

        {/* Right Panel - Node Details */}
        <div
          className={`transition-all duration-300 ease-in-out ${
            selectedNode ? "w-[500px]" : "w-0"
          } flex-shrink-0 border-l border-neutral-800 overflow-hidden`}
        >
          <DetailPanel node={selectedNode} validator={selectedValidator} />
        </div>
      </div>
    </div>
  );
};

export default App;
