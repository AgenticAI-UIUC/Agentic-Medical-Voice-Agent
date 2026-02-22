import { NextRequest, NextResponse } from 'next/server';
import type {
  VapiWebhookPayload,
  StatusUpdateMessage,
  FunctionCallMessage,
  EndOfCallReportMessage,
  TranscriptMessage,
  HangMessage,
  SpeechUpdateMessage,
  AssistantRequestResponse,
  FunctionCallResponse,
} from '@/app/types/vapi';
import { broadcastToClients } from '../events/route';
import {
  persistEndOfCallArtifacts,
  persistStatusUpdate,
  persistTranscriptTurn,
} from '@/app/lib/callPersistence';
import { redactPhiText } from '@/app/lib/phi';

export const runtime = 'nodejs';

export async function POST(request: NextRequest) {
  try {
    // Parse the incoming webhook payload
    const payload: VapiWebhookPayload = await request.json();

    const { message } = payload;
    const eventType = message.type;

    console.log('Received Vapi webhook:', eventType);
    console.log('Payload:', JSON.stringify(message, null, 2));

    // Handle different webhook event types
    switch (eventType) {
      case 'assistant-request':
        // Fired when the assistant is requested
        console.log('Assistant requested for call');
        return handleAssistantRequest();

      case 'status-update':
        // Fired when call status changes (e.g., ringing, in-progress, ended)
        console.log('Call status update:', message);
        return handleStatusUpdate(message);

      case 'function-call':
        // Fired when assistant wants to call a function
        console.log('Function call requested:', message);
        return handleFunctionCall(message);

      case 'end-of-call-report':
        // Fired when call ends with full report
        console.log('Call ended. Report:', message);
        return handleEndOfCallReport(message);

      case 'transcript':
        // Fired for real-time transcript updates
        console.log('Transcript update:', message.transcript);
        return handleTranscript(message);

      case 'hang':
        // Fired when call is hung up
        console.log('Call hung up');
        return handleHang(message);

      case 'speech-update':
        // Fired during speech recognition updates
        return handleSpeechUpdate(message);

      default:
        console.log('Unknown event type:', eventType);
        return NextResponse.json({
          success: true,
          message: 'Event received but not handled',
        });
    }
  } catch (error) {
    console.error('Error processing webhook:', error);
    return NextResponse.json(
      { error: 'Failed to process webhook' },
      { status: 500 }
    );
  }
}

// Handler functions for each event type

function handleAssistantRequest(): NextResponse<AssistantRequestResponse> {
  // Return assistant configuration if needed
  // This allows dynamic assistant configuration per call
  const response: AssistantRequestResponse = {
    assistant: {
      // You can customize the assistant config here
      // or return the default assistant
      firstMessage: 'Hello! This is your medical voice assistant. How can I help you today?',
      // Optionally override model settings
      // model: {
      //   provider: 'openai',
      //   model: 'gpt-4',
      // },
    },
  };

  return NextResponse.json(response);
}

async function handleStatusUpdate(message: StatusUpdateMessage) {
  // Handle call status updates
  // You might want to log this to a database
  const { status, call } = message;
  console.log('Call status:', status, 'Call ID:', call.id);

  // Broadcast to frontend clients
  broadcastToClients({
    type: 'status-update',
    data: { status, callId: call.id, timestamp: new Date().toISOString() },
  });

  try {
    await persistStatusUpdate(message);
  } catch (error) {
    console.error('Status update persistence skipped:', error);
  }

  return NextResponse.json({ success: true });
}

