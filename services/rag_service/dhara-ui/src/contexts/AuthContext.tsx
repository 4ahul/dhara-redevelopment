"use client";

import React, { createContext, useContext, useState, useEffect, useCallback } from "react";

interface User {
  id: number;
  email: string;
  username: string;
  full_name: string | null;
  avatar_url: string | null;
  is_verified: boolean;
}

interface AuthContextType {
  user: User | null;
  token: string | null;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, full_name: string) => Promise<void>;
  logout: () => void;
  googleLogin: () => Promise<void>;
  githubLogin: () => Promise<void>;
  handleOAuthCallback: (provider: string, code: string, state: string) => Promise<void>;
  verifyEmail: (token: string) => Promise<void>;
  forgotPassword: (email: string) => Promise<void>;
  resetPassword: (token: string, newPassword: string) => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

const API_URL = process.env.NEXT_PUBLIC_API_URL 
  ? `${process.env.NEXT_PUBLIC_API_URL}/api`
  : "http://localhost:8000/api";

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const storedToken = localStorage.getItem("auth_token");
    if (storedToken) {
      setToken(storedToken);
      fetchUser(storedToken);
    } else {
      setIsLoading(false);
    }
  }, []);

  const fetchUser = async (authToken: string) => {
    try {
      const response = await fetch(`${API_URL}/auth/me`, {
        headers: { Authorization: `Bearer ${authToken}` },
      });
      if (response.ok) {
        const userData = await response.json();
        setUser(userData);
      } else {
        localStorage.removeItem("auth_token");
        setToken(null);
      }
    } catch {
      localStorage.removeItem("auth_token");
      setToken(null);
    } finally {
      setIsLoading(false);
    }
  };

  const login = useCallback(async (email: string, password: string) => {
    const response = await fetch(`${API_URL}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || "Login failed");
    }

    const data = await response.json();
    if (data.requires_verification) {
      throw new Error("Please verify your email first. Check your inbox for the verification link.");
    }

    setToken(data.access_token);
    setUser(data.user);
    localStorage.setItem("auth_token", data.access_token);
    localStorage.setItem("access_token", data.access_token); // For chat page compatibility
  }, []);

  const register = useCallback(async (email: string, password: string, full_name: string) => {
    const response = await fetch(`${API_URL}/auth/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password, full_name }),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || "Registration failed");
    }
  }, []);

  const logout = useCallback(() => {
    setUser(null);
    setToken(null);
    localStorage.removeItem("auth_token");
  }, []);

  const googleLogin = useCallback(async () => {
    const response = await fetch(`${API_URL}/auth/google`);
    if (!response.ok) throw new Error("Google login not available");
    const data = await response.json();
    window.location.href = data.url;
  }, []);

  const githubLogin = useCallback(async () => {
    const response = await fetch(`${API_URL}/auth/github`);
    if (!response.ok) throw new Error("GitHub login not available");
    const data = await response.json();
    window.location.href = data.url;
  }, []);

  const handleOAuthCallback = useCallback(async (provider: string, code: string, state: string) => {
    const endpoint = provider === "google" ? "/auth/google/callback" : "/auth/github/callback";
    const response = await fetch(`${API_URL}${endpoint}`, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({ code, state }),
    });

    if (!response.ok) {
      throw new Error(`${provider} login failed`);
    }

    const data = await response.json();
    setToken(data.access_token);
    setUser(data.user);
    localStorage.setItem("auth_token", data.access_token);
  }, []);

  const verifyEmail = useCallback(async (token: string) => {
    const response = await fetch(`${API_URL}/auth/verify?token=${token}`);
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || "Verification failed");
    }
  }, []);

  const forgotPassword = useCallback(async (email: string) => {
    const formData = new URLSearchParams();
    formData.append("email", email);
    
    const response = await fetch(`${API_URL}/auth/forgot-password`, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: formData,
    });

    if (!response.ok) {
      throw new Error("Failed to send reset email");
    }
  }, []);

  const resetPassword = useCallback(async (token: string, newPassword: string) => {
    const formData = new URLSearchParams();
    formData.append("token", token);
    formData.append("new_password", newPassword);

    const response = await fetch(`${API_URL}/auth/reset-password`, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: formData,
    });

    if (!response.ok) {
      throw new Error("Password reset failed");
    }
  }, []);

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        isLoading,
        login,
        register,
        logout,
        googleLogin,
        githubLogin,
        handleOAuthCallback,
        verifyEmail,
        forgotPassword,
        resetPassword,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
