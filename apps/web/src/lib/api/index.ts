// Re-export from client for convenience
export { api as default, apiClient, APIClient, apiCache } from './client';
export type { APIClientConfig } from './client';

// Re-export all API modules
export * from './achievements';
export * from './email';
export * from './fantrax';
export * from './onboarding';
export * from './prospects';
export * from './recommendations';
export * from './subscriptions';
export * from './watchlist';