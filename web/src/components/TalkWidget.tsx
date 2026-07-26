/** Talk to Meemoo from the browser — /ws/voice, both directions (step-07 §2).
 *
 * Typing always works; hold-to-talk appears when the browser has a mic. A
 * reply that came with real TTS audio plays automatically. Distress and
 * crisis flags surface honestly — the same safety-ordered pipeline as the
 * room microphone is on the other end of this socket.
 */

import { useEffect, useRef, useState } from "react";
import { wsUrl } from "../lib/api";
import { micSupported, startMic, type MicCapture } from "../lib/mic";
import { Button, EmptyNote } from "./ui";

type Bubble = {
  role: "user" | "meemoo" | "note";
  text: string;
  flag?: "distress" | "crisis";
};

type ServerMessage =
  | { type: "ready"; stt: boolean; tts: string; voice: string }
  | { type: "transcript"; text: string }
  | { type: "reply"; text: string; distress: boolean; crisis: boolean }
  | { type: "audio"; available: boolean; rate?: number; engine?: string }
  | { type: "error"; reason: string; detail?: string };

export default function TalkWidget() {
  const [bubbles, setBubbles] = useState<Bubble[]>([]);
  const [draft, setDraft] = useState("");
  const [ready, setReady] = useState<{ stt: boolean; tts: string } | null>(null);
  const [recording, setRecording] = useState(false);
  const socketRef = useRef<WebSocket | null>(null);
  const micRef = useRef<MicCapture | null>(null);
  const scrollRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    let disposed = false;
    let socket: WebSocket | null = null;
    let timer: number | undefined;

    const connect = () => {
      socket = new WebSocket(wsUrl("/ws/voice"));
      socket.binaryType = "blob";
      socketRef.current = socket;
      socket.onmessage = (raw: MessageEvent<Blob | string>) => {
        if (typeof raw.data !== "string") {
          const url = URL.createObjectURL(raw.data);
          const audio = new Audio(url);
          audio.onended = () => URL.revokeObjectURL(url);
          void audio.play().catch(() => URL.revokeObjectURL(url));
          return;
        }
        const message = JSON.parse(raw.data) as ServerMessage;
        if (message.type === "ready") {
          setReady({ stt: message.stt, tts: message.tts });
        } else if (message.type === "transcript") {
          setBubbles((prev) => [...prev, { role: "user", text: message.text }]);
        } else if (message.type === "reply") {
          const flag = message.crisis
            ? ("crisis" as const)
            : message.distress
              ? ("distress" as const)
              : undefined;
          setBubbles((prev) => [
            ...prev,
            { role: "meemoo", text: message.text, flag },
          ]);
        } else if (message.type === "error") {
          setBubbles((prev) => [
            ...prev,
            { role: "note", text: message.detail ?? message.reason },
          ]);
        }
      };
      socket.onclose = () => {
        setReady(null);
        if (!disposed) timer = window.setTimeout(connect, 2500);
      };
    };
    connect();
    return () => {
      disposed = true;
      window.clearTimeout(timer);
      micRef.current?.stop();
      socket?.close();
    };
  }, []);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight });
  }, [bubbles]);

  const send = () => {
    const text = draft.trim();
    const socket = socketRef.current;
    if (!text || socket === null || socket.readyState !== WebSocket.OPEN) return;
    socket.send(JSON.stringify({ type: "text", text }));
    setBubbles((prev) => [...prev, { role: "user", text }]);
    setDraft("");
  };

  const startTalk = async () => {
    const socket = socketRef.current;
    if (socket === null || socket.readyState !== WebSocket.OPEN) return;
    try {
      micRef.current = await startMic((pcm) => {
        if (socket.readyState === WebSocket.OPEN) socket.send(pcm);
      });
      setRecording(true);
    } catch {
      setBubbles((prev) => [
        ...prev,
        { role: "note", text: "Microphone unavailable — typing still works." },
      ]);
    }
  };

  const stopTalk = () => {
    micRef.current?.stop();
    micRef.current = null;
    setRecording(false);
    const socket = socketRef.current;
    if (socket !== null && socket.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify({ type: "end" }));
    }
  };

  return (
    <div className="flex h-full flex-col">
      <div
        ref={scrollRef}
        className="flex-1 space-y-2 overflow-y-auto rounded-2xl bg-cream p-3"
        style={{ minHeight: "10rem", maxHeight: "16rem" }}
      >
        {bubbles.length === 0 && (
          <EmptyNote>
            Say hello — this goes through the very same ears and voice Meemoo
            uses in the room.
          </EmptyNote>
        )}
        {bubbles.map((bubble, index) => (
          <div
            key={index}
            className={`flex ${bubble.role === "user" ? "justify-end" : "justify-start"}`}
          >
            <span
              className={`max-w-[85%] rounded-2xl px-4 py-2 text-sm ${
                bubble.role === "user"
                  ? "bg-sage text-white"
                  : bubble.role === "meemoo"
                    ? "bg-card shadow-sm"
                    : "bg-peach-soft text-ink-soft"
              }`}
            >
              {bubble.text}
              {bubble.flag && (
                <span className="mt-1 block text-xs font-semibold text-rose">
                  {bubble.flag === "crisis"
                    ? "Crisis support offered (988)"
                    : "Heard as a call for help — Meemoo is escalating"}
                </span>
              )}
            </span>
          </div>
        ))}
      </div>
      <form
        className="mt-3 flex items-center gap-2"
        onSubmit={(event) => {
          event.preventDefault();
          send();
        }}
      >
        <input
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          placeholder={
            ready === null ? "Connecting…" : "Type something to Meemoo…"
          }
          disabled={ready === null}
          className="min-w-0 flex-1 rounded-full border border-line bg-card px-4 py-2 text-sm outline-none focus:border-sage"
        />
        <Button type="submit" disabled={ready === null || !draft.trim()}>
          Send
        </Button>
        {micSupported() && ready !== null && ready.stt && (
          <button
            type="button"
            onMouseDown={() => void startTalk()}
            onMouseUp={stopTalk}
            onMouseLeave={() => recording && stopTalk()}
            onTouchStart={() => void startTalk()}
            onTouchEnd={stopTalk}
            className={`rounded-full px-4 py-2 text-sm font-semibold transition ${
              recording ? "animate-ring bg-rose text-white" : "bg-sky-soft text-ink-soft"
            }`}
          >
            {recording ? "Listening…" : "Hold to talk"}
          </button>
        )}
      </form>
      {ready !== null && !ready.stt && (
        <p className="mt-2 text-xs text-ink-faint">
          No speech engine on this machine yet — typed chat works fully.
        </p>
      )}
    </div>
  );
}
