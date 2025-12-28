import React, { useState } from "react";
import { TraceEvent, ToolCall } from "../types";
import { NODE_COLORS } from "../constants";
import { ChevronDown, ChevronRight, Clock, Hash, Activity, Shield } from "lucide-react";

type DetailTab = "agent" | "validation";

interface DetailPanelProps {
  node: TraceEvent | null;
  validator?: TraceEvent | null;
  onClose?: () => void;
}

const DetailPanel: React.FC<DetailPanelProps> = ({ node, validator }) => {
  const [activeTab, setActiveTab] = useState<DetailTab>("agent");
  
  if (!node) {
    return (
      <div className="h-full flex items-center justify-center text-neutral-500 bg-neutral-900">
        <div className="text-center">
          <Activity className="w-12 h-12 mx-auto mb-2 opacity-20" />
          <p>Select a node to view details</p>
        </div>
      </div>
    );
  }

  const bgColor = NODE_COLORS[node.context];
  const hasValidator = !!validator;

  return (
    <div className="h-full flex flex-col bg-neutral-900 text-neutral-200 overflow-hidden w-[500px] max-w-full">
      {/* Header */}
      <div
        className="p-4 border-b border-neutral-800 flex-shrink-0"
        style={{ borderLeft: `6px solid ${bgColor}` }}
      >
        <div className="flex justify-between items-start mb-1">
          <h2 className="text-xl font-bold text-neutral-100">{node.context}</h2>
          <span className="text-xs font-mono bg-neutral-800 px-2 py-1 rounded text-neutral-400 border border-neutral-700">
            Node {node.node_id}
          </span>
        </div>
        <div className="flex items-center gap-4 text-xs text-neutral-500">
          <div className="flex items-center gap-1">
            <Clock className="w-3 h-3" />
            <span>{node.timing.toFixed(2)}s</span>
          </div>
          <div className="flex items-center gap-1">
            <Hash className="w-3 h-3" />
            <span>Depth {node.depth}</span>
          </div>
          {hasValidator && (
            <div className="flex items-center gap-1">
              <Shield className="w-3 h-3" />
              <span className={validator.validation_passed ? "text-emerald-400" : "text-rose-400"}>
                {validator.validation_passed ? "Validated ✅" : "Failed ❌"}
              </span>
            </div>
          )}
        </div>
      </div>

      {/* Tabs */}
      {hasValidator && (
        <div className="flex items-center gap-1 px-4 py-2 border-b border-neutral-800 bg-neutral-900/50">
          <button
            onClick={() => setActiveTab("agent")}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-medium transition-colors ${
              activeTab === "agent"
                ? "bg-neutral-800 text-neutral-200"
                : "text-neutral-500 hover:text-neutral-300 hover:bg-neutral-800/50"
            }`}
          >
            <Activity className="w-3.5 h-3.5" />
            Agent Step
          </button>
          <button
            onClick={() => setActiveTab("validation")}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-medium transition-colors ${
              activeTab === "validation"
                ? "bg-neutral-800 text-neutral-200"
                : "text-neutral-500 hover:text-neutral-300 hover:bg-neutral-800/50"
            }`}
          >
            <Shield className="w-3.5 h-3.5" />
            Validation
          </button>
        </div>
      )}

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-4 space-y-6 scrollbar-thin scrollbar-thumb-neutral-700 scrollbar-track-neutral-900">
        {activeTab === "agent" ? (
          <AgentStepContent node={node} />
        ) : (
          validator && <ValidationContent validator={validator} />
        )}
      </div>
    </div>
  );
};

