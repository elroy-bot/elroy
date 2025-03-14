export * from './client';
export * from './auth';
export * from './goals';
export * from './memories';
export * from './messages';
export * from './documents';

// Re-export all API services as a single object
import { AuthApi } from './auth';
import { GoalsApi } from './goals';
import { MemoriesApi } from './memories';
import { MessagesApi } from './messages';
import { DocumentsApi } from './documents';
import { getApiClient } from './client';

export const Api = {
  Auth: AuthApi,
  Goals: GoalsApi,
  Memories: MemoriesApi,
  Messages: MessagesApi,
  Documents: DocumentsApi,
  getApiClient: () => getApiClient(),
};
