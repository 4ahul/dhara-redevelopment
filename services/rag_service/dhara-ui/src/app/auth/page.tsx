"use client";

import { useState, useEffect, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "@/contexts/AuthContext";
import { cn } from "@/lib/utils";
import {
  Building2,
  Mail,
  Lock,
  User,
  Loader2,
  Eye,
  EyeOff,
  ArrowLeft,
  Chrome,
  Github,
  CheckCircle,
  AlertCircle,
  Shield,
  Sparkles,
  MessageSquare,
  FileSearch,
} from "lucide-react";

type AuthMode = "login" | "register" | "forgot" | "reset" | "verify";

function AuthContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { user, isLoading, login, register, logout, googleLogin, githubLogin, handleOAuthCallback, verifyEmail, forgotPassword, resetPassword } = useAuth();

  const [mode, setMode] = useState<AuthMode>("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [verificationToken, setVerificationToken] = useState("");

  useEffect(() => {
    const token = searchParams.get("token");
    const provider = searchParams.get("provider");
    const code = searchParams.get("code");
    const state = searchParams.get("state");

    if (token && mode !== "verify") {
      setVerificationToken(token);
      setMode("verify");
      handleVerify(token);
    } else if (provider && code && state) {
      handleOAuthCallback(provider, code, state).then(() => {
        router.push("/chat");
      });
    }
  }, [searchParams, mode]);

  useEffect(() => {
    if (user && !isLoading) {
      router.push("/chat");
    }
  }, [user, isLoading, router]);

  const handleVerify = async (token: string) => {
    try {
      setIsSubmitting(true);
      await verifyEmail(token);
      setSuccess("Email verified successfully! You can now login.");
      setMode("login");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Verification failed");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccess(null);
    setIsSubmitting(true);

    try {
      switch (mode) {
        case "login":
          await login(email, password);
          router.push("/chat");
          break;
        case "register":
          await register(email, password, fullName);
          setSuccess("Account created! Check your email to verify your account.");
          setMode("login");
          break;
        case "forgot":
          await forgotPassword(email);
          setSuccess("Password reset link sent to your email.");
          setMode("login");
          break;
        case "reset":
          if (verificationToken) {
            await resetPassword(verificationToken, password);
            setSuccess("Password reset successfully! You can now login.");
            setMode("login");
          }
          break;
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "An error occurred");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleOAuth = async (provider: "google" | "github") => {
    setError(null);
    try {
      if (provider === "google") {
        await googleLogin();
      } else {
        await githubLogin();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "OAuth not configured");
    }
  };

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-zinc-950">
        <Loader2 className="w-8 h-8 animate-spin text-blue-500" />
      </div>
    );
  }

  return (
    <div className="min-h-screen flex bg-zinc-950">
      <div className="hidden lg:flex lg:w-1/2 bg-gradient-to-br from-blue-600 via-blue-700 to-indigo-900 p-12 flex-col justify-between relative overflow-hidden">
        <div className="absolute inset-0 bg-[url('data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNjAiIGhlaWdodD0iNjAiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+PGRlZnM+PHBhdHRlcm4gaWQ9ImdyaWQiIHdpZHRoPSI2MCIgaGVpZ2h0PSI2MCIgcGF0dGVyblVuaXRzPSJ1c2VyU3BhY2VPblVzZSI+PHBhdGggZD0iTSA2MCAwIEwgMCAwIDAgNjAiIGZpbGw9Im5vbmUiIHN0cm9rZT0icmdiYSgyNTUsMjU1LDI1NSwwLjA1KSIgc3Ryb2tlLXdpZHRoPSIxIi8+PC9wYXR0ZXJuPjwvZGVmcz48cmVjdCB3aWR0aD0iMTAwJSIgaGVpZ2h0PSIxMDAlIiBmaWxsPSJ1cmwoI2dyaWQpIi8+PC9zdmc+')] opacity-30" />
        
        <div className="relative z-10">
          <div className="flex items-center gap-3 mb-16">
            <div className="w-12 h-12 rounded-xl bg-white/20 backdrop-blur flex items-center justify-center">
              <Building2 className="w-7 h-7 text-white" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-white">Dhara RAG</h1>
              <p className="text-blue-200">PMC Regulatory Intelligence</p>
            </div>
          </div>

          <div className="space-y-8">
            <div>
              <h2 className="text-4xl font-bold text-white mb-4 leading-tight">
                AI-Powered Regulatory<br />Compliance Assistant
              </h2>
              <p className="text-blue-100 text-lg">
                Navigate DCPR 2034 regulations with intelligent semantic search and expert guidance.
              </p>
            </div>

            <div className="space-y-4">
              <Feature icon={MessageSquare} title="Intelligent Chat" description="Ask regulatory questions in natural language" />
              <Feature icon={FileSearch} title="DCPR Search" description="Semantic search across 939 regulation chunks" />
              <Feature icon={Shield} title="Compliance Ready" description="Generate reports for regulatory submissions" />
            </div>
          </div>
        </div>

        <div className="relative z-10 flex items-center gap-3 text-blue-200">
          <Sparkles className="w-5 h-5" />
          <span className="text-sm">Powered by advanced RAG technology</span>
        </div>
      </div>

      <div className="flex-1 flex items-center justify-center p-8">
        <div className="w-full max-w-md">
          <div className="lg:hidden flex items-center gap-3 mb-8">
            <div className="w-10 h-10 rounded-lg bg-blue-600 flex items-center justify-center">
              <span className="text-xl font-bold text-white">D</span>
            </div>
            <div>
              <h1 className="text-xl font-semibold text-white">Dhara RAG</h1>
              <p className="text-sm text-zinc-400">PMC Regulatory Intelligence</p>
            </div>
          </div>

          <div className="bg-zinc-900/50 border border-zinc-800 rounded-2xl p-8">
            <div className="mb-8">
              <h2 className="text-2xl font-semibold text-white mb-2">
                {mode === "login" && "Welcome back"}
                {mode === "register" && "Create account"}
                {mode === "forgot" && "Reset password"}
                {mode === "reset" && "Set new password"}
                {mode === "verify" && "Verifying..."}
              </h2>
              <p className="text-zinc-400">
                {mode === "login" && "Sign in to continue to Dhara RAG"}
                {mode === "register" && "Get started with your free account"}
                {mode === "forgot" && "Enter your email to receive reset instructions"}
                {mode === "reset" && "Enter your new password"}
                {mode === "verify" && "Please wait while we verify your email"}
              </p>
            </div>

            {error && (
              <div className="mb-6 p-4 bg-red-500/10 border border-red-500/20 rounded-xl flex items-center gap-3 text-red-400">
                <AlertCircle className="w-5 h-5 flex-shrink-0" />
                <p className="text-sm">{error}</p>
              </div>
            )}

            {success && (
              <div className="mb-6 p-4 bg-green-500/10 border border-green-500/20 rounded-xl flex items-center gap-3 text-green-400">
                <CheckCircle className="w-5 h-5 flex-shrink-0" />
                <p className="text-sm">{success}</p>
              </div>
            )}

            {mode !== "verify" && (
              <form onSubmit={handleSubmit} className="space-y-5">
                {mode === "register" && (
                  <div className="space-y-2">
                    <label className="text-sm font-medium text-zinc-300">Full Name</label>
                    <div className="relative">
                      <User className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-zinc-500" />
                      <input
                        type="text"
                        value={fullName}
                        onChange={(e) => setFullName(e.target.value)}
                        placeholder="John Doe"
                        required
                        className="w-full pl-10 pr-4 py-2.5 bg-zinc-800 border border-zinc-700 rounded-lg text-white placeholder-zinc-500 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-colors"
                      />
                    </div>
                  </div>
                )}

                {(mode === "login" || mode === "register" || mode === "forgot") && (
                  <div className="space-y-2">
                    <label className="text-sm font-medium text-zinc-300">Email</label>
                    <div className="relative">
                      <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-zinc-500" />
                      <input
                        type="email"
                        value={email}
                        onChange={(e) => setEmail(e.target.value)}
                        placeholder="you@company.com"
                        required
                        className="w-full pl-10 pr-4 py-2.5 bg-zinc-800 border border-zinc-700 rounded-lg text-white placeholder-zinc-500 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-colors"
                      />
                    </div>
                  </div>
                )}

                {(mode === "login" || mode === "register" || mode === "reset") && (
                  <div className="space-y-2">
                    <label className="text-sm font-medium text-zinc-300">Password</label>
                    <div className="relative">
                      <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-zinc-500" />
                      <input
                        type={showPassword ? "text" : "password"}
                        value={password}
                        onChange={(e) => setPassword(e.target.value)}
                        placeholder="••••••••"
                        required
                        minLength={8}
                        className="w-full pl-10 pr-12 py-2.5 bg-zinc-800 border border-zinc-700 rounded-lg text-white placeholder-zinc-500 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-colors"
                      />
                      <button
                        type="button"
                        onClick={() => setShowPassword(!showPassword)}
                        className="absolute right-3 top-1/2 -translate-y-1/2 text-zinc-500 hover:text-zinc-300 transition-colors"
                      >
                        {showPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                      </button>
                    </div>
                  </div>
                )}

                {mode === "login" && (
                  <div className="flex justify-end">
                    <button
                      type="button"
                      onClick={() => setMode("forgot")}
                      className="text-sm text-blue-400 hover:text-blue-300 transition-colors"
                    >
                      Forgot password?
                    </button>
                  </div>
                )}

                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="w-full py-2.5 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-600/50 text-white font-medium rounded-lg transition-all duration-200 flex items-center justify-center gap-2"
                >
                  {isSubmitting ? (
                    <Loader2 className="w-5 h-5 animate-spin" />
                  ) : (
                    <>
                      {mode === "login" && "Sign In"}
                      {mode === "register" && "Create Account"}
                      {mode === "forgot" && "Send Reset Link"}
                      {mode === "reset" && "Reset Password"}
                    </>
                  )}
                </button>
              </form>
            )}

            {mode === "verify" && isSubmitting && (
              <div className="flex justify-center py-4">
                <Loader2 className="w-8 h-8 animate-spin text-blue-500" />
              </div>
            )}

            {(mode === "login" || mode === "register") && (
              <>
                <div className="relative my-6">
                  <div className="absolute inset-0 flex items-center">
                    <div className="w-full border-t border-zinc-700" />
                  </div>
                  <div className="relative flex justify-center text-sm">
                    <span className="px-4 bg-zinc-900/50 text-zinc-500">or continue with</span>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <button
                    onClick={() => handleOAuth("google")}
                    className="flex items-center justify-center gap-2 py-2.5 bg-zinc-800 hover:bg-zinc-700 border border-zinc-700 rounded-lg text-white font-medium transition-all duration-200"
                  >
                    <Chrome className="w-5 h-5" />
                    Google
                  </button>
                  <button
                    onClick={() => handleOAuth("github")}
                    className="flex items-center justify-center gap-2 py-2.5 bg-zinc-800 hover:bg-zinc-700 border border-zinc-700 rounded-lg text-white font-medium transition-all duration-200"
                  >
                    <Github className="w-5 h-5" />
                    GitHub
                  </button>
                </div>
              </>
            )}

            <div className="mt-6 text-center">
              {mode === "login" && (
                <p className="text-zinc-400">
                  Don&apos;t have an account?{" "}
                  <button
                    onClick={() => setMode("register")}
                    className="text-blue-400 hover:text-blue-300 font-medium transition-colors"
                  >
                    Sign up
                  </button>
                </p>
              )}
              {(mode === "register" || mode === "forgot" || mode === "reset") && (
                <button
                  onClick={() => setMode("login")}
                  className="text-zinc-400 hover:text-zinc-300 text-sm transition-colors inline-flex items-center gap-1"
                >
                  <ArrowLeft className="w-4 h-4" />
                  Back to login
                </button>
              )}
            </div>
          </div>

          <p className="mt-6 text-center text-xs text-zinc-500">
            By continuing, you agree to our Terms of Service and Privacy Policy
          </p>
        </div>
      </div>
    </div>
  );
}

function AuthContentFallback() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-zinc-950">
      <Loader2 className="w-8 h-8 animate-spin text-blue-500" />
    </div>
  );
}

export default function AuthPage() {
  return (
    <Suspense fallback={<AuthContentFallback />}>
      <AuthContent />
    </Suspense>
  );
}

function Feature({ icon: Icon, title, description }: { icon: React.ElementType; title: string; description: string }) {
  return (
    <div className="flex items-start gap-4 group">
      <div className="w-10 h-10 rounded-lg bg-white/10 backdrop-blur flex items-center justify-center flex-shrink-0 group-hover:bg-white/20 transition-colors">
        <Icon className="w-5 h-5 text-white" />
      </div>
      <div>
        <h3 className="font-medium text-white">{title}</h3>
        <p className="text-sm text-blue-100">{description}</p>
      </div>
    </div>
  );
}
