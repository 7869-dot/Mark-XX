/** The human behind the agents — returned by GET /users/me. */
export type User = {
  id: string;
  name: string;
  email: string;
  avatar_url: string | null;
  onboarding_complete: boolean;
};

export type ApiResponse<T> = {
  success: boolean;
  data: T | null;
  error: string | { code: string; message: string } | null;
  message?: string;
  meta: { timestamp: string; agent_id: string | null };
};
