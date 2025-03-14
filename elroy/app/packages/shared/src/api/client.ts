import axios, { AxiosInstance, AxiosRequestConfig } from 'axios';

export interface ApiClientConfig {
  baseURL: string;
  timeout?: number;
}

export class ApiClient {
  private client: AxiosInstance;
  private token: string | null = null;
  private baseURL: string;

  constructor(config: ApiClientConfig) {
    this.baseURL = config.baseURL;
    this.client = axios.create({
      baseURL: config.baseURL,
      timeout: config.timeout || 10000,
    });

    // Add request interceptor to add auth token
    this.client.interceptors.request.use(
      (config: any) => {
        if (this.token) {
          config.headers.Authorization = `Bearer ${this.token}`;
        }
        return config;
      },
      (error: any) => Promise.reject(error)
    );
  }

  getBaseUrl(): string {
    return this.baseURL;
  }

  getToken(): string | null {
    return this.token;
  }

  setToken(token: string): void {
    this.token = token;
  }

  clearToken(): void {
    this.token = null;
  }

  async get<T>(url: string, config?: AxiosRequestConfig): Promise<T> {
    const response = await this.client.get<T>(url, config);
    return response.data;
  }

  async post<T>(url: string, data?: any, config?: AxiosRequestConfig): Promise<T> {
    const response = await this.client.post<T>(url, data, config);
    return response.data;
  }

  async put<T>(url: string, data?: any, config?: AxiosRequestConfig): Promise<T> {
    const response = await this.client.put<T>(url, data, config);
    return response.data;
  }

  async delete<T>(url: string, config?: AxiosRequestConfig): Promise<T> {
    const response = await this.client.delete<T>(url, config);
    return response.data;
  }
}

// Create a singleton instance
let apiClient: ApiClient | null = null;

export const createApiClient = (config: ApiClientConfig): ApiClient => {
  if (!apiClient) {
    apiClient = new ApiClient(config);
  }
  return apiClient;
};

export const getApiClient = (): ApiClient => {
  if (!apiClient) {
    throw new Error('API client not initialized. Call createApiClient first.');
  }
  return apiClient;
};
