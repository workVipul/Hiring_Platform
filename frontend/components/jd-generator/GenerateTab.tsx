"use client";

import { useMemo, useRef, useState } from "react";

import { jdApi } from "@/services/jdApi";
import type { GeneratedJD } from "@/types/jd";

type InputType = "text" | "voice" | "chat";
type ChatMessage = { role: "recruiter" | "assistant"; content: string };

type SpeechRecognitionResultItem = {
  transcript: string;
};

type SpeechRecognitionResult = {
  isFinal: boolean;
  0: SpeechRecognitionResultItem;
};

type SpeechRecognitionEvent = {
  resultIndex: number;
  results: {
    length: number;
    [index: number]: SpeechRecognitionResult;
  };
};

type SpeechRecognitionInstance = {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  start: () => void;
  stop: () => void;
  onresult: ((event: SpeechRecognitionEvent) => void) | null;
  onend: (() => void) | null;
  onerror: (() => void) | null;
};

type SpeechRecognitionConstructor = new () => SpeechRecognitionInstance;

type SpeechWindow = Window & {
  SpeechRecognition?: SpeechRecognitionConstructor;
  webkitSpeechRecognition?: SpeechRecognitionConstructor;
};

export default function GenerateTab({ onGenerated }: { onGenerated: (jd: GeneratedJD) => void }) {
  const [rawInput, setRawInput] = useState("");
  const [inputType, setInputType] = useState<InputType>("text");
  const [loading, setLoading] = useState(false);
  const [listening, setListening] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [chatDraft, setChatDraft] = useState("");
  const [audioFile, setAudioFile] = useState<File | null>(null);
  const [transcribing, setTranscribing] = useState(false);
  const [extracting, setExtracting] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([
    { role: "assistant", content: "Share the role, seniority, tech stack, location, and must-have skills." },
  ]);
  const recognitionRef = useRef<SpeechRecognitionInstance | null>(null);

  const generationInput = useMemo(() => {
    if (inputType === "chat") {
      return messages.map((message) => `${message.role}: ${message.content}`).join("\n");
    }
    return rawInput;
  }, [inputType, messages, rawInput]);

  async function handleGenerate() {
    setLoading(true);
    setError(null);
    try {
      const result = await jdApi.generate(generationInput, inputType);
      onGenerated(result);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Generation failed");
    } finally {
      setLoading(false);
    }
  }

  function startVoiceCapture() {
    setError(null);
    const SpeechRecognition = (window as SpeechWindow).SpeechRecognition ?? (window as SpeechWindow).webkitSpeechRecognition;
    if (!SpeechRecognition) {
      setError("Voice input is not supported in this browser. Use Chrome or Edge, or paste the transcript manually.");
      return;
    }

    const recognition = new SpeechRecognition();
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.lang = "en-IN";
    recognition.onresult = (event) => {
      let finalTranscript = "";
      for (let i = event.resultIndex; i < event.results.length; i += 1) {
        const result = event.results[i];
        if (result.isFinal) finalTranscript += `${result[0].transcript} `;
      }
      if (finalTranscript.trim()) {
        setRawInput((prev) => `${prev}${prev ? " " : ""}${finalTranscript.trim()}`);
      }
    };
    recognition.onerror = () => {
      setError("Voice capture stopped unexpectedly. Check microphone permission and try again.");
      setListening(false);
    };
    recognition.onend = () => setListening(false);
    recognitionRef.current = recognition;
    recognition.start();
    setListening(true);
  }

  function stopVoiceCapture() {
    recognitionRef.current?.stop();
    recognitionRef.current = null;
    setListening(false);
  }

  async function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) {
      setAudioFile(null);
      return;
    }

    const isVideo = file.type.startsWith("video/") || [".mp4", ".mov", ".avi", ".mkv", ".webm"].some(ext => file.name.toLowerCase().endsWith(ext));
    if (isVideo) {
      setExtracting(true);
      setError(null);
      try {
        const extracted = await extractAudioFromMedia(file);
        setAudioFile(extracted);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to extract audio from video file.");
        setAudioFile(null);
      } finally {
        setExtracting(false);
      }
    } else {
      setAudioFile(file);
    }
  }

  async function transcribeUploadedVoice() {
    if (!audioFile) return;
    setTranscribing(true);
    setError(null);
    try {
      const result = await jdApi.transcribe(audioFile);
      setRawInput((prev) => `${prev}${prev ? " " : ""}${result.text}`.trim());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Voice transcription failed");
    } finally {
      setTranscribing(false);
    }
  }

  function addChatMessage() {
    const content = chatDraft.trim();
    if (!content) return;
    setMessages((prev) => [...prev, { role: "recruiter", content }]);
    setChatDraft("");
  }

  return (
    <div className="panel stack">
      <div className="segmented">
        {(["text", "voice", "chat"] as const).map((type) => (
          <button key={type} className={inputType === type ? "active" : ""} onClick={() => setInputType(type)}>
            {type === "voice" ? "voice & video" : type}
          </button>
        ))}
      </div>

      {inputType === "text" && (
        <textarea
          value={rawInput}
          onChange={(e) => setRawInput(e.target.value)}
          placeholder="Paste hiring context, notes, transcript, or role requirements..."
          rows={12}
        />
      )}

      {inputType === "voice" && (
        <div className="stack">
          <div className="voice-controls">
            <button className={listening ? "danger-button" : "secondary-button"} onClick={listening ? stopVoiceCapture : startVoiceCapture}>
              {listening ? "Stop recording" : "Start recording"}
            </button>
            <button className="ghost-button" onClick={() => setRawInput("")}>Clear transcript</button>
            <span className={listening ? "recording-pill active" : "recording-pill"}>{listening ? "Listening" : "Idle"}</span>
          </div>
          <div className="upload-row">
            <input
              type="file"
              accept="audio/*,video/*,.mp3,.mp4,.mpeg,.mpga,.m4a,.mov,.avi,.wav,.webm"
              onChange={handleFileChange}
              disabled={extracting || transcribing}
            />
            <button className="secondary-button" disabled={!audioFile || transcribing || extracting} onClick={transcribeUploadedVoice}>
              {transcribing ? "Transcribing..." : extracting ? "Extracting audio..." : "Transcribe upload"}
            </button>
          </div>
          <textarea
            value={rawInput}
            onChange={(e) => setRawInput(e.target.value)}
            placeholder="Your dictated hiring context will appear here. You can edit it before generating."
            rows={12}
          />
        </div>
      )}

      {inputType === "chat" && (
        <div className="chat-builder">
          <div className="chat-log">
            {messages.map((message, index) => (
              <div key={`${message.role}-${index}`} className={`chat-message ${message.role}`}>
                <span>{message.role}</span>
                <p>{message.content}</p>
              </div>
            ))}
          </div>
          <div className="chat-input-row">
            <input
              value={chatDraft}
              onChange={(e) => setChatDraft(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") addChatMessage();
              }}
              placeholder="Add role detail, skill requirement, location, budget, or hiring notes"
            />
            <button className="secondary-button" onClick={addChatMessage}>Add</button>
          </div>
          <div className="inline-actions">
            <button className="ghost-button" onClick={() => setMessages(messages.slice(0, 1))}>Clear chat</button>
          </div>
        </div>
      )}

      {error && <p className="error">{error}</p>}
      <button className="primary-button" disabled={loading || generationInput.trim().length < 10} onClick={handleGenerate}>
        {loading ? "Generating..." : `Generate JD from ${inputType === "voice" ? "voice & video" : inputType}`}
      </button>
    </div>
  );
}

