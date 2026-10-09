// ==========================================================
// 全局类型定义：与后端 Pydantic Schema 一一对应
// ==========================================================

// 统一响应包裹结构
export interface ApiResponse<T = unknown> {
  code: number
  message: string
  data: T | null
}

// 分页结果结构
export interface PageResult<T> {
  items: T[]
  total: number
  page: number
  page_size: number
}

// ---------- 用户 / 认证 ----------
export interface UserInfo {
  id: number
  email: string
  full_name?: string | null
  role: string
  is_active: number
  created_at?: string | null
}

export interface LoginData {
  token: string
  user: UserInfo
}

// ---------- 任务 ----------
export type TaskType = 'text_gen' | 'summary' | 'extraction' | 'code' | 'custom'

export interface Task {
  id: number
  user_id: number
  name: string
  task_type: TaskType
  description: string
  objective: string
  criteria: string
  execution_model: string
  judge_model: string
  auto_weight: number
  judge_weight: number
  initial_prompt?: string | null
  best_prompt?: string | null
  best_score?: number | null
  target_score?: number | null
  max_rounds: number
  variants_per_round: number
  concurrency: number
  stagnant_rounds: number
  kb_id?: number | null
  enable_rag?: number
  status: TaskStatus
  current_round: number
  last_error?: string | null
  created_at: string
  updated_at?: string | null
}

export type TaskStatus = 'pending' | 'running' | 'completed' | 'stopped' | 'failed'

export interface TaskListItem {
  id: number
  name: string
  task_type: TaskType
  case_count: number
  best_score?: number | null
  status: TaskStatus
  current_round: number
  created_at: string
}

// 创建任务请求体
export interface TaskCreateParams {
  name: string
  task_type: TaskType
  description: string
  objective: string
  criteria: string
  execution_model?: string
  judge_model?: string
  auto_weight?: number
  judge_weight?: number
  initial_prompt?: string
  target_score?: number
  max_rounds?: number
  variants_per_round?: number
  concurrency?: number
  stagnant_rounds?: number
  kb_id?: number | null
  enable_rag?: number
}

// ---------- 测试用例 ----------
export interface TestCase {
  id: number
  task_id: number
  input_text: string
  reference_output?: string | null
  keywords?: string | null
  run_test?: string | null
  sort_order: number
  created_at: string
}

export interface ImportResult {
  total: number
  success: number
  failed: number
  errors: string[]
}

// ---------- 迭代 ----------
export interface StartIterationResult {
  task_id: number
  task_status: string
  total_rounds: number
  start_round: number
  resume: boolean
}

export interface IterationStatus {
  task_id: number
  task_status: string
  current_round: number
  max_rounds: number
  current_best_score?: number | null
  variants_done: number
  variants_total: number
  cases_done: number
  cases_total: number
  cases_success: number
  cases_failed: number
  message?: string | null
}

export interface Variant {
  id: number
  variant_no: number
  prompt_text: string
  strategy_tag?: string | null
  score?: number | null
  status: string
}

export interface ScorePoint {
  round: number
  best_score: number
}

export interface ScoreCurve {
  rounds: ScorePoint[]
  target_score?: number | null
}

export interface Version {
  id: number
  version_no: number
  prompt_text: string
  is_best: number
  score?: number | null
  frozen: number
  created_at: string
}

export interface EvalResult {
  id: number
  variant_no: number
  test_case_id: number
  model_output?: string | null
  outcome: string
  error_reason?: string | null
  bleu?: number | null
  rouge?: number | null
  keyword_hit?: number | null
  format_ok?: number | null
  judge_score?: number | null
  judge_reason?: string | null
  total_score?: number | null
  manual_score?: number | null
  manual_checked: number
  manual_note?: string | null
}

// ---------- 模板 / 模型 ----------
export interface TaskTemplate {
  task_type: TaskType
  name: string
  description_template: string
  criteria_template: string
  recommended_metrics: string[]
  example_cases: Record<string, unknown>[]
}

export interface ModelInfo {
  id: string
  name: string
  description: string
  is_default?: boolean
}

// ---------- 报告 ----------
export interface ReportData {
  task_id: number
  task_name: string
  best_prompt?: string | null
  initial_prompt?: string | null
  score_curve: ScorePoint[]
  version_diffs: Record<string, unknown>[]
  judge_summary: Record<string, unknown>[]
  suggestions: string[]
}