function handleFunctionCall(
  message: FunctionCallMessage
): NextResponse<FunctionCallResponse> {
  // Handle function calls from the assistant
  // Example: looking up patient records, scheduling appointments, etc.
  const { functionCall, call } = message;
  const { name, parameters } = functionCall;

  console.log(`Function called: ${name}`, parameters);
  console.log('Call ID:', call.id);

  // Example function implementations
  let result: Record<string, unknown>;

  switch (name) {
    case 'scheduleAppointment':
      // Implement appointment scheduling logic
      result = {
        success: true,
        appointmentId: 'APT-' + Date.now(),
        scheduledTime: parameters.time,
      };
      break;

    case 'getPatientInfo':
      // Implement patient lookup logic
      result = {
        success: true,
        patient: {
          name: 'Sample Patient',
          lastVisit: '2024-01-15',
        },
      };
      break;

    case 'checkSymptoms':
      // Implement symptom checking logic
      result = {
        success: true,
        recommendation: 'Please consult with your primary care physician.',
      };
      break;

    default:
      result = {
        success: false,
        error: `Unknown function: ${name}`,
      };
  }

  return NextResponse.json({ result });
}

async function handleEndOfCallReport(message: EndOfCallReportMessage) {
  // Process end-of-call analytics
  // Store in database, send notifications, etc.
  const {
    call,
    endedReason,
    transcript,
    recordingUrl,
    summary,
    messages,
  } = message;

  console.log('Call Summary:', {
    callId: call.id,
    duration: call.duration,
    endedReason,
    recordingUrl,
    summary,
    messageCount: messages?.length,
  });

  let persistedArtifacts:
    | Awaited<ReturnType<typeof persistEndOfCallArtifacts>>
    | undefined;
  const allowPhiStream = process.env.ALLOW_MONITOR_PHI_STREAM === 'true';

  try {
    persistedArtifacts = await persistEndOfCallArtifacts(message);
  } catch (error) {
    console.error('End-of-call persistence skipped:', error);
  }

  const redactedTranscript = persistedArtifacts?.redactedTranscript ?? redactPhiText(transcript);
  const redactedSummary = redactPhiText(summary);

  // Broadcast end-of-call report to frontend clients
  broadcastToClients({
    type: 'end-of-call-report',
    data: {
      callId: call.id,
      duration: call.duration,
      endedReason,
      recordingUrl,
      transcript: allowPhiStream ? transcript : redactedTranscript,
      redactedTranscript,
      summary: allowPhiStream ? summary : redactedSummary,
      structuredSummary: persistedArtifacts?.structuredSummary,
      messages,
      timestamp: new Date().toISOString(),
    },
  });

  return NextResponse.json({ success: true });
}

async function handleTranscript(message: TranscriptMessage) {
  // Process real-time transcripts
  // You can use this for live monitoring or sentiment analysis
  const { transcript, role, call } = message;
  const allowPhiStream = process.env.ALLOW_MONITOR_PHI_STREAM === 'true';
  const redactedTranscript = redactPhiText(transcript);

  console.log(`[${call.id}] ${role}: ${transcript}`);

  // Broadcast transcript to frontend clients
  broadcastToClients({
    type: 'transcript',
    data: {
      transcript: allowPhiStream ? transcript : redactedTranscript,
      redactedTranscript,
      role,
      callId: call.id,
      timestamp: new Date().toISOString(),
    },
  });

  try {
    await persistTranscriptTurn(message);
  } catch (error) {
    console.error('Transcript persistence skipped:', error);
  }

  return NextResponse.json({ success: true });
}

function handleHang(message: HangMessage) {
  // Handle call hangup
  const { call } = message;
  console.log('Call was hung up. Call ID:', call.id);

  // TODO: Clean up any ongoing processes
  // TODO: Save final call state

  return NextResponse.json({ success: true });
}

function handleSpeechUpdate(message: SpeechUpdateMessage) {
  // Handle speech recognition updates
  const { role, status, call } = message;
  console.log(`Speech ${status} for ${role} on call ${call.id}`);

  return NextResponse.json({ success: true });
}

// Optional: Webhook signature verification
// Uncomment and implement if Vapi provides webhook secrets
/*
function verifyWebhookSignature(request: NextRequest): boolean {
  const signature = request.headers.get('x-vapi-signature');
  const webhookSecret = process.env.VAPI_WEBHOOK_SECRET;

  if (!signature || !webhookSecret) {
    return false;
  }

  // Implement signature verification logic here
  // This depends on Vapi's signature algorithm

  return true;
}
*/
