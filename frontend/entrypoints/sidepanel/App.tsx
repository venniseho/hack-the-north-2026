import { useState, type FormEvent } from 'react';
import { sendMessage } from '@/lib/api';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
}

export default function App() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [draft, setDraft] = useState('');
  const [threadId, setThreadId] = useState<string>();
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState<string>();

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();

    const content = draft.trim();
    if (!content || isSending) return;

    setMessages((prev) => [...prev, { id: crypto.randomUUID(), role: 'user', content }]);
    setDraft('');
    setIsSending(true);
    setError(undefined);

    try {
      const reply = await sendMessage(content, threadId);
      setThreadId(reply.threadId);
      setMessages((prev) => [
        ...prev,
        { id: crypto.randomUUID(), role: 'assistant', content: reply.content },
      ]);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Request failed.');
    } finally {
      setIsSending(false);
    }
  }

  return (
    <div className="flex h-full flex-col bg-white text-sm text-slate-900 dark:bg-slate-900 dark:text-slate-100">
      <header className="border-b border-slate-200 px-4 py-3 font-semibold dark:border-slate-700">
        Assistant
      </header>

      <main className="flex-1 space-y-3 overflow-y-auto p-4">
        {messages.length === 0 && (
          <p className="text-slate-500 dark:text-slate-400">
            Ask a question to get started.
          </p>
        )}

        {messages.map((message) => (
          <MessageBubble key={message.id} message={message} />
        ))}

        {isSending && <p className="text-slate-500 dark:text-slate-400">Thinking…</p>}
        {error && <p className="text-red-600 dark:text-red-400">{error}</p>}
      </main>

      <form
        onSubmit={handleSubmit}
        className="flex gap-2 border-t border-slate-200 p-3 dark:border-slate-700"
      >
        <input
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          placeholder="Send a message…"
          className="flex-1 rounded-md border border-slate-300 px-3 py-2 outline-none focus:border-blue-500 dark:border-slate-600 dark:bg-slate-800"
        />
        <button
          type="submit"
          disabled={isSending || draft.trim() === ''}
          className="rounded-md bg-blue-600 px-3 py-2 font-medium text-white disabled:opacity-50"
        >
          Send
        </button>
      </form>
    </div>
  );
}

function MessageBubble({ message }: { message: Message }) {
  const isUser = message.role === 'user';

  return (
    <div className={isUser ? 'text-right' : 'text-left'}>
      <span
        className={`inline-block max-w-[85%] whitespace-pre-wrap rounded-lg px-3 py-2 text-left ${
          isUser
            ? 'bg-blue-600 text-white'
            : 'bg-slate-100 text-slate-900 dark:bg-slate-800 dark:text-slate-100'
        }`}
      >
        {message.content}
      </span>
    </div>
  );
}
