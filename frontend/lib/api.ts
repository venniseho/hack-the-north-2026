const BASE_URL = import.meta.env.WXT_API_BASE_URL ?? 'http://localhost:8000';

export interface ChatReply {
  content: string;
  /** Backboard groups a conversation under a thread; send it back to continue one. */
  threadId: string;
}

export async function sendMessage(
  content: string,
  threadId?: string,
): Promise<ChatReply> {
  const response = await fetch(`${BASE_URL}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ content, thread_id: threadId }),
  });

  if (!response.ok) {
    throw new Error(`Backend responded ${response.status}: ${await response.text()}`);
  }

  const data = await response.json();
  return { content: data.content, threadId: data.thread_id };
}