// Agent Step Content Component
const AgentStepContent: React.FC<{ node: TraceEvent }> = ({ node }) => {
  return (
    <>
      {/* System Prompt (Collapsible) */}
      <CollapsibleSection title="System Prompt" defaultOpen={false}>
        <pre className="text-xs text-neutral-400 whitespace-pre-wrap bg-neutral-950 p-3 rounded border border-neutral-800 font-mono">
          {node.system_prompt}
        </pre>
      </CollapsibleSection>

      {/* Input Messages */}
      <Section title="Input Conversation">
        <div className="space-y-3">
          {node.input_messages.map((msg, idx) => (
            <div key={idx} className="text-sm">
              <span className={`font-bold text-xs uppercase tracking-wide ${msg.role === 'user' ? 'text-blue-400' : 'text-purple-400'}`}>
                {msg.role}
              </span>
              <div className="mt-1 bg-neutral-950 p-3 rounded border border-neutral-800 text-neutral-300 whitespace-pre-wrap leading-relaxed">
                {msg.content}
              </div>
            </div>
          ))}
        </div>
      </Section>

      {/* Reasoning */}
      {node.reasoning && (
        <Section title="Thinking / Reasoning">
          <div className="bg-amber-950/30 p-3 rounded border border-amber-900/50 text-amber-200 italic text-sm leading-relaxed">
            {node.reasoning}
          </div>
        </Section>
      )}

      {/* Structured Output */}
      <Section title="Decision Output">
        <JsonView data={node.output} />
      </Section>

      {/* Tool Calls / Subagent Results */}
      {node.tool_calls && node.tool_calls.length > 0 && (
        <Section title="Tool Execution">
          <div className="space-y-3">
            {node.tool_calls.map((call, idx) => (
              <ToolCallItem key={idx} call={call} index={idx} />
            ))}
          </div>
        </Section>
      )}

      {node.subagent_result && (
        <Section title="Delegation Result">
          <div className={`p-3 rounded border ${node.subagent_result.status === 'completed' ? 'bg-green-950/30 border-green-900/50' : 'bg-red-950/30 border-red-900/50'}`}>
            <div className="flex justify-between items-center mb-2">
              <span className="font-bold text-sm text-neutral-200">{node.subagent_result.subagent_name}</span>
              <span className={`text-xs px-2 py-0.5 rounded-full uppercase font-bold ${node.subagent_result.status === 'completed' ? 'bg-green-900/50 text-green-400' : 'bg-red-900/50 text-red-400'}`}>
                {node.subagent_result.status}
              </span>
            </div>
            <p className="text-sm text-neutral-300">{node.subagent_result.report}</p>
          </div>
        </Section>
      )}
    </>
  );
};

