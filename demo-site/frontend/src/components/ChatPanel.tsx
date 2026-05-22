import { useState, useRef, useEffect } from "react";
import { Send, Lightbulb, Trash2 } from "lucide-react";
import type { ChatMessage, FixSuggestion, ChatResponse, PenFile } from "../types/pen";

const API = "";

interface Props {
  projectId: string;
  pen: PenFile;
  onApplySuggestion?: (op: string, payload: Record<string, unknown>) => void;
}

export function ChatPanel({ projectId, onApplySuggestion }: Props) {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      role: "ai",
      text: "Hello! I'm your DFD/ERD assistant. Ask me about your diagram — errors, suggestions, entity explanations, or how to improve your schema. Try 'How does my diagram look?' or 'What should I fix?'",
    },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  const sendMessage = async () => {
    const text = input.trim();
    if (!text || loading) return;

    setInput("");
    setLoading(true);

    const userMsg: ChatMessage = { role: "user", text };
    setMessages((prev) => [...prev, userMsg]);

    try {
      const res = await fetch(`${API}/llm/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          project_id: projectId,
          message: text,
          context: "both",
        }),
      });
      if (!res.ok) throw new Error(await res.text());
      const data: ChatResponse = await res.json();

      const aiMsg: ChatMessage = {
        role: "ai",
        text: data.message,
        suggestions: data.suggestions,
      };
      setMessages((prev) => [...prev, aiMsg]);
    } catch {
      setMessages((prev) => [
        ...prev,
        { role: "ai", text: "Sorry, I couldn't get a response. Is the backend running?" },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const applySuggestion = (suggestion: FixSuggestion) => {
    if (onApplySuggestion) {
      onApplySuggestion(suggestion.op, suggestion.payload);
    }
  };

  const clearChat = () => {
    setMessages([
      {
        role: "ai",
        text: "Chat cleared. Ask me about your diagram!",
      },
    ]);
  };

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between px-4 py-2 border-b border-gray-100">
        <h2 className="font-semibold text-gray-900 text-sm">AI Assistant</h2>
        <button
          onClick={clearChat}
          className="p-1 text-gray-400 hover:text-gray-600 rounded"
          title="Clear chat"
        >
          <Trash2 className="w-3.5 h-3.5" />
        </button>
      </div>

      <div ref={scrollRef} className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map((msg, i) => (
          <div key={i}>
            <div
              className={`
                text-sm whitespace-pre-wrap leading-relaxed
                ${msg.role === "user"
                  ? "text-right"
                  : "text-gray-700"
                }
              `}
            >
              <span
                className={`
                  inline-block px-3 py-2.5 rounded-xl text-sm max-w-[85%]
                  ${msg.role === "user"
                    ? "bg-blue-600 text-white text-right"
                    : "bg-gray-100 text-gray-800"
                  }
                `}
              >
                {msg.text}
              </span>
            </div>

            {msg.suggestions && msg.suggestions.length > 0 && (
              <div className="mt-2 flex flex-col gap-1.5">
                <div className="text-xs text-gray-400 flex items-center gap-1">
                  <Lightbulb className="w-3 h-3" />
                  Suggestions
                </div>
                {msg.suggestions.map((s, j) => (
                  <button
                    key={j}
                    onClick={() => applySuggestion(s)}
                    className="text-left px-3 py-2 rounded-lg bg-indigo-50 border border-indigo-200 text-xs text-indigo-700 hover:bg-indigo-100 transition-colors"
                  >
                    <span className="font-medium">{s.label}</span>
                    {s.reason && (
                      <span className="text-indigo-500"> — {s.reason}</span>
                    )}
                  </button>
                ))}
              </div>
            )}
          </div>
        ))}
        {loading && (
          <div className="text-sm text-gray-400 italic">Thinking...</div>
        )}
      </div>

      <div className="p-3 border-t border-gray-200">
        <div className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && sendMessage()}
            placeholder="Ask about your diagram..."
            className="flex-1 text-sm px-3 py-2 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
            disabled={loading}
          />
          <button
            onClick={sendMessage}
            disabled={loading || !input.trim()}
            className="px-3 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors"
          >
            <Send className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
}
