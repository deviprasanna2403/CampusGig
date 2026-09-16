/**
 * Auth endpoints — shapes from apps/accounts (verified against disk):
 * register/login return the token pair + user; refresh rotates BOTH tokens;
 * logout blacklists the refresh token and returns 205.
 */

import { api } from "./client";
import type { TokenPairResponse, User } from "./types";

export interface RegisterInput {
  email: string;
  password: string;
  password_confirm: string;
  role: "student" | "business";
  phone?: string;
}

export interface LoginInput {
  email: string;
  password: string;
}

export async function register(input: RegisterInput): Promise<TokenPairResponse> {
  const { data } = await api.post<TokenPairResponse>("/auth/register/", input);
  return data;
}

export async function login(input: LoginInput): Promise<TokenPairResponse> {
  const { data } = await api.post<TokenPairResponse>("/auth/login/", input);
  return data;
}

export async function logout(refresh: string): Promise<void> {
  // 205 Reset Content — no body.
  await api.post("/auth/logout/", { refresh });
}

export async function me(): Promise<User> {
  const { data } = await api.get<User>("/auth/me/");
  return data;
}
