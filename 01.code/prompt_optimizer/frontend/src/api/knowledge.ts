// ==========================================================
// 知识库（RAG 检索评测）API：建库/列表/详情/删除、上传语料、批量导入、检索预览、RAG 评测
// ==========================================================
import http from './http'
import type {
  KnowledgeBase,
  RagEvaluateResult,
  RetrieveResult,
} from '@/types'

// 知识库列表
export function listKnowledgeBases() {
  return http.get<{ items: KnowledgeBase[]; total: number }, { items: KnowledgeBase[]; total: number }>('/knowledge-bases')
}

// 知识库详情（含文档列表）
export function getKnowledgeBase(id: number) {
  return http.get<KnowledgeBase, KnowledgeBase>(`/knowledge-bases/${id}`)
}

// 创建知识库
export function createKnowledgeBase(data: { name: string; description?: string }) {
  return http.post<KnowledgeBase, KnowledgeBase>('/knowledge-bases', data)
}

// 删除知识库
export function deleteKnowledgeBase(id: number) {
  return http.delete<{ id: number }, { id: number }>(`/knowledge-bases/${id}`)
}

// 上传/粘贴单篇语料（后端同步分块+嵌入）
export function addDoc(id: number, data: { title?: string; content: string }) {
  return http.post<{ doc_id: number; chunk_count: number; embed_mode: string },
    { doc_id: number; chunk_count: number; embed_mode: string }>(`/knowledge-bases/${id}/docs`, data)
}

// 批量导入多篇语料
export function addDocsBulk(id: number, docs: { title?: string; content: string }[]) {
  return http.post<{ success: number; failed: number; errors: string[] },
    { success: number; failed: number; errors: string[] }>(`/knowledge-bases/${id}/docs/bulk`, { docs })
}

// 一键导入示例语料库目录
export function importCorpus(id: number, dir?: string) {
  return http.post<{ success: number; failed: number; total: number; errors: string[] },
    { success: number; failed: number; total: number; errors: string[] }>(
    `/knowledge-bases/${id}/import-corpus`, { dir: dir ?? '' })
}

// 检索预览：query → top-k 命中块
export function retrieve(id: number, query: string, topK = 4) {
  return http.post<RetrieveResult, RetrieveResult>(`/knowledge-bases/${id}/retrieve`, {
    query, top_k: topK,
  })
}

// RAG 检索+生成评测：答案 + 来源支撑度 + 忠实度
export function evaluate(id: number, data: { query: string; top_k?: number; model?: string }) {
  return http.post<RagEvaluateResult, RagEvaluateResult>(`/knowledge-bases/${id}/evaluate`, data)
}