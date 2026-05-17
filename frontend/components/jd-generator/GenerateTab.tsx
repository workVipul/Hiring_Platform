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
            {type}
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
              accept="audio/*,.mp3,.mp4,.mpeg,.mpga,.m4a,.ogg,.wav,.webm"
              onChange={(e) => setAudioFile(e.target.files?.[0] ?? null)}
            />
            <button className="secondary-button" disabled={!audioFile || transcribing} onClick={transcribeUploadedVoice}>
              {transcribing ? "Transcribing..." : "Transcribe upload"}
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
        {loading ? "Generating..." : `Generate JD from ${inputType}`}
      </button>
    </div>
  );
}
