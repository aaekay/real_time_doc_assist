import { useCallback, useRef, useState } from 'react';

interface UseAudioCaptureReturn {
  isRecording: boolean;
  error: string | null;
  start: () => Promise<void>;
  stop: () => void;
}

/**
 * Captures microphone audio as raw PCM16 mono 16kHz and sends chunks
 * via the provided callback.
 */
export function useAudioCapture(
  onAudioChunk: (data: ArrayBuffer) => void,
): UseAudioCaptureReturn {
  const [isRecording, setIsRecording] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const contextRef = useRef<AudioContext | null>(null);
  const sourceRef = useRef<MediaStreamAudioSourceNode | null>(null);
  const processorRef = useRef<ScriptProcessorNode | null>(null);
  const streamRef = useRef<MediaStream | null>(null);

  const start = useCallback(async () => {
    if (isRecording) return;
    setError(null);

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          sampleRate: 16000,
          echoCancellation: true,
          noiseSuppression: true,
        },
      });
      streamRef.current = stream;

      const context = new AudioContext({ sampleRate: 16000 });
      contextRef.current = context;

      const source = context.createMediaStreamSource(stream);
      sourceRef.current = source;

      // ScriptProcessorNode with buffer size 4096 (~256ms at 16kHz)
      const processor = context.createScriptProcessor(4096, 1, 1);
      processorRef.current = processor;

      processor.onaudioprocess = (e) => {
        const float32 = e.inputBuffer.getChannelData(0);
        // Convert float32 [-1,1] to PCM16 int16
        const pcm16 = new Int16Array(float32.length);
        for (let i = 0; i < float32.length; i++) {
          const s = Math.max(-1, Math.min(1, float32[i]));
          pcm16[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
        }
        onAudioChunk(pcm16.buffer);
      };

      source.connect(processor);
      processor.connect(context.destination);
      setIsRecording(true);
    } catch {
      setError('Microphone access failed. Check browser permissions.');
      setIsRecording(false);
    }
  }, [isRecording, onAudioChunk]);

  const stop = useCallback(() => {
    if (!isRecording) return;
    processorRef.current?.disconnect();
    sourceRef.current?.disconnect();
    void contextRef.current?.close().catch(() => {
      // No-op: context might already be closed in some browsers.
    });
    streamRef.current?.getTracks().forEach((t) => t.stop());
    processorRef.current = null;
    sourceRef.current = null;
    contextRef.current = null;
    streamRef.current = null;
    setIsRecording(false);
  }, [isRecording]);

  return { isRecording, error, start, stop };
}
