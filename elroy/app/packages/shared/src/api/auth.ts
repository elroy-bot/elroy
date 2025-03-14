import { getApiClient } from './client';

export interface LoginRequest {
  username: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
}

export interface UserCreate {
  username: string;
  password: string;
}

export interface User {
  username: string;
  disabled?: boolean;
}

export const AuthApi = {
  login: async (credentials: LoginRequest): Promise<TokenResponse> => {
    // For login, we need to use form data instead of JSON
    const formData = new URLSearchParams();
    formData.append('username', credentials.username);
    formData.append('password', credentials.password);

    const response = await fetch(`${getApiClient().getBaseUrl()}/token`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
      body: formData.toString(),
    });

    if (!response.ok) {
      throw new Error(`Login failed: ${response.statusText}`);
    }

    const data = await response.json();
    // Store the token in the API client
    getApiClient().setToken(data.access_token);
    return data;
  },

  register: async (user: UserCreate): Promise<User> => {
    return getApiClient().post<User>('/users', user);
  },

  logout: (): void => {
    getApiClient().clearToken();
  },

  isAuthenticated: (): boolean => {
    return getApiClient().getToken() !== null;
  }
};
