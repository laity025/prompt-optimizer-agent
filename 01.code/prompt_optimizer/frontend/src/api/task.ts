// ==========================================================
// 任务 / 用例 / 迭代 / 版本 / 报告 / 模板 / 模型 接口
// ==========================================================
import http from './http'
import type {
  BenchmarkList,
  BenchmarkReport,
  BenchmarkStartResult,
  ImportResult,
  IterationStatus,
  ModelInfo,
  PageResult,
  ReportData,
  ScoreCurve,
  StartIterationResult,
  Task,
  TaskCreateParams,
  TaskListItem,
  TaskTemplate,
  TestCase,
  Variant,
  Version,
  EvalResult,
} from '@/types'

// ---------- 任务 ----------
// 创建任务
export function createTask(data: TaskCreateParams) {
  return http.post<Task, Task>('/tasks', data)
}
// 任务列表（分页 + 状态筛选 + 关键词搜索）
export function listTasks(params: {
  page?: number
  page_size?: number
  status?: string
  keyword?: string
}) {
  return http.get<PageResult<TaskListItem>, PageResult<TaskListItem>>('/tasks', { params })
}
// 任务详情
export function getTask(id: number) {
  return http.get<Task, Task>(`/tasks/${id}`)
}
// 更新任务
export function updateTask(id: number, data: Partial<TaskCreateParams>) {
  return http.put<Task, Task>(`/tasks/${id}`, data)
}
// 删除任务（级联删除）
export function deleteTask(id: number) {
  return http.delete(`/tasks/${id}`)
}
// 获取最优提示词
export function getBestPrompt(id: number) {
  return http.get<{ task_id: number; best_prompt?: string | null; best_score?: number | null }>(
    `/tasks/${id}/best`,
  )
}

// ---------- 测试用例 ----------
// 用例列表
export function listCases(taskId: number, params?: { page?: number; page_size?: number }) {
  return http.get<PageResult<TestCase>, PageResult<TestCase>>(`/tasks/${taskId}/cases`, { params })
}
// 添加单条用例
export function addCase(taskId: number, data: { input_text: string; reference_output?: string; keywords?: string[]; run_test?: string }) {
  return http.post<TestCase, TestCase>(`/tasks/${taskId}/cases`, data)
}
// 批量导入用例（JSON/CSV 文件）
export function importCases(taskId: number, file: File) {
  const formData = new FormData()
  formData.append('file', file)
  return http.post<ImportResult, ImportResult>(`/tasks/${taskId}/cases/import`, formData)
}
// 删除用例
export function deleteCase(taskId: number, caseId: number) {
  return http.delete(`/tasks/${taskId}/cases/${caseId}`)
}

// ---------- 迭代 ----------
// 开始迭代（异步执行，立即返回）
export function startIteration(taskId: number) {
  return http.post<StartIterationResult, StartIterationResult>(`/tasks/${taskId}/iterations/start`)
}
// 停止迭代
export function stopIteration(taskId: number) {
  return http.post<{ task_status: string }, { task_status: string }>(`/tasks/${taskId}/iterations/stop`)
}
// 查询迭代进度（前端每 1.5s 轮询）
export function getIterationStatus(taskId: number) {
  return http.get<IterationStatus, IterationStatus>(`/tasks/${taskId}/iterations/status`)
}
// 某轮变体列表
export function getRoundVariants(taskId: number, round: number) {
  return http.get<Variant[], Variant[]>(`/tasks/${taskId}/iterations/${round}/variants`)
}
// 得分曲线
export function getScoreCurve(taskId: number, round: number) {
  return http.get<ScoreCurve, ScoreCurve>(`/tasks/${taskId}/iterations/${round}/scores`)
}
// 评估结果明细（变体 × 用例）
export function getEvalResults(taskId: number, round: number) {
  return http.get<PageResult<EvalResult>, PageResult<EvalResult>>(
    `/tasks/${taskId}/iterations/${round}/eval-results`,
  )
}
// 人工抽检评分
export function reviewEval(taskId: number, evalId: number, data: { manual_score: number; manual_note?: string }) {
  return http.post<Record<string, never>, Record<string, never>>(`/tasks/${taskId}/eval-results/${evalId}/review`, data)
}

// ---------- 版本 ----------
// 版本历史
export function listVersions(taskId: number) {
  return http.get<Version[], Version[]>(`/tasks/${taskId}/versions`)
}
// 冻结 / 回退版本（后端 action 通过 query 参数接收）
export function setVersionAction(taskId: number, versionId: number, action: 'freeze' | 'revert') {
  return http.post<unknown, unknown>(`/tasks/${taskId}/versions/${versionId}/freeze`, null, {
    params: { action },
  })
}

// ---------- 报告 ----------
// 获取优化报告
export function getReport(taskId: number) {
  return http.get<ReportData, ReportData>(`/tasks/${taskId}/report`)
}
// 导出报告（返回 blob 供下载）
export async function exportReport(taskId: number, format: 'markdown' | 'json' = 'markdown') {
  const resp = await http.get(`/tasks/${taskId}/report/export`, {
    params: { format },
    responseType: 'blob',
  })
  return resp as unknown as Blob
}

// ---------- 模板 / 模型 ----------
// 任务类型模板
export function getTemplates() {
  return http.get<TaskTemplate[], TaskTemplate[]>('/task-templates')
}
// 可用模型列表
export function getModels() {
  return http.get<ModelInfo[], ModelInfo[]>('/models')
}

// ---------- 多模型对比评测 ----------
// 发起评测（异步执行）
export function startBenchmark(taskId: number, data: {
  models: string[]
  prompt_mode: string
  prompt?: string
  name?: string
}) {
  return http.post<BenchmarkStartResult, BenchmarkStartResult>(`/tasks/${taskId}/benchmarks/start`, data)
}
// 评测历史列表
export function listBenchmarks(taskId: number) {
  return http.get<BenchmarkList, BenchmarkList>(`/tasks/${taskId}/benchmarks`)
}
// 我的全部评测历史（无需先选任务）
export function listAllBenchmarks() {
  return http.get<BenchmarkList, BenchmarkList>(`/benchmarks`)
}
// 评测结果详情（得分矩阵 + 各模型汇总）
export function getBenchmark(taskId: number, runId: number) {
  return http.get<BenchmarkReport, BenchmarkReport>(`/tasks/${taskId}/benchmarks/${runId}`)
}
// 导出评测报告（返回 blob 供下载）
export async function exportBenchmark(taskId: number, runId: number) {
  const resp = await http.get(`/tasks/${taskId}/benchmarks/${runId}/report`, {
    responseType: 'blob',
  })
  return resp as unknown as Blob
}