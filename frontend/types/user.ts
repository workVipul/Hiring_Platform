export interface AuthUser {
  userId: number;
  userName: string;
  token: string;
  accessType: "admin" | "normal";
}

export interface LoginResponse {
  access_token: string;
  token_type: "bearer";
  user_name: string;
  user_id: number;
  access_type: "admin" | "normal";
}
