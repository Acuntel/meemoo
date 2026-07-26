/** WebSocket hooks: auto-reconnecting event stream + sim stream + video. */

import { useEffect, useRef, useState } from "react";
import { wsUrl } from "./api";
import type { BusEvent, FloorPlan, SimSnapshot } from "./types";

const RECONNECT_MS = 2500;

/** Subscribe to /ws/events. `onEvent` fires for every bus event. */
export function useEventStream(onEvent?: (event: BusEvent) => void): {
  connected: boolean;
  lastByTopic: Record<string, BusEvent>;
} {
  const [connected, setConnected] = useState(false);
  const [lastByTopic, setLastByTopic] = useState<Record<string, BusEvent>>({});
  const handler = useRef(onEvent);
  handler.current = onEvent;

  useEffect(() => {
    let socket: WebSocket | null = null;
    let timer: number | undefined;
    let disposed = false;

    const connect = () => {
      socket = new WebSocket(wsUrl("/ws/events"));
      socket.onmessage = (raw: MessageEvent<string>) => {
        const data = JSON.parse(raw.data) as BusEvent | { ready: boolean };
        if ("ready" in data) {
          setConnected(data.ready);
          return;
        }
        setLastByTopic((prev) => ({ ...prev, [data.topic]: data }));
        handler.current?.(data);
      };
      socket.onclose = () => {
        setConnected(false);
        if (!disposed) timer = window.setTimeout(connect, RECONNECT_MS);
      };
    };
    connect();
    return () => {
      disposed = true;
      window.clearTimeout(timer);
      socket?.close();
    };
  }, []);

  return { connected, lastByTopic };
}

/** Subscribe to /ws/sim: floor plan (once) + ~10 Hz snapshots. */
export function useSimStream(): {
  ready: boolean;
  plan: FloorPlan | null;
  snapshot: SimSnapshot | null;
} {
  const [ready, setReady] = useState(false);
  const [plan, setPlan] = useState<FloorPlan | null>(null);
  const [snapshot, setSnapshot] = useState<SimSnapshot | null>(null);

  useEffect(() => {
    let socket: WebSocket | null = null;
    let timer: number | undefined;
    let disposed = false;

    const connect = () => {
      socket = new WebSocket(wsUrl("/ws/sim"));
      socket.onmessage = (raw: MessageEvent<string>) => {
        const data = JSON.parse(raw.data) as
          | { ready: boolean; plan?: FloorPlan }
          | SimSnapshot;
        if ("ready" in data) {
          setReady(data.ready);
          if (data.plan) setPlan(data.plan);
          return;
        }
        setSnapshot(data);
      };
      socket.onclose = () => {
        setReady(false);
        if (!disposed) timer = window.setTimeout(connect, RECONNECT_MS);
      };
    };
    connect();
    return () => {
      disposed = true;
      window.clearTimeout(timer);
      socket?.close();
    };
  }, []);

  return { ready, plan, snapshot };
}

/** Subscribe to /ws/video: binary JPEG frames → object URL. */
export function useVideoStream(): { ready: boolean; frameUrl: string | null } {
  const [ready, setReady] = useState(false);
  const [frameUrl, setFrameUrl] = useState<string | null>(null);

  useEffect(() => {
    let socket: WebSocket | null = null;
    let timer: number | undefined;
    let disposed = false;
    let currentUrl: string | null = null;

    const connect = () => {
      socket = new WebSocket(wsUrl("/ws/video"));
      socket.binaryType = "blob";
      socket.onmessage = (raw: MessageEvent<Blob | string>) => {
        if (typeof raw.data === "string") {
          const hello = JSON.parse(raw.data) as { ready: boolean };
          setReady(hello.ready);
          return;
        }
        const url = URL.createObjectURL(raw.data);
        if (currentUrl) URL.revokeObjectURL(currentUrl);
        currentUrl = url;
        setFrameUrl(url);
      };
      socket.onclose = () => {
        setReady(false);
        if (!disposed) timer = window.setTimeout(connect, RECONNECT_MS);
      };
    };
    connect();
    return () => {
      disposed = true;
      window.clearTimeout(timer);
      socket?.close();
      if (currentUrl) URL.revokeObjectURL(currentUrl);
    };
  }, []);

  return { ready, frameUrl };
}
