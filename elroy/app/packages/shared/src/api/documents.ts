import { getApiClient } from './client';

export interface DocIngestRequest {
  address: string;
  force_refresh?: boolean;
}

export interface DocIngestDirRequest {
  address: string;
  include: string[];
  exclude: string[];
  recursive: boolean;
  force_refresh?: boolean;
}

export interface DocIngestResult {
  success: boolean;
  message: string;
  document_name?: string;
  document_size?: number;
  chunks_created?: number;
}

export const DocumentsApi = {
  ingestDocument: async (request: DocIngestRequest): Promise<DocIngestResult> => {
    return getApiClient().post<DocIngestResult>('/documents/ingest', request);
  },

  ingestDirectory: async (request: DocIngestDirRequest): Promise<Record<string, number>> => {
    return getApiClient().post<Record<string, number>>('/documents/ingest-dir', request);
  },

  uploadDocument: async (file: File, force_refresh: boolean = false): Promise<DocIngestResult> => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('force_refresh', String(force_refresh));

    return getApiClient().post<DocIngestResult>('/documents/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
  }
};
