export type Context =
  | "TaskAnalyzer"
  | "Orchestrator"
  | "ProductExplorer"
  | "BasketBuilder"
  | "CouponOptimizer"
  | "CheckoutProcessor"
  | "BullshitCaller";

export interface Message {
  role: "system" | "user" | "assistant";
  content: string;
}

export interface ToolCall {
  request: {
    tool: string;
    [key: string]: any;
  };
  response: {
    [key: string]: any;
  };
}

export interface SubagentResult {
  subagent_name: Context;
  status: "completed" | "refused";
  report: string;
}

export interface Call {
  call_mode: "single" | "batch";
  function?: {
    tool: string;
    [key: string]: any;
  };
  functions?: {
    tool: string;
    [key: string]: any;
  }[];
}

export interface Output {
  // TaskAnalyzer
  gotchas?: string[];
  wording_explanations?: string[];
  tldr_rephrased_task?: string;

  // Orchestrator/Subagent
  current_state?: string;
  remaining_work?: string[];
  next_action?: string;
  call?: Call;

  // BullshitCaller
  terminal_action?: "complete_task" | "refuse_task";
  analysis?: string;
  is_valid?: boolean;
  rejection_message?: string;
}

export interface TraceEvent {
  event: "llm_call" | "agent_step" | "validator_step";
  node_id: string;
  parent_node_id: string | null;
  prev_sibling_node_id: string | null;
  depth: number;
  context: Context;
  system_prompt: string;
  input_messages: Message[];
  output: Output;
  reasoning: string | null;
  timing: number;
  tool_calls?: ToolCall[];
  subagent_result?: SubagentResult;
  
  // Validator-specific fields (only present when event === "validator_step")
  validator_name?: string;
  validation_passed?: boolean;
  validates_node_id?: string;
}

export interface TaskResult {
  task_id: string;
  task_index: number;
  task_text: string;
  benchmark: string;
  code: "completed" | "refused" | "timeout";
  summary: string;
  score: number | null;
  eval_logs: string | null;
  trace: TraceEvent[];
  orchestrator_log?: Message[];
}

export interface RunMeta {
  benchmark: string;
  task_indices: number[];
  num_runs: number;
  session_id: string | null;
  total_score: number;
  num_tasks: number;
  avg_score: number;
  workspace: string;
  name: string;
  architecture: string;
  started_at: string;
}

export interface RunResult {
  results: TaskResult[];
  meta: RunMeta;
}
