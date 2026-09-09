import { useCallback, useRef, useState } from "react";

const SAMPLE_RATE = 16000;

export interface VoiceTurnEvent {
  transcript: string;
  reply_text: string;
  appointment_id: string | null;
}

interface VoiceSessionCallbacks {
  onTurn: (event: VoiceTurnEvent) => void;
  onAudio: (audio: ArrayBuffer) => void;
}

function voiceWebSocketUrl(sessionId: string, accessToken: string): string {
  const apiBase = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8001";
  const wsBase = apiBase.replace(/^http/, "ws");
  return `${wsBase}/api/v1/voice/${sessionId}?token=${encodeURIComponent(accessToken)}`;
}

/**
 * Captures mic audio, streams it as 16-bit PCM over the voice WebSocket, and
 * surfaces transcript/reply events plus the raw reply audio for playback.
 *
 * Uses the deprecated ScriptProcessorNode rather than an AudioWorklet: the
 * modern replacement needs a separate worklet module file; ScriptProcessorNode
 * is simpler to keep in one file and is still broadly supported. Swapping to
 * an AudioWorklet is the natural upgrade path if processor-thread audio
 * glitches ever become a real problem.
 */
export function useVoiceSession(accessToken: string | null) {
  const [isRecording, setIsRecording] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const streamRef = useRef<MediaStream | null>(null);

  const stop = useCallback(() => {
    streamRef.current?.getTracks().forEach((track) => track.stop());
    audioContextRef.current?.close();
    wsRef.current?.close();
    streamRef.current = null;
    audioContextRef.current = null;
    wsRef.current = null;
    setIsRecording(false);
  }, []);

  const start = useCallback(
    async (sessionId: string, callbacks: VoiceSessionCallbacks) => {
      if (!accessToken) {
        setError("Please sign in first.");
        return;
      }
      if (!navigator.mediaDevices?.getUserMedia) {
        setError("Voice isn't supported in this browser.");
        return;
      }

      setError(null);

      let stream: MediaStream;
      try {
        stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      } catch {
        setError("Microphone access was denied.");
        return;
      }
      streamRef.current = stream;

      const ws = new WebSocket(voiceWebSocketUrl(sessionId, accessToken));
      ws.binaryType = "arraybuffer";
      wsRef.current = ws;

      ws.onmessage = (event) => {
        if (typeof event.data === "string") {
          callbacks.onTurn(JSON.parse(event.data) as VoiceTurnEvent);
        } else {
          callbacks.onAudio(event.data as ArrayBuffer);
        }
      };
      ws.onerror = () => setError("Voice connection failed.");
      ws.onclose = () => setIsRecording(false);

      const audioContext = new AudioContext({ sampleRate: SAMPLE_RATE });
      audioContextRef.current = audioContext;
      const source = audioContext.createMediaStreamSource(stream);
      const processor = audioContext.createScriptProcessor(4096, 1, 1);

      processor.onaudioprocess = (event) => {
        if (ws.readyState !== WebSocket.OPEN) return;
        const input = event.inputBuffer.getChannelData(0);
        const pcm = new Int16Array(input.length);
        for (let i = 0; i < input.length; i++) {
          const sample = Math.max(-1, Math.min(1, input[i]));
          pcm[i] = sample < 0 ? sample * 0x8000 : sample * 0x7fff;
        }
        ws.send(pcm.buffer);
      };

      source.connect(processor);
      processor.connect(audioContext.destination);
      setIsRecording(true);
    },
    [accessToken],
  );

  return { isRecording, error, start, stop };
}
