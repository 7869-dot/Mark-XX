import { create } from 'zustand';

interface User {
  id: string;
  email: string;
  full_name?: string;
  avatar_url?: string;
}

interface Message {
  role: 'user' | 'assistant';
  content: string;
  id?: string;
}

interface AppState {
  user: User | null;
  token: string | null;
  messages: Message[];
  isStreaming: boolean;
  personality: any | null;
  summary: string | null;
  
  // Actions
  setUser: (user: User | null) => void;
  setToken: (token: string | null) => void;
  addMessage: (message: Message) => void;
  setMessages: (messages: Message[]) => void;
  updateLastMessage: (content: string) => void;
  setIsStreaming: (isStreaming: boolean) => void;
  setPersonality: (personality: any) => void;
  setSummary: (summary: string) => void;
  logout: () => void;
}

export const useStore = create<AppState>((set) => ({
  user: null,
  token: localStorage.getItem('axolot_token'),
  messages: [],
  isStreaming: false,
  personality: null,
  summary: null,

  setUser: (user) => set({ user }),
  setToken: (token) => {
    if (token) localStorage.setItem('axolot_token', token);
    else localStorage.removeItem('axolot_token');
    set({ token });
  },
  addMessage: (message) => set((state) => ({ 
    messages: [...state.messages, message] 
  })),
  setMessages: (messages) => set({ messages }),
  updateLastMessage: (content) => set((state) => {
    const newMessages = [...state.messages];
    if (newMessages.length > 0) {
      newMessages[newMessages.length - 1].content = content;
    }
    return { messages: newMessages };
  }),
  setIsStreaming: (isStreaming) => set({ isStreaming }),
  setPersonality: (personality) => set({ personality }),
  setSummary: (summary) => set({ summary }),
  logout: () => {
    localStorage.removeItem('axolot_token');
    set({ user: null, token: null, messages: [], personality: null, summary: null });
  },
}));
