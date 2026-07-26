/** Browser push-to-talk capture: mic → PCM16 mono 16 kHz chunks.
 *
 * Matches the /ws/voice contract (binary PCM16 chunks, then {"type":"end"}).
 * Raw audio goes straight over the socket and is discarded server-side after
 * transcription (Art. V §2) — nothing is buffered here beyond one chunk.
 */

export const MIC_SAMPLE_RATE = 16_000;

export type MicCapture = { stop: () => void };

export function micSupported(): boolean {
  return (
    typeof navigator !== "undefined" &&
    !!navigator.mediaDevices &&
    typeof navigator.mediaDevices.getUserMedia === "function"
  );
}

function downsampleTo16k(input: Float32Array, inputRate: number): Int16Array {
  const ratio = inputRate / MIC_SAMPLE_RATE;
  const length = Math.floor(input.length / ratio);
  const out = new Int16Array(length);
  for (let i = 0; i < length; i += 1) {
    const sample = input[Math.floor(i * ratio)] ?? 0;
    const clamped = Math.max(-1, Math.min(1, sample));
    out[i] = Math.round(clamped * 0x7fff);
  }
  return out;
}

/** Start capturing; `onChunk` receives PCM16 @ 16 kHz until `stop()`. */
export async function startMic(
  onChunk: (pcm: ArrayBuffer) => void,
): Promise<MicCapture> {
  const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  const context = new AudioContext();
  const source = context.createMediaStreamSource(stream);
  // ScriptProcessor is deprecated but dependency-free and universal; the
  // buffer is tiny (4096 samples) and freed as soon as each chunk is sent.
  const processor = context.createScriptProcessor(4096, 1, 1);
  processor.onaudioprocess = (event: AudioProcessingEvent) => {
    const mono = event.inputBuffer.getChannelData(0);
    const pcm = downsampleTo16k(mono, context.sampleRate);
    onChunk(pcm.buffer as ArrayBuffer);
  };
  source.connect(processor);
  processor.connect(context.destination);
  return {
    stop: () => {
      processor.disconnect();
      source.disconnect();
      for (const track of stream.getTracks()) track.stop();
      void context.close();
    },
  };
}