// Validation Content Component
const ValidationContent: React.FC<{ validator: TraceEvent }> = ({ validator }) => {
  return (
    <>
      {/* Validation Status */}
      <Section title="Validation Status">
        <div className={`p-4 rounded-lg border-2 ${
          validator.validation_passed 
            ? 'bg-emerald-950/30 border-emerald-600' 
            : 'bg-rose-950/30 border-rose-600'
        }`}>
          <div className="flex items-center gap-3 mb-2">
            <span className="text-3xl">
              {validator.validation_passed ? "✅" : "❌"}
            </span>
            <div>
              <h4 className={`font-bold text-lg ${
                validator.validation_passed ? 'text-emerald-400' : 'text-rose-400'
              }`}>
                {validator.validation_passed ? "Validation Passed" : "Validation Failed"}
              </h4>
              <p className="text-xs text-neutral-400">
                Validator: {validator.validator_name || validator.context}
              </p>
            </div>
          </div>
          {validator.output?.analysis && (
            <p className="text-sm text-neutral-300 mt-3 leading-relaxed">
              {validator.output.analysis}
            </p>
          )}
          {!validator.validation_passed && validator.output?.rejection_message && (
            <div className="mt-3 p-2 bg-rose-900/20 rounded border border-rose-800">
              <p className="text-xs uppercase font-bold text-rose-400 mb-1">Rejection Reason</p>
              <p className="text-sm text-rose-200">{validator.output.rejection_message}</p>
            </div>
          )}
        </div>
      </Section>

      {/* Validator System Prompt */}
      <CollapsibleSection title="Validator System Prompt" defaultOpen={false}>
        <pre className="text-xs text-neutral-400 whitespace-pre-wrap bg-neutral-950 p-3 rounded border border-neutral-800 font-mono">
          {validator.system_prompt}
        </pre>
      </CollapsibleSection>

      {/* Validator Input */}
      <Section title="Validator Input">
        <div className="space-y-3">
          {validator.input_messages.map((msg, idx) => (
            <div key={idx} className="text-sm">
              <span className={`font-bold text-xs uppercase tracking-wide ${msg.role === 'user' ? 'text-blue-400' : 'text-purple-400'}`}>
                {msg.role}
              </span>
              <div className="mt-1 bg-neutral-950 p-3 rounded border border-neutral-800 text-neutral-300 whitespace-pre-wrap leading-relaxed">
                {msg.content}
              </div>
            </div>
          ))}
        </div>
      </Section>

      {/* Validator Reasoning */}
      {validator.reasoning && (
        <Section title="Validator Reasoning">
          <div className="bg-amber-950/30 p-3 rounded border border-amber-900/50 text-amber-200 italic text-sm leading-relaxed">
            {validator.reasoning}
          </div>
        </Section>
      )}

      {/* Full Validator Output */}
      <Section title="Full Validator Output">
        <JsonView data={validator.output} />
      </Section>

      {/* Timing */}
      <Section title="Validation Timing">
        <div className="flex items-center gap-2 text-sm">
          <Clock className="w-4 h-4 text-neutral-500" />
          <span className="text-neutral-300">{validator.timing.toFixed(2)}s</span>
        </div>
      </Section>
    </>
  );
};

const Section: React.FC<{ title: string; children: React.ReactNode }> = ({ title, children }) => (
  <div>
    <h3 className="text-xs font-bold text-neutral-500 uppercase tracking-wider mb-2">{title}</h3>
    {children}
  </div>
);

const CollapsibleSection: React.FC<{ title: string; children: React.ReactNode; defaultOpen?: boolean }> = ({ title, children, defaultOpen = false }) => {
  const [isOpen, setIsOpen] = useState(defaultOpen);
  return (
    <div>
      <button 
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center w-full text-xs font-bold text-neutral-500 uppercase tracking-wider mb-2 hover:text-neutral-300 transition-colors"
      >
        {isOpen ? <ChevronDown className="w-3 h-3 mr-1" /> : <ChevronRight className="w-3 h-3 mr-1" />}
        {title}
      </button>
      {isOpen && <div className="animate-in fade-in slide-in-from-top-1 duration-200">{children}</div>}
    </div>
  );
};

const ToolCallItem: React.FC<{ call: ToolCall; index: number }> = ({ call, index }) => {
  return (
    <div className="border border-neutral-800 rounded overflow-hidden text-sm">
      <div className="bg-neutral-800 px-3 py-2 border-b border-neutral-800 flex justify-between items-center">
        <span className="font-mono font-bold text-neutral-300">{call.request.tool}</span>
        <span className="text-xs text-neutral-500">Call #{index + 1}</span>
      </div>
      <div className="p-3 bg-neutral-900 space-y-2">
        <div>
           <span className="text-xs text-neutral-500 uppercase">Input</span>
           <JsonView data={call.request} compact />
        </div>
        <div>
           <span className="text-xs text-neutral-500 uppercase">Output</span>
           <JsonView data={call.response} compact />
        </div>
      </div>
    </div>
  );
}

const JsonView: React.FC<{ data: any; compact?: boolean }> = ({ data, compact }) => {
  return (
    <pre className={`font-mono text-xs bg-neutral-950 p-2 rounded border border-neutral-800 text-neutral-300 overflow-x-auto ${compact ? 'max-h-32' : ''}`}>
      {JSON.stringify(data, null, 2)}
    </pre>
  );
};

export default DetailPanel;