// ---------- 多模型对比评测 ----------
export interface BenchmarkRunItem {
  id: number
  task_id?: number
  task_name?: string
  name: string
  prompt_mode: string
  models: string[]
  status: string
  best_model?: string | null
  best_score?: number | null
  created_at: string
  finished_at?: string | null
}

export interface BenchmarkModelAgg {
  model: string
  avg_score?: number | null
  success_cases: number
  failed_cases: number
  avg_keyword_hit?: number | null
}

export interface BenchmarkCell {
  model: string
  score?: number | null
  judge_score?: number | null
  judge_reason?: string | null
  output?: string | null
  error_reason?: string | null
  bleu?: number | null
  rouge?: number | null
  keyword_hit?: number | null
}

export interface BenchmarkMatrixRow {
  case_id: number
  models: BenchmarkCell[]
}

export interface BenchmarkCaseInfo {
  case_id: number
  input_text: string
  reference_output?: string | null
}

export interface BenchmarkReport {
  run: {
    id: number
    task_id: number
    name: string
    prompt_mode: string
    prompt_snapshot?: string | null
    status: string
    best_model?: string | null
    best_score?: number | null
    created_at: string
    finished_at?: string | null
  }
  models_order: string[]
  models: BenchmarkModelAgg[]
  cases: BenchmarkCaseInfo[]
  matrix: BenchmarkMatrixRow[]
}

export interface BenchmarkStartResult {
  run_id: number
  task_id: number
  status: string
  models: string[]
  models_count: number
  prompt_mode: string
}

export interface BenchmarkList {
  items: BenchmarkRunItem[]
  total: number
}

// ---------- 多步工作流（多 Agent） ----------
export interface WorkflowStep {
  id?: number
  seq: number
  name: string
  prompt_template: string
  model?: string
  output_var?: string
}

export interface Workflow {
  id: number
  task_id: number
  name: string
  description?: string | null
  created_at: string
  step_count: number
  steps?: WorkflowStep[] | null
}

export interface WorkflowRunItem {
  id: number
  name: string
  status: string
  run_baseline: number
  avg_score?: number | null
  baseline_avg_score?: number | null
  created_at: string
  finished_at?: string | null
}

export interface WorkflowStepTrace {
  seq: number
  name: string
  output_var: string
  output: string
}

export interface WorkflowReport {
  run: {
    id: number
    workflow_id: number
    task_id: number
    name: string
    status: string
    run_baseline: number
    avg_score?: number | null
    baseline_avg_score?: number | null
    created_at: string
    finished_at?: string | null
  }
  workflow: { id: number; name: string } | null
  steps: { seq: number; name: string; output_var: string; model: string }[]
  cases: {
    case_id: number
    input_text: string
    final_output?: string | null
    error_reason?: string | null
    step_trace: WorkflowStepTrace[]
    bleu?: number | null
    rouge?: number | null
    keyword_hit?: number | null
    format_ok?: number | null
    judge_score?: number | null
    judge_reason?: string | null
    total_score?: number | null
    baseline_output?: string | null
    baseline_score?: number | null
  }[]
}

// ---------- 在线服务（Prompt 一键上线） ----------
export interface EndpointItem {
  id: number
  task_id: number
  name: string
  description?: string | null
  model: string
  active: number
  call_count: number
  created_at: string
}

export interface EndpointDetail extends EndpointItem {
  prompt: string
  task_type: string
  api_key: string
}

export interface EndpointInvokeResult {
  endpoint_id: number
  output: string
  latency_ms: number
}

export interface EndpointCallLogItem {
  id: number
  input_text?: string | null
  output?: string | null
  error_reason?: string | null
  status: string
  latency_ms?: number | null
  created_at: string
}

export interface EndpointStats {
  call_count: number
  success: number
  failed: number
  avg_latency_ms?: number | null
}

// ---------- 管理员 ----------
export interface AdminLogItem {
  id: number
  user_id?: number | null
  user_email?: string | null
  action: string
  result: string
  duration_ms?: number | null
  error_message?: string | null
  created_at: string
}

export interface AdminUserUpdateParams {
  role?: string
  is_active?: number
}

