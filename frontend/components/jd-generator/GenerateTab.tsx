"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import ConfirmDialog from "@/components/dashboard/ConfirmDialog";
import { jdApi } from "@/services/jdApi";
import type { GeneratedJD, ZohoJobOpening } from "@/types/jd";

type InputType = "text" | "voice" | "chat" | "zoho";
type ChatMessage = { role: "recruiter" | "assistant"; content: string };

const inputChecklist = [
  {
    id: "title",
    label: "Role title",
    hint: "Example: Senior Java Architect",
    question: "What role title are we hiring for?",
    pattern: /\b(role|title|position|hiring for|job title|architect|engineer|developer|manager|analyst|consultant|lead)\b/i,
  },
  {
    id: "experience",
    label: "Experience range",
    hint: "Years, seniority, or level",
    question: "What experience range or seniority should candidates have?",
    pattern: /\b(experience|years?|yrs?|senior|junior|mid[- ]level|lead|principal|fresher|\d+\s*\+?\s*(years?|yrs?))\b/i,
  },
  {
    id: "skills",
    label: "Must-have skills",
    hint: "Core technologies and tools",
    question: "Which must-have technical skills are required?",
    pattern: /\b(skill|must[- ]have|required|java|python|react|node|aws|azure|sql|spring|kubernetes|docker|microservices|api|angular|devops|testing)\b/i,
  },
  {
    id: "responsibilities",
    label: "Responsibilities",
    hint: "What the hire will own",
    question: "What are the core responsibilities for this role?",
    pattern: /\b(responsibility|own|deliver|design|build|manage|lead|develop|implement|collaborate|review|architect)\b/i,
  },
  {
    id: "location",
    label: "Location and work mode",
    hint: "City plus onsite, hybrid, or remote",
    question: "Where is the role based, and is it onsite, hybrid, or remote?",
    pattern: /\b(location|onsite|on-site|hybrid|remote|work mode|office|bangalore|bengaluru|pune|mumbai|chennai|hyderabad|delhi|noida|gurgaon|gurugram)\b/i,
  },
  {
    id: "extras",
    label: "Nice-to-have or context",
    hint: "Domain, compensation, shift, team notes",
    question: "Any nice-to-have skills, domain context, or compensation notes?",
    pattern: /\b(nice[- ]to[- ]have|good[- ]to[- ]have|preferred|domain|compensation|salary|budget|shift|notice|client|industry|context|fintech|banking|healthcare|retail)\b/i,
  },
];
const chatQuestions = inputChecklist.map((item) => item.question);
const followUpQuestion = "Any other information to include? If not, choose Generate now.";
const generationPromptPlaceholder = "Example: Generate a JD for a Senior Java Architect with 8-12 years of experience in Bangalore, hybrid mode. Must-have skills are Core Java, Spring Boot, microservices, REST APIs, SQL, AWS, and system design. The person will lead architecture, guide engineers, review designs, and own delivery quality. Good to have Kafka, Kubernetes, fintech domain exposure, and strong stakeholder communication.";

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
  const [zohoLoading, setZohoLoading] = useState(false);
  const [zohoOpenings, setZohoOpenings] = useState<ZohoJobOpening[]>([]);
  const [selectedZohoId, setSelectedZohoId] = useState("");
  const [pendingGenerationInput, setPendingGenerationInput] = useState<string | null>(null);
  const [missingChecklistItems, setMissingChecklistItems] = useState<string[]>([]);
  const [messages, setMessages] = useState<ChatMessage[]>([
    { role: "assistant", content: chatQuestions[0] },
  ]);
  const recognitionRef = useRef<SpeechRecognitionInstance | null>(null);
  const chatLogRef = useRef<HTMLDivElement | null>(null);

  const generationInput = useMemo(() => {
    if (inputType === "chat") {
      return messages.map((message) => `${message.role}: ${message.content}`).join("\n");
    }
    return rawInput;
  }, [inputType, messages, rawInput]);

  const checklistStatus = useMemo(() => {
    if (inputType === "chat") {
      return assessChatCompleteness(answeredChatQuestions());
    }
    return assessInputCompleteness(generationInput);
  }, [generationInput, inputType, messages]);

  useEffect(() => {
    if (inputType !== "chat") return;
    const chatLog = chatLogRef.current;
    if (!chatLog) return;
    chatLog.scrollTo({ top: chatLog.scrollHeight, behavior: "smooth" });
  }, [inputType, messages]);

  useEffect(() => {
    if (inputType === "zoho" && zohoOpenings.length === 0 && !zohoLoading) {
      void loadZohoOpenings();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [inputType]);

  async function executeGenerate(input: string) {
    setLoading(true);
    setError(null);
    try {
      const result = await jdApi.generate(input, inputType);
      if (inputType === "zoho" && selectedZohoId) {
        if (!result.metadata) result.metadata = {};
        result.metadata.zoho_recruit_id = selectedZohoId;
      }
      onGenerated(result);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Generation failed");
    } finally {
      setLoading(false);
    }
  }

  async function loadZohoOpenings() {
    setZohoLoading(true);
    setError(null);
    try {
      const result = await jdApi.zohoJobOpenings(1, 200);
      setZohoOpenings(result.data ?? []);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Zoho Recruit job fetch failed");
    } finally {
      setZohoLoading(false);
    }
  }

  function selectZohoOpening(jobId: string) {
    setSelectedZohoId(jobId);
    const opening = zohoOpenings.find((item) => item.id === jobId);
    setRawInput(opening ? formatZohoOpeningForGeneration(opening) : "");
  }

  async function handleGenerate(inputOverride?: string) {
    const input = inputOverride ?? generationInput;
    const status = inputType === "chat" ? assessChatCompleteness(countRecruiterAnswers(input)) : assessInputCompleteness(input);
    const missingItems = status.filter((item) => !item.complete).map((item) => item.label);
    if (missingItems.length > 0) {
      setMissingChecklistItems(missingItems);
      setPendingGenerationInput(input);
      return;
    }
    await executeGenerate(input);
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
    if (inputType === "chat" && answeredChatQuestions() >= chatQuestions.length) {
      const nextMessages = [...messages, { role: "recruiter" as const, content }];
      setMessages(nextMessages);
      setChatDraft("");
      void handleGenerate(formatMessages(nextMessages));
      return;
    }

    setMessages((prev) => {
      const answeredCount = prev.filter((message) => message.role === "recruiter").length;
      const nextQuestion = chatQuestions[answeredCount + 1] ?? followUpQuestion;
      return [
        ...prev,
        { role: "recruiter", content },
        ...(nextQuestion ? [{ role: "assistant" as const, content: nextQuestion }] : []),
      ];
    });
    setChatDraft("");
  }

  function answeredChatQuestions() {
    return messages.filter((message) => message.role === "recruiter").length;
  }

  function generateChatNow() {
    void handleGenerate(formatMessages(messages));
  }

  const tabLabels: Record<InputType, string> = {
    text: "Text",
    voice: "Voice & Video",
    chat: "Chat",
    zoho: "Zoho Recruit",
  };

  return (
    <div className="generate-layout">
      <div className="panel stack generate-input-panel">
        <div className="segmented">
          {(["text", "voice", "chat", "zoho"] as const).map((type) => (
            <button key={type} className={inputType === type ? "active" : ""} onClick={() => setInputType(type)}>
              {tabLabels[type]}
            </button>
          ))}
        </div>

        {inputType === "text" && (
          <textarea
            value={rawInput}
            onChange={(e) => setRawInput(e.target.value)}
            placeholder={generationPromptPlaceholder}
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
              placeholder={generationPromptPlaceholder}
              rows={12}
            />
          </div>
        )}

        {inputType === "chat" && (
          <div className="chat-builder">
            <div className="chat-log" ref={chatLogRef}>
              {messages.map((message, index) => (
                <div key={`${message.role}-${index}`} className={`chat-message ${message.role}`}>
                  <span>{message.role}</span>
                  <p>{message.content}</p>
                </div>
              ))}
            </div>
            <div className="chat-progress">
              <span className="muted small">{Math.min(answeredChatQuestions(), chatQuestions.length)} of {chatQuestions.length} details captured</span>
              <div className="chat-progress-track">
                <div style={{ width: `${Math.min(100, (answeredChatQuestions() / chatQuestions.length) * 100)}%` }} />
              </div>
            </div>
            <div className="chat-input-row">
              <input
                value={chatDraft}
                onChange={(e) => setChatDraft(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") addChatMessage();
                }}
                placeholder={answeredChatQuestions() >= chatQuestions.length ? "Add optional extra info" : "Add role detail, skill requirement, location, budget, or hiring notes"}
              />
              <button className="secondary-button" onClick={addChatMessage}>Add</button>
            </div>
            <div className="inline-actions">
              {answeredChatQuestions() >= chatQuestions.length && (
                <button className="primary-button" disabled={loading} onClick={generateChatNow}>
                  {loading ? "Generating..." : "No extra info"}
                </button>
              )}
              <button className="ghost-button" onClick={() => setMessages([{ role: "assistant", content: chatQuestions[0] }])}>Clear chat</button>
            </div>
          </div>
        )}

        {inputType === "zoho" && (
          <div className="zoho-generator stack">
            <div className="zoho-toolbar">
              <label>
                Job opening
                <select value={selectedZohoId} onChange={(e) => selectZohoOpening(e.target.value)} disabled={zohoLoading}>
                  <option value="">{zohoLoading ? "Loading Zoho jobs..." : "Select a Zoho Recruit job ID"}</option>
                  {zohoOpenings.map((opening) => (
                    <option key={opening.id} value={opening.id}>
                      {opening.id} - {opening.Posting_Title ?? "Untitled opening"}
                    </option>
                  ))}
                </select>
              </label>
              <button className="secondary-button compact-button" disabled={zohoLoading} onClick={loadZohoOpenings}>
                {zohoLoading ? "Refreshing..." : "Refresh"}
              </button>
            </div>
            {selectedZohoId && (
              <div className="zoho-selected-card">
                <strong>{zohoOpenings.find((item) => item.id === selectedZohoId)?.Posting_Title ?? "Selected Zoho job"}</strong>
                <span>{selectedZohoId}</span>
              </div>
            )}
            <textarea
              value={rawInput}
              onChange={(e) => setRawInput(e.target.value)}
              placeholder="Select a Zoho Recruit job to generate a JD from its job opening fields."
              rows={12}
            />
          </div>
        )}

        {error && <p className="error">{error}</p>}
        {inputType !== "chat" && (
          <button className="primary-button" disabled={loading || zohoLoading || generationInput.trim().length < 10} onClick={() => handleGenerate()}>
            {loading ? "Generating..." : "Generate JD"}
          </button>
        )}
      </div>

      <aside className="panel jd-input-checklist">
        <div>
          <p className="eyebrow">Input checklist</p>
          <h2>Before generating</h2>
          <p className="muted small">Capture these details once to avoid repeated JD generation calls.</p>
        </div>
        <div className="checklist-items">
          {checklistStatus.map((item, index) => (
            <div key={item.id} className={item.complete ? "checklist-item complete" : "checklist-item"}>
              <span>{item.complete ? "OK" : index + 1}</span>
              <div>
                <strong>{item.label}</strong>
                <p>{item.hint}</p>
              </div>
            </div>
          ))}
        </div>
      </aside>

      <ConfirmDialog
        open={pendingGenerationInput !== null}
        title="Generate with missing context?"
        message={`Missing details: ${missingChecklistItems.join(", ")}. You can proceed, but filling these first usually creates a stronger JD.`}
        confirmLabel="Generate anyway"
        cancelLabel="Fill details"
        onCancel={() => {
          setPendingGenerationInput(null);
          setMissingChecklistItems([]);
        }}
        onConfirm={() => {
          const input = pendingGenerationInput;
          setPendingGenerationInput(null);
          setMissingChecklistItems([]);
          if (input) void executeGenerate(input);
        }}
      />
    </div>
  );
}

function assessInputCompleteness(input: string) {
  return inputChecklist.map((item) => ({
    id: item.id,
    label: item.label,
    hint: item.hint,
    complete: item.pattern.test(input),
  }));
}

function assessChatCompleteness(answeredCount: number) {
  return inputChecklist.map((item, index) => ({
    id: item.id,
    label: item.label,
    hint: item.hint,
    complete: index < answeredCount,
  }));
}

function countRecruiterAnswers(input: string): number {
  return input.split("\n").filter((line) => line.toLowerCase().startsWith("recruiter:")).length;
}

function formatMessages(messages: ChatMessage[]): string {
  return messages.map((message) => `${message.role}: ${message.content}`).join("\n");
}

function formatZohoOpeningForGeneration(opening: ZohoJobOpening): string {
  const location = [opening.City, opening.State, opening.Country].filter(Boolean).join(", ");
  return [
    `Zoho Recruit Job ID: ${opening.id}`,
    `Posting Title: ${opening.Posting_Title ?? ""}`,
    `Client Name: ${opening.Client_Name ?? ""}`,
    `Job Description: ${opening.Job_Description ?? ""}`,
    `Required Skill Set: ${opening.Required_Skill_Set ?? ""}`,
    `Work Experience: ${opening.Work_Experience ?? ""}`,
    `Job Type: ${opening.Job_Type ?? ""}`,
    `Remote Job: ${opening.Remote_Job === true ? "Yes" : opening.Remote_Job === false ? "No" : ""}`,
    `Location: ${location}`,
    `Number of Positions: ${opening.No_of_Positions ?? ""}`,
    `Opening Status: ${opening.Job_Opening_Status ?? ""}`,
    `Date Opened: ${opening.Date_Opened ?? ""}`,
    `Target Date: ${opening.Target_Date ?? ""}`,
    `Salary: ${opening.Salary ?? ""}`,
  ].filter((line) => !line.endsWith(": ")).join("\n");
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
  const AudioContextClass = window.AudioContext || (window as Window & { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
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