function audioBufferToWav(buffer: AudioBuffer): Blob {
  const targetSampleRate = 16000;
  const numChannels = 1;
  const sampleRateRatio = buffer.sampleRate / targetSampleRate;
  const targetLength = Math.round(buffer.length / sampleRateRatio);
  
  const bufferArr = new ArrayBuffer(targetLength * 2 + 44);
  const view = new DataView(bufferArr);
  let pos = 0;

  const setUint16 = (data: number) => {
    view.setUint16(pos, data, true);
    pos += 2;
  };

  const setUint32 = (data: number) => {
    view.setUint32(pos, data, true);
    pos += 4;
  };

  // write WAV container header
  setUint32(0x46464952); // "RIFF"
  setUint32(targetLength * 2 + 36); // file length - 8
  setUint32(0x45564157); // "WAVE"
  setUint32(0x20746d66); // "fmt " chunk
  setUint32(16);         // length = 16
  setUint16(1);          // PCM audio format = 1
  setUint16(numChannels);
  setUint32(targetSampleRate);
  setUint32(targetSampleRate * numChannels * 2); // byte rate
  setUint16(numChannels * 2);              // block align
  setUint16(16);                         // bits per sample
  setUint32(0x61746164); // "data" chunk
  setUint32(targetLength * 2); // chunk length

  // Downsample and write mono channel data
  const channelData = buffer.getChannelData(0);
  for (let i = 0; i < targetLength; i++) {
    const sourceIndex = Math.floor(i * sampleRateRatio);
    let sample = channelData[sourceIndex];
    sample = Math.max(-1, Math.min(1, sample)); // clamp
    sample = sample < 0 ? sample * 0x8000 : sample * 0x7FFF;
    view.setInt16(pos, sample, true);
    pos += 2;
  }

  return new Blob([bufferArr], { type: "audio/wav" });
}

async function extractAudioFromMedia(file: File): Promise<File> {
  const AudioContextClass = window.AudioContext || (window as any).webkitAudioContext;
  if (!AudioContextClass) {
    throw new Error("Web Audio API is not supported in this browser.");
  }

  const audioCtx = new AudioContextClass();
  try {
    const arrayBuffer = await file.arrayBuffer();
    const audioBuffer = await audioCtx.decodeAudioData(arrayBuffer);
    const wavBlob = audioBufferToWav(audioBuffer);
    const baseName = file.name.substring(0, file.name.lastIndexOf(".")) || file.name;
    return new File([wavBlob], `${baseName}_audio.wav`, { type: "audio/wav" });
  } catch (err) {
    console.error("Audio extraction failed:", err);
    throw new Error("Failed to extract audio from the video file. Make sure it is a valid video format supported by your browser.");
  } finally {
    await audioCtx.close();
  }
}

