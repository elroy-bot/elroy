import { getApiClient } from './client';

export interface Memory {
  name: string;
  text: string;
  created_at: string;
}

export interface MemoryCreate {
  name: string;
  text: string;
}

export interface MemoryQuery {
  query: string;
}

export const MemoriesApi = {
  createMemory: async (memory: MemoryCreate): Promise<string> => {
    return getApiClient().post<string>('/memories', memory);
  },

  queryMemory: async (query: MemoryQuery): Promise<string> => {
    return getApiClient().post<string>('/memories/query', query);
  },

  remember: async (memory: MemoryCreate): Promise<string> => {
    return getApiClient().post<string>('/memories/remember', memory);
  }
};