// 任务类型中文映射，用于界面展示
export const TASK_TYPE_LABEL: Record<TaskType, string> = {
  text_gen: '文本生成',
  summary: '文本摘要',
  extraction: '信息抽取',
  code: '代码生成',
  custom: '自定义',
}

// 任务状态中文映射与徽标颜色
export const TASK_STATUS_LABEL: Record<TaskStatus, string> = {
  pending: '待运行',
  running: '运行中',
  completed: '已完成',
  stopped: '已停止',
  failed: '失败',
}

// ---------- 知识库（RAG 检索评测） ----------
export interface KnowledgeBase {
  id: number
  name: string
  description?: string | null
  embed_model: string
  doc_count: number
  chunk_count: number
  created_at: string
  docs?: KnowledgeDoc[]
}

export interface KnowledgeDoc {
  id: number
  title: string
  status: string
  error?: string | null
  content?: string
  created_at?: string
}

export interface RetrieveHit {
  doc_title: string
  seq: number
  text: string
  score: number
}

export interface RetrieveResult {
  kb_id: number
  query: string
  embed_model: string
  hits: RetrieveHit[]
}

export interface RagEvaluateResult {
  query: string
  embed_model: string
  answer: string
  source_score: number
  faithfulness: { score: number; reason: string }
  retrieved: RetrieveHit[]
}

// ---------- 工作流瓶颈步骤自动迭代优化（Phase 5） ----------
export interface WorkflowOptVariant {
  id: number
  round_no: number
  variant_no: number
  strategy_tag: string
  prompt_text: string
  avg_score?: number | null
  status: string
  error_reason?: string | null
  is_best: number
}

export interface WorkflowOptItem {
  id: number
  step_seq: number
  status: string
  base_score?: number | null
  best_score?: number | null
  improved: number
  current_round: number
  max_rounds: number
  created_at: string
  finished_at?: string | null
}

export interface WorkflowOptReport {
  opt: {
    id: number
    workflow_id: number
    task_id: number
    step_seq: number
    status: string
    base_prompt: string
    best_prompt?: string | null
    base_score?: number | null
    best_score?: number | null
    improved: number
    current_round: number
    max_rounds: number
    created_at: string
    finished_at?: string | null
  }
  workflow: { id: number; name: string } | null
  step: { seq: number; name: string } | null
  variants: WorkflowOptVariant[]
}

// ---------- 资产管理门户 / 汇总仪表盘（Phase 6） ----------
export interface DashboardOverview {
  tasks: number
  cases: number
  versions: number
  endpoints: number
  calls: number
  avg_latency_ms: number
  benchmarks: number
  workflows: number
  knowledge_bases: number
  best_score_avg: number
}

export interface DashboardTrend {
  days: number
  series: Record<string, Record<string, number>>
}

export interface DashboardTaskAsset {
  id: number
  name: string
  task_type: TaskType
  status: TaskStatus
  case_count: number
  version_count: number
  benchmark_count: number
  workflow_count: number
  best_score?: number | null
  current_round: number
  max_rounds: number
  updated_at?: string | null
  created_at: string
}

export interface DashboardModelStat {
  model: string
  calls: number
  success_rate: number
  avg_latency_ms: number
}

export interface DashboardVersionItem {
  id: number
  task_id: number
  task_name: string
  version_no: number
  prompt_text: string
  is_best: number
  score?: number | null
  frozen: number
  created_at: string
}

// ---------- 报告分享（Phase 7） ----------
export type ReportShareType = 'benchmark' | 'optimization' | 'task'

export interface ReportShareItem {
  id: number
  report_type: ReportShareType
  target_id: number
  title: string
  token: string
  status: string
  expires_at?: string | null
  view_count: number
  created_at: string
  url: string
}

export interface PublicReportMeta {
  token: string
  report_type: ReportShareType
  title: string
  status: string
  expires_at?: string | null
  valid: boolean
  view_count: number
  created_at: string
}

export interface PublicReportData<T = unknown> {
  meta: PublicReportMeta
  payload: T
}

// 三种可分享报告的公开载荷类型（复用已定义报告接口）
export type PublicBenchmarkPayload = BenchmarkReport
export type PublicOptimizationPayload = WorkflowOptReport
export type PublicTaskPayload = ReportData