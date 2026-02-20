// Vapi Webhook Event Types

export interface VapiCall {
  id: string;
  orgId: string;
  createdAt: string;
  updatedAt: string;
  type: 'webCall' | 'inboundPhoneCall' | 'outboundPhoneCall';
  status: 'queued' | 'ringing' | 'in-progress' | 'forwarding' | 'ended';
  phoneNumber?: VapiPhoneNumber;
  customer?: VapiCustomer;
  assistantId?: string;
  assistant?: VapiAssistant;
  duration?: number;
  endedReason?:
    | 'assistant-ended-call'
    | 'assistant-forwarded-call'
    | 'assistant-joined-call'
    | 'customer-ended-call'
    | 'customer-did-not-answer'
    | 'customer-did-not-give-microphone-permission'
    | 'assistant-said-end-call-phrase'
    | 'unknown-error'
    | 'voicemail'
    | 'vonage-disconnected'
    | 'vonage-failed-to-connect-call'
    | 'phone-call-provider-closed-websocket';
  cost?: number;
  recordingUrl?: string;
  transcript?: string;
  summary?: string;
  messages?: VapiMessage[];
  metadata?: Record<string, any>;
}

export interface VapiPhoneNumber {
  number: string;
  twilioPhoneNumber?: string;
  vonagePhoneNumber?: string;
}

export interface VapiCustomer {
  number?: string;
  name?: string;
  email?: string;
  metadata?: Record<string, any>;
}

export interface VapiAssistant {
  id: string;
  name?: string;
  model?: {
    provider: string;
    model: string;
  };
  voice?: {
    provider: string;
    voiceId: string;
  };
  firstMessage?: string;
  transcriber?: {
    provider: string;
    model?: string;
    language?: string;
  };
}

export interface VapiMessage {
  role: 'user' | 'assistant' | 'system' | 'function';
  message?: string;
  time?: number;
  endTime?: number;
  secondsFromStart?: number;
  duration?: number;
  name?: string;
  args?: string;
  result?: string;
}

export interface VapiFunctionCall {
  name: string;
  parameters: Record<string, any>;
}

// Webhook event message types

export interface AssistantRequestMessage {
  type: 'assistant-request';
  call: VapiCall;
  timestamp: string;
}

export interface StatusUpdateMessage {
  type: 'status-update';
  status: VapiCall['status'];
  call: VapiCall;
  timestamp: string;
  messages?: VapiMessage[];
}

export interface FunctionCallMessage {
  type: 'function-call';
  functionCall: VapiFunctionCall;
  call: VapiCall;
  timestamp: string;
}

export interface EndOfCallReportMessage {
  type: 'end-of-call-report';
  call: VapiCall;
  endedReason: VapiCall['endedReason'];
  transcript?: string;
  recordingUrl?: string;
  summary?: string;
  messages?: VapiMessage[];
  timestamp: string;
  artifact?: {
    messages?: VapiMessage[];
    messagesOpenAIFormatted?: any[];
  };
}

export interface TranscriptMessage {
  type: 'transcript';
  role: 'user' | 'assistant';
  transcript: string;
  call: VapiCall;
  timestamp: string;
}

export interface HangMessage {
  type: 'hang';
  call: VapiCall;
  timestamp: string;
}

export interface SpeechUpdateMessage {
  type: 'speech-update';
  role: 'user' | 'assistant';
  status: 'started' | 'stopped';
  call: VapiCall;
  timestamp: string;
}

export type VapiWebhookMessage =
  | AssistantRequestMessage
  | StatusUpdateMessage
  | FunctionCallMessage
  | EndOfCallReportMessage
  | TranscriptMessage
  | HangMessage
  | SpeechUpdateMessage;

export interface VapiWebhookPayload {
  message: VapiWebhookMessage;
}

// Assistant request response type
export interface AssistantRequestResponse {
  assistant?: Partial<VapiAssistant> & {
    firstMessage?: string;
    model?: {
      provider: string;
      model: string;
      messages?: Array<{
        role: 'system' | 'user' | 'assistant';
        content: string;
      }>;
    };
    functions?: Array<{
      name: string;
      description?: string;
      parameters?: {
        type: 'object';
        properties: Record<string, any>;
        required?: string[];
      };
    }>;
  };
}

// Function call response type
export interface FunctionCallResponse {
  result: any;
}
