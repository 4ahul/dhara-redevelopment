"use client";

import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/contexts/AuthContext";
import { cn, stripMarkdown, API_URL } from "@/lib/utils";
import {
  Building2,
  Send,
  Loader2,
  Star,
  Trash2,
  Plus,
  Search,
  Settings,
  LogOut,
  Copy,
  Check,
  ChevronDown,
  ChevronRight,
  X,
  MessageSquare,
  Square,
  PanelLeft,
  Volume2,
  MoreVertical,
  Edit3,
} from "lucide-react";

interface Message {
  id: number | string;
  role: "user" | "assistant";
  content: string;
  sources?: any[];
  clauses?: any[];
  metadata?: any;
  feedback?: string;
  edited_at?: string;
  created_at: string;
}

interface Session {
  session_id: string;
  title: string;
  is_incognito: boolean;
  is_starred: boolean;
  message_count: number;
  last_message_at: string | null;
  created_at: string;
}

export default function ChatPage() {
  const router = useRouter();
  const { user, token, isLoading, logout } = useAuth();

  const [sessions, setSessions] = useState<Session[]>([]);
  const [currentSession, setCurrentSession] = useState<Session | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoadingChat, setIsLoadingChat] = useState(false);
  const [isLoadingSessions, setIsLoadingSessions] = useState(true);
  const [isIncognito, setIsIncognito] = useState(false);
  const [copiedMessageId, setCopiedMessageId] = useState<number | string | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [showUserMenu, setShowUserMenu] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [stopGeneration, setStopGeneration] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [speakingMessageId, setSpeakingMessageId] = useState<string | null>(null);
  const [sidebarTab, setSidebarTab] = useState<"recent" | "starred">("recent");
  const [showThinking, setShowThinking] = useState<string | null>(null);
  const [thinkingMessageId, setThinkingMessageId] = useState<string | null>(null);
  const [isGreeting, setIsGreeting] = useState(false);
  const [thoughtSteps, setThoughtSteps] = useState<string[]>([]);
  const [showThoughtProcess, setShowThoughtProcess] = useState(false);
  const [dateFilter, setDateFilter] = useState<"today" | "week" | "month">("today");
  const [editingSessionId, setEditingSessionId] = useState<string | null>(null);
  const [editingTitle, setEditingTitle] = useState("");
  const [sessionMenuOpen, setSessionMenuOpen] = useState<string | null>(null);
  const [newChatTitle, setNewChatTitle] = useState("");
  const [showNewChatInput, setShowNewChatInput] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const userMenuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!isLoading && !user) {
      router.push("/auth");
    }
  }, [user, isLoading, router]);

  useEffect(() => {
    if (user && token) {
      fetchSessions();
    }
  }, [user, token]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (userMenuRef.current && !userMenuRef.current.contains(event.target as Node)) {
        setShowUserMenu(false);
      }
      if (sessionMenuOpen && !(event.target as Element).closest('.session-menu')) {
        setSessionMenuOpen(null);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [sessionMenuOpen]);

  const fetchSessions = async () => {
    try {
      const response = await fetch(`${API_URL}/api/sessions`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (response.ok) {
        const data = await response.json();
        setSessions(data.sessions || []);
        if (data.sessions?.length > 0 && !currentSession) {
          selectSession(data.sessions[0]);
        }
      }
    } catch (error) {
      console.error("Failed to fetch sessions:", error);
    } finally {
      setIsLoadingSessions(false);
    }
  };

  const selectSession = async (session: Session) => {
    setCurrentSession(session);
    setIsIncognito(session.is_incognito);
    try {
      const response = await fetch(`${API_URL}/api/sessions/${session.session_id}/history`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (response.ok) {
        const data = await response.json();
        const msgs = Array.isArray(data.messages) ? data.messages : [];
        setMessages(msgs.map((m: any) => ({
          ...m,
          id: m.id,
          created_at: m.created_at,
        })));
      }
    } catch (error) {
      console.error("Failed to load session:", error);
    }
  };

  const createNewSession = async (title?: string) => {
    const chatTitle = title || "New Chat";
    try {
      const response = await fetch(`${API_URL}/api/sessions`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          title: chatTitle,
          is_incognito: isIncognito,
        }),
      });
      if (response.ok) {
        const data = await response.json();
        setCurrentSession(data);
        setMessages([]);
        setIsIncognito(false);
        setNewChatTitle("");
        setShowNewChatInput(false);
        fetchSessions();
        inputRef.current?.focus();
      }
    } catch (error) {
      console.error("Failed to create session:", error);
    }
  };

  const updateSessionTitle = async (sessionId: string, newTitle: string) => {
    try {
      const response = await fetch(`${API_URL}/api/sessions/${sessionId}`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ title: newTitle }),
      });
      if (response.ok) {
        setSessions((prev) =>
          prev.map((s) => (s.session_id === sessionId ? { ...s, title: newTitle } : s))
        );
        if (currentSession?.session_id === sessionId) {
          setCurrentSession((prev) => (prev ? { ...prev, title: newTitle } : null));
        }
      }
    } catch (error) {
      console.error("Failed to update session:", error);
    }
    setEditingSessionId(null);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend(input);
    }
  };

  const GREETINGS = ["hi", "hello", "hey", "good morning", "good afternoon", "good evening", "howdy", "hi there", "hello there"];

  const handleSend = async (content: string, isRegeneration = false) => {
    if (!content.trim() || isLoadingChat) return;

    const trimmedContent = content.trim();
    const isGreetingMsg = GREETINGS.includes(trimmedContent.toLowerCase());
    
    setIsGreeting(isGreetingMsg);
    setThoughtSteps([]);
    setShowThoughtProcess(false);
    setInput("");
    setIsLoadingChat(true);
    setStopGeneration(false);
    
    const tempAsstId = `temp-asst-${Date.now()}`;
    setThinkingMessageId(tempAsstId);

    const userMessage: Message = {
      id: `temp-${Date.now()}`,
      role: "user",
      content: trimmedContent,
      created_at: new Date().toISOString(),
    };

    if (!isRegeneration) {
      setMessages((prev) => [...prev, userMessage]);
    }

    try {
      const response = await fetch(`${API_URL}/api/chat/stream`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          message: trimmedContent,
          session_id: currentSession?.session_id,
          is_incognito: isIncognito,
        }),
      });

      if (!response.ok) throw new Error("Failed to send message");

      const reader = response.body?.getReader();
      if (!reader) throw new Error("No response body");

      const assistantMessage: Message = {
        id: `asst-${Date.now()}`,
        role: "assistant",
        content: "",
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, assistantMessage]);

      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        if (stopGeneration) {
          reader.cancel();
          break;
        }
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        
        // Split by double newline as per SSE standard, or single newline
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (let line of lines) {
          line = line.trim();
          if (!line) continue;
          
          // CRITICAL: Robustly extract JSON even if prefix is malformed or missing
          let jsonStr = line.trim();
          if (jsonStr.includes("{")) {
            jsonStr = jsonStr.substring(jsonStr.indexOf("{"));
          }
          
          if (!jsonStr || jsonStr.startsWith("data:") || jsonStr === "[DONE]") continue;
          
          try {
            const data = JSON.parse(jsonStr);
            console.log('Stream data:', data.type, data);
            
            // Skip thought_process chunks - they're handled separately
            if (data.type === "thought_process") {
              setThoughtSteps(data.steps || []);
              setMessages((prev) => {
                const updated = [...prev];
                const lastMsg = updated[updated.length - 1];
                if (lastMsg?.role === "assistant") {
                  lastMsg.metadata = { ...lastMsg.metadata, thought_process: data.steps };
                }
                return updated;
              });
              continue;
            }
            
            if (data.type === "content" && data.content) {
              setThinkingMessageId(null);
              // Only add non-thought-process content
              setMessages((prev) => {
                const updated = [...prev];
                const lastMsg = updated[updated.length - 1];
                if (lastMsg?.role === "assistant") {
                  // Skip if content looks like thought process
                  if (!data.content.includes("AI Thinking") && !data.content.includes("Analyzing query")) {
                    lastMsg.content += data.content;
                  }
                }
                return updated;
              });
            } else if (data.type === "metadata") {
              setMessages((prev) => {
                const updated = [...prev];
                const lastMsg = updated[updated.length - 1];
                if (lastMsg?.role === "assistant") {
                  lastMsg.sources = data.sources;
                  lastMsg.metadata = data;
                }
                return updated;
              });
            } else if (data.type === "error") {
              console.error("Backend error:", data.content);
              setThinkingMessageId(null);
            } else if (data.type === "done") {
              setThinkingMessageId(null);
              break;
            }
          } catch (e) {
            console.warn("Failed to parse stream chunk:", e, line);
          }
        }
      }

      if (currentSession) {
        // Refresh session to get updated title and history
        fetchSessions();
      } else {
        fetchSessions();
      }
    } catch (error) {
      console.error("Chat error:", error);
    } finally {
      setIsLoadingChat(false);
      setThinkingMessageId(null);
    }
  };

  const handleStopGeneration = () => {
    setStopGeneration(true);
  };

  const handleCopy = async (text: string, id: string) => {
    const textToCopy = stripMarkdown(text);
    await navigator.clipboard.writeText(textToCopy);
    setCopiedMessageId(id);
    setTimeout(() => setCopiedMessageId(null), 2000);
  };

  const handleResend = (content: string) => {
    const msgs = Array.isArray(messages) ? messages : [];
    setMessages((prev) => prev.filter((m) => m.id !== msgs[msgs.length - 1]?.id));
    handleSend(content, true);
  };

  const handleDeleteSession = async (sessionId: string) => {
    try {
      const response = await fetch(`${API_URL}/api/sessions/${sessionId}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (response.ok) {
        setSessions((prev) => prev.filter((s) => s.session_id !== sessionId));
        if (currentSession?.session_id === sessionId) {
          setCurrentSession(null);
          setMessages([]);
        }
      }
    } catch (error) {
      console.error("Failed to delete session:", error);
    }
  };

  const handleStarSession = async (sessionId: string) => {
    try {
      const session = sessions.find((s) => s.session_id === sessionId);
      if (!session) return;
      const response = await fetch(`${API_URL}/api/sessions/${sessionId}`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ is_starred: !session.is_starred }),
      });
      if (response.ok) {
        fetchSessions();
      }
    } catch (error) {
      console.error("Failed to star session:", error);
    }
  };

  const speakMessage = (text: string, messageId: string) => {
    if (isSpeaking && speakingMessageId === messageId) {
      window.speechSynthesis.cancel();
      setIsSpeaking(false);
      setSpeakingMessageId(null);
      return;
    }

    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = "en-US";
    utterance.rate = 1;

    utterance.onstart = () => {
      setIsSpeaking(true);
      setSpeakingMessageId(messageId);
    };

    utterance.onend = () => {
      setIsSpeaking(false);
      setSpeakingMessageId(null);
    };

    window.speechSynthesis.speak(utterance);
  };

  const filterSessionsByDate = (sessionList: Session[]) => {
    const now = new Date();
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    const weekAgo = new Date(today.getTime() - 7 * 24 * 60 * 60 * 1000);
    const monthAgo = new Date(now.getFullYear(), now.getMonth() - 1, now.getDate());

    return sessionList.filter(s => {
      if (!s.last_message_at) return false;
      const sessionDate = new Date(s.last_message_at);
      if (dateFilter === "today") return sessionDate >= today;
      if (dateFilter === "week") return sessionDate >= weekAgo;
      if (dateFilter === "month") return sessionDate >= monthAgo;
      return true;
    });
  };

  const recentSessions = sessions.filter(s => !s.is_starred);
  const starredSessions = sessions.filter(s => s.is_starred);
  const filteredRecentSessions = filterSessionsByDate(recentSessions);
  const filteredSessions = sidebarTab === "starred" ? starredSessions : filteredRecentSessions;

  if (isLoading || !user || isLoadingSessions) {
    return (
      <div className="min-h-screen bg-black flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-zinc-400" />
      </div>
    );
  }

  const chatMessages = Array.isArray(messages) ? messages : [];

  return (
    <div className="flex h-screen bg-black text-white">
      {/* Sidebar */}
      <aside
        className={cn(
          "w-72 bg-[#0F0F0F] border-r border-zinc-800/50 flex flex-col transition-all duration-300",
          !sidebarOpen && "w-0 -translate-x-full overflow-hidden"
        )}
      >
        <div className="p-4 border-b border-zinc-800/50">
          <button
            onClick={() => {
              setShowNewChatInput(true);
              createNewSession();
            }}
            className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-[#1A1A1A] hover:bg-[#252525] text-white rounded-xl text-sm font-medium transition-colors border border-zinc-800"
          >
            <Plus className="w-4 h-4" />
            New Chat
          </button>
        </div>

        <div className="px-4 pt-4 pb-2">
          <div className="flex items-center justify-between">
            <h3 className="text-xs font-medium text-zinc-500 uppercase tracking-wider">Recent Chats</h3>
            <div className="relative">
              <button
                onClick={() => setDateFilter(dateFilter === "today" ? "week" : dateFilter === "week" ? "month" : "today")}
                className="flex items-center gap-1 px-2 py-1 text-xs text-zinc-400 hover:text-white bg-[#1A1A1A] rounded-md border border-zinc-800"
              >
                {dateFilter === "today" ? "Today" : dateFilter === "week" ? "This week" : "This month"}
                <ChevronDown className="w-3 h-3" />
              </button>
            </div>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto px-4 pb-3">
          {filteredSessions.length === 0 ? (
            <p className="text-sm text-zinc-500 text-center py-4">
              {sidebarTab === "starred" ? "No starred conversations" : "No conversations yet"}
            </p>
          ) : (
            <div className="space-y-1">
              {filteredSessions.map((session) => (
                <div
                  key={session.session_id}
                  onClick={() => selectSession(session)}
                  className={cn(
                    "group flex items-center gap-3 px-3 py-3 rounded-xl cursor-pointer transition-all",
                    currentSession?.session_id === session.session_id
                      ? "bg-[#1A1A1A] border border-zinc-800"
                      : "hover:bg-[#1A1A1A] hover:border border-zinc-800/50 border border-transparent"
                  )}
                >
                  <MessageSquare className="w-4 h-4 text-zinc-500 flex-shrink-0" />
                  {editingSessionId === session.session_id ? (
                    <input
                      type="text"
                      value={editingTitle}
                      onChange={(e) => setEditingTitle(e.target.value)}
                      onBlur={() => updateSessionTitle(session.session_id, editingTitle)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") {
                          updateSessionTitle(session.session_id, editingTitle);
                        }
                      }}
                      className="flex-1 bg-transparent text-sm text-white focus:outline-none"
                      autoFocus
                      onClick={(e) => e.stopPropagation()}
                    />
                  ) : (
                    <>
                      <span className="flex-1 text-sm text-zinc-300 truncate">{session.title}</span>
                      <div className="opacity-0 group-hover:opacity-100 transition-opacity flex items-center gap-1">
                        <div className="relative">
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              setSessionMenuOpen(sessionMenuOpen === session.session_id ? null : session.session_id);
                            }}
                            className="p-1 hover:bg-zinc-700 rounded"
                          >
                            <MoreVertical className="w-3.5 h-3.5 text-zinc-500" />
                          </button>
                          {sessionMenuOpen === session.session_id && (
                            <div className="absolute right-0 top-full mt-1 w-36 bg-[#1A1A1A] border border-zinc-700 rounded-lg shadow-lg overflow-hidden z-50 session-menu">
                              <button
                                onClick={(e) => {
                                  e.stopPropagation();
                                  setEditingTitle(session.title);
                                  setEditingSessionId(session.session_id);
                                  setSessionMenuOpen(null);
                                }}
                                className="w-full flex items-center gap-2 px-3 py-2 hover:bg-zinc-800 text-sm text-zinc-300"
                              >
                                <Edit3 className="w-3.5 h-3.5" />
                                Rename
                              </button>
                              <button
                                onClick={(e) => {
                                  e.stopPropagation();
                                  handleStarSession(session.session_id);
                                  setSessionMenuOpen(null);
                                }}
                                className="w-full flex items-center gap-2 px-3 py-2 hover:bg-zinc-800 text-sm text-zinc-300"
                              >
                                <Star className={cn("w-3.5 h-3.5", session.is_starred && "fill-amber-400 text-amber-400")} />
                                {session.is_starred ? "Unstar" : "Star"}
                              </button>
                              <button
                                onClick={(e) => {
                                  e.stopPropagation();
                                  handleDeleteSession(session.session_id);
                                  setSessionMenuOpen(null);
                                }}
                                className="w-full flex items-center gap-2 px-3 py-2 hover:bg-zinc-800 text-sm text-red-400"
                              >
                                <Trash2 className="w-3.5 h-3.5" />
                                Delete
                              </button>
                            </div>
                          )}
                        </div>
                      </div>
                    </>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="p-3 border-t border-zinc-800">
          <div className="relative" ref={userMenuRef}>
            <button
              onClick={() => setShowUserMenu(!showUserMenu)}
              className="w-full flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-zinc-800 transition-colors"
            >
              <div className="w-8 h-8 rounded-full bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center">
                <span className="text-sm font-medium">
                  {user.full_name?.[0] || user.email?.[0]?.toUpperCase() || "U"}
                </span>
              </div>
              <div className="flex-1 text-left">
                <p className="text-sm font-medium truncate">{user.full_name || user.email}</p>
                <p className="text-xs text-zinc-500">Free Plan</p>
              </div>
              <ChevronDown className="w-4 h-4 text-zinc-500" />
            </button>
            {showUserMenu && (
              <div className="absolute bottom-full left-0 right-0 mb-1 bg-zinc-800 border border-zinc-700 rounded-lg shadow-lg overflow-hidden">
                <button className="w-full flex items-center gap-3 px-3 py-2.5 hover:bg-zinc-700 text-sm">
                  <Settings className="w-4 h-4" />
                  Settings
                </button>
                <button
                  onClick={logout}
                  className="w-full flex items-center gap-3 px-3 py-2.5 hover:bg-zinc-700 text-sm text-red-400"
                >
                  <LogOut className="w-4 h-4" />
                  Log out
                </button>
              </div>
            )}
          </div>
        </div>
      </aside>

      {/* Main Chat Area */}
      <main className="flex-1 flex flex-col min-w-0 bg-black">
        {/* Header */}
        <header className="h-14 flex items-center justify-between px-4 border-b border-zinc-800/30 bg-black/50 backdrop-blur-sm">
          <div className="flex items-center gap-3">
            {!sidebarOpen && (
              <button
                onClick={() => setSidebarOpen(!sidebarOpen)}
                className="p-1.5 hover:bg-zinc-800 rounded-lg transition-colors"
              >
                <PanelLeft className="w-5 h-5 text-zinc-400" />
              </button>
            )}
            <div className="relative">
              <button className="flex items-center gap-2 px-3 py-1.5 bg-[#1A1A1A] hover:bg-[#252525] rounded-lg border border-zinc-800 transition-colors">
                <h1 className="text-sm font-medium text-zinc-200 max-w-[200px] truncate">
                  {currentSession?.title || "New Chat"}
                </h1>
                <ChevronDown className="w-4 h-4 text-zinc-500" />
              </button>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => setSidebarTab(sidebarTab === "recent" ? "starred" : "recent")}
              className="flex items-center gap-2 px-3 py-1.5 text-sm text-zinc-400 hover:text-white transition-colors"
            >
              <MessageSquare className="w-4 h-4" />
              {sidebarTab === "recent" ? "Recent" : "Starred"}
            </button>
            {isLoadingChat && (
              <button
                onClick={handleStopGeneration}
                className="flex items-center gap-2 px-3 py-1.5 bg-zinc-800 hover:bg-zinc-700 rounded-lg text-sm transition-colors"
              >
                <Square className="w-3.5 h-3.5" />
                Stop
              </button>
            )}
          </div>
        </header>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto">
          {chatMessages.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full px-4">
              <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-blue-500 to-blue-600 flex items-center justify-center mb-6 shadow-lg">
                <Building2 className="w-8 h-8 text-white" />
              </div>
              <h2 className="text-2xl font-semibold text-white mb-3">
                Welcome to Dhara RAG
              </h2>
              <p className="text-zinc-400 text-center max-w-md mb-8">
                Your AI assistant for DCPR 2034 regulations, property feasibility analysis, and redevelopment compliance.
              </p>
              <div className="grid grid-cols-2 gap-3 w-full max-w-2xl">
                {[
                  "FSI for residential on 9m road",
                  "33(7B) affordable housing",
                  "Parking requirements",
                  "Premium FSI charges",
                ].map((query, i) => (
                  <button
                    key={i}
                    onClick={() => handleSend(query)}
                    className="p-4 bg-[#1A1A1A] hover:bg-[#252525] border border-zinc-800 hover:border-zinc-700 rounded-xl text-left text-sm text-zinc-300 hover:text-white transition-all"
                  >
                    {query}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <div className="max-w-2xl mx-auto px-6 py-8 space-y-6">
              {chatMessages.map((message, index) => (
                <div
                  key={message.id}
                  className={cn("group")}
                >
                  <div className="flex gap-4">
                    <div
                      className={cn(
                        "w-9 h-9 rounded-full flex-shrink-0 flex items-center justify-center",
                        message.role === "user"
                          ? "bg-gradient-to-br from-blue-500 to-indigo-600"
                          : "bg-gradient-to-br from-purple-500 to-pink-500"
                      )}
                    >
                      {message.role === "user" ? (
                        <span className="text-sm font-medium text-white">
                          {user.full_name?.[0] || user.email?.[0]?.toUpperCase() || "U"}
                        </span>
                      ) : (
                        <Building2 className="w-4 h-4 text-white" />
                      )}
                    </div>

                    <div className="flex-1 min-w-0">
                      <div className="group/msg relative">
                        <div
                          className={cn(
                            "text-[15px] leading-7",
                            message.role === "user" ? "text-white" : "text-zinc-100"
                          )}
                        >
                          {message.content.split("\n").map((line, i) => (
                            <p key={i} className={cn(i > 0 && "mt-4")}>
                              {line}
                            </p>
                          ))}
                        </div>

                        {/* Message Actions */}
                        <div className="absolute left-0 -top-8 opacity-0 group-hover/msg:opacity-100 transition-opacity flex items-center gap-1">
                          <button
                            onClick={() => handleCopy(message.content, message.id as string)}
                            className="p-1.5 hover:bg-zinc-800 rounded-md transition-colors"
                            title="Copy"
                          >
                            {copiedMessageId === message.id ? (
                              <Check className="w-4 h-4 text-zinc-400" />
                            ) : (
                              <Copy className="w-4 h-4 text-zinc-400" />
                            )}
                          </button>
                          {message.role === "assistant" && (
                            <button
                              onClick={() => speakMessage(message.content, message.id as string)}
                              className="p-1.5 hover:bg-zinc-800 rounded-md transition-colors"
                              title={speakingMessageId === message.id ? "Stop" : "Speak"}
                            >
                              <Volume2 className={cn(
                                "w-4 h-4",
                                speakingMessageId === message.id ? "text-red-400" : "text-zinc-400"
                              )} />
                            </button>
                          )}
                          {message.role === "user" && (
                            <button
                              onClick={() => handleResend(message.content)}
                              className="p-1.5 hover:bg-zinc-800 rounded-md transition-colors"
                              title="Regenerate"
                            >
                              <Copy className="w-4 h-4 text-zinc-400" />
                            </button>
                          )}
                        </div>
                      </div>

                      {/* Sources */}
                      {message.sources && message.sources.length > 0 && (
                        <div className="mt-4 pt-4 border-t border-zinc-800/50">
                          <p className="text-xs text-zinc-500 mb-2">Sources</p>
                          <div className="space-y-1">
                            {message.sources.map((source: any, i: number) => (
                              <a
                                key={i}
                                href={source.url || "#"}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="block text-sm text-blue-400 hover:underline truncate"
                              >
                                {source.title || source.text?.slice(0, 50) || `Source ${i + 1}`}
                              </a>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              ))}

              {isLoadingChat && thinkingMessageId && (
                <div className="flex gap-4">
                  <div className="w-9 h-9 rounded-full bg-zinc-800/50 flex items-center justify-center flex-shrink-0 border border-zinc-800/50">
                    <Building2 className="w-4 h-4 text-zinc-500" />
                  </div>
                  <div className="flex flex-col gap-2">
                    {/* Show Thinking button */}
                    <button
                      onClick={() => setShowThoughtProcess(!showThoughtProcess)}
                      className="text-xs text-zinc-500 hover:text-zinc-400 flex items-center gap-1 w-fit transition-colors"
                    >
                      <ChevronRight className={cn("w-3 h-3 transition-transform", showThoughtProcess && "rotate-90")} />
                      {showThoughtProcess ? "Hide" : "Show"} Thinking Process
                    </button>
                    
                    {/* Thinking steps */}
                    {showThoughtProcess && thoughtSteps.length > 0 && (
                      <div className="p-3 bg-zinc-900/30 rounded-lg text-xs text-zinc-500 font-mono max-w-md border border-zinc-800/50">
                        {thoughtSteps.map((step, i) => (
                          <div key={i} className="mb-1 last:mb-0">
                            <span className="text-blue-500/50 mr-2">›</span>
                            {step}
                          </div>
                        ))}
                      </div>
                    )}
                    
                    {/* Loading text */}
                    {!showThoughtProcess && (
                      <div className="flex items-center text-zinc-400 text-[15px]">
                        <span className="flex items-center gap-1.5">
                          Thinking
                          <span className="flex gap-0.5">
                            <span className="w-1 h-1 bg-zinc-600 rounded-full animate-bounce [animation-delay:-0.3s]"></span>
                            <span className="w-1 h-1 bg-zinc-600 rounded-full animate-bounce [animation-delay:-0.15s]"></span>
                            <span className="w-1 h-1 bg-zinc-600 rounded-full animate-bounce"></span>
                          </span>
                        </span>
                      </div>
                    )}
                  </div>
                </div>
              )}

              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

        {/* Input Area */}
        <div className="p-4 pb-6">
          <div className="max-w-2xl mx-auto">
            <div className="flex items-end gap-3 bg-transparent">
              <div className="flex-1 relative">
                <textarea
                  ref={inputRef}
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder="Ask anything..."
                  className="w-full bg-[#1A1A1A] text-white placeholder-zinc-500 resize-none focus:outline-none rounded-xl border border-zinc-800 px-4 py-3 text-[15px]"
                  rows={1}
                  disabled={isLoadingChat}
                />
              </div>
              <button
                onClick={() => handleSend(input)}
                disabled={!input.trim() || isLoadingChat}
                className={cn(
                  "p-3 rounded-xl transition-all flex items-center justify-center",
                  input.trim()
                    ? "bg-[#3B82F6] hover:bg-blue-600 text-white"
                    : "bg-[#1A1A1A] text-zinc-500 cursor-not-allowed border border-zinc-800"
                )}
              >
                {isLoadingChat ? (
                  <Loader2 className="w-5 h-5 animate-spin" />
                ) : (
                  <Send className="w-5 h-5" />
                )}
              </button>
            </div>
            <p className="mt-2 text-center text-xs text-zinc-600">
              Dhara RAG may produce inaccurate information. Verify important details independently.
            </p>
          </div>
        </div>
      </main>
    </div>
  );
}
