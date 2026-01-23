import api from '../../../services/api';

export interface Document {
  id: number;
  name: string;
  source_type: string;
  source_url?: string;
  version: string;
  created_at: string;
  updated_at: string;
}

export interface DocumentListResponse {
  documents: Document[];
  total: number;
}

export interface ImportDocumentRequest {
  importType: 'file' | 'url';
  sourceType: string;
  name: string;
  version: string;
  autoParse: boolean;
  file?: File;
  url?: string;
  project_id?: number;
  version_id?: number;
}

export interface ImportDocumentResponse {
  document: Document;
  endpoints_count: number;
}

/**
 * 获取文档列表
 */
export const getDocuments = async (params?: {
  skip?: number;
  limit?: number;
  project_id?: number;
  version_id?: number;
}): Promise<DocumentListResponse> => {
  const response = await api.get('/api-integration/documents', { params });
  return response.data;
};

/**
 * 获取文档详情
 */
export const getDocument = async (id: number): Promise<Document> => {
  const response = await api.get(`/api-integration/documents/${id}`);
  return response.data;
};

/**
 * 导入文档
 */
export const importDocument = async (data: ImportDocumentRequest): Promise<ImportDocumentResponse> => {
  const formData = new FormData();

  formData.append('source_type', data.sourceType);
  formData.append('name', data.name);
  formData.append('version', data.version);
  formData.append('auto_parse', String(data.autoParse));

  if (data.project_id !== undefined) {
    formData.append('project_id', String(data.project_id));
  }

  if (data.version_id !== undefined) {
    formData.append('version_id', String(data.version_id));
  }

  if (data.importType === 'file' && data.file) {
    formData.append('file', data.file);
  } else if (data.importType === 'url' && data.url) {
    formData.append('source_url', data.url);
  }

  const response = await api.post('/api-integration/documents/import', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });

  return response.data;
};

/**
 * 删除文档
 */
export const deleteDocument = async (id: number): Promise<void> => {
  await api.delete(`/api-integration/documents/${id}`);
};

/**
 * 解析文档
 */
export const parseDocument = async (id: number): Promise<{ document_id: number; endpoints_count: number }> => {
  const response = await api.post(`/api-integration/documents/${id}/parse`);
  return response.data;
};

/**
 * 获取文档版本历史
 */
export const getDocumentVersions = async (id: number): Promise<{ versions: Document[]; total: number }> => {
  const response = await api.get(`/api-integration/documents/${id}/versions`);
  return response.data;
};

/**
 * 创建文档新版本
 */
export const createDocumentVersion = async (id: number, version: string): Promise<Document> => {
  const response = await api.post(`/api-integration/documents/${id}/versions`, { version });
  return response.data;
};

/**
 * 对比文档版本
 */
export const compareDocumentVersions = async (id: number, versionId: number): Promise<{ data: any }> => {
  const response = await api.get(`/api-integration/documents/${id}/versions/${versionId}/compare`);
  return response.data;
};

/**
 * 回滚文档版本
 */
export const rollbackDocumentVersion = async (id: number, versionId: number): Promise<Document> => {
  const response = await api.post(`/api-integration/documents/${id}/versions/${versionId}/rollback`);
  return response.data;
};