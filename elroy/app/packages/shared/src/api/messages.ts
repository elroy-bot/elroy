import { getApiClient } from './client';

export interface MessageRequest {
  input: string;
  enable_tools?: boolean;
}

export interface MessageResponse {
  response: string;
  timestamp: string;
}

export interface ContextRefreshResponse {
  refreshed: boolean;
  timestamp: string;
}

export interface PersonaResponse {
  persona: string;
}

export const MessagesApi = {
  sendMessage: async (message: MessageRequest): Promise<MessageResponse> => {
    return getApiClient().post<MessageResponse>('/messages', message);
  },

  streamMessage: async (message: MessageRequest): Promise<ReadableStream<Uint8Array>> => {
    const response = await fetch(`${getApiClient().getBaseUrl()}/messages/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(getApiClient().getToken() ? { 'Authorization': `Bearer ${getApiClient().getToken()}` } : {})
      },
      body: JSON.stringify(message)
    });

    if (!response.ok) {
      throw new Error(`Error streaming message: ${response.statusText}`);
    }

    return response.body!;
  },

  recordMessage: async (role: string, message: string): Promise<void> => {
    await getApiClient().post('/messages/record', { role, message });
  },

  refreshContext: async (): Promise<ContextRefreshResponse> => {
    return getApiClient().post<ContextRefreshResponse>('/messages/context/refresh');
  },

  refreshContextIfNeeded: async (): Promise<ContextRefreshResponse> => {
    return getApiClient().get<ContextRefreshResponse>('/messages/context/refresh-if-needed');
  },

  getPersona: async (): Promise<PersonaResponse> => {
    return getApiClient().get<PersonaResponse>('/messages/persona');
  }
};
