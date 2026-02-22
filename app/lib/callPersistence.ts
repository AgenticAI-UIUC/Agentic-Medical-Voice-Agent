import type {
  EndOfCallReportMessage,
  StatusUpdateMessage,
  TranscriptMessage,
} from '@/app/types/vapi';
import { buildStructuredSummary, redactPhiText } from '@/app/lib/phi';
import {
  getArtifactExpiry,
  getRecordingBucketName,
  getSupabaseAdminClient,
} from '@/app/lib/supabase';

interface PersistOutcome {
  redactedTranscript?: string;
  structuredSummary?: ReturnType<typeof buildStructuredSummary>;
}

function normalizeTimestamp(value?: string): string {
  if (!value) {
    return new Date().toISOString();
  }

  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? new Date().toISOString() : parsed.toISOString();
}

function parseConfidence(message: TranscriptMessage): number | null {
  const candidate = (message as TranscriptMessage & { confidence?: number }).confidence;
  if (typeof candidate === 'number' && candidate >= 0 && candidate <= 1) {
    return candidate;
  }

  return null;
}

function extractToolCallContext(message: TranscriptMessage): Record<string, unknown> {
  const explicit = (message as TranscriptMessage & { toolCallContext?: Record<string, unknown> })
    .toolCallContext;

  if (explicit && typeof explicit === 'object') {
    return explicit;
  }

  return {
    callMetadata: message.call.metadata ?? null,
  };
}

async function upsertSessionBase(params: {
  callId: string;
  callType?: string;
  status?: string;
  assistantId?: string;
  startedAt?: string;
  endedAt?: string;
  durationSeconds?: number;
  endedReason?: string;
  metadata?: Record<string, unknown>;
  patientIdentifier?: string | null;
}) {
  const supabase = getSupabaseAdminClient();

  const { error } = await supabase.from('call_sessions').upsert(
    {
      call_id: params.callId,
      call_type: params.callType,
      status: params.status,
      assistant_id: params.assistantId,
      started_at: params.startedAt,
      ended_at: params.endedAt,
      duration_seconds: params.durationSeconds,
      ended_reason: params.endedReason,
      patient_identifier: params.patientIdentifier,
      metadata: params.metadata ?? {},
      updated_at: new Date().toISOString(),
    },
    { onConflict: 'call_id' }
  );

  if (error) {
    throw new Error(`Failed to upsert call session: ${error.message}`);
  }
}

async function writeAuditLog(params: {
  action: string;
  tableName: string;
  callId: string;
  metadata?: Record<string, unknown>;
}) {
  const supabase = getSupabaseAdminClient();

  const { error } = await supabase.from('phi_access_audit_logs').insert({
    actor_id: 'system-webhook',
    actor_role: 'system_service',
    action: params.action,
    table_name: params.tableName,
    call_id: params.callId,
    metadata: params.metadata ?? {},
  });

  if (error) {
    console.error('Failed to write audit log:', error.message);
  }
}

async function mirrorRecordingIfConfigured(params: {
  callId: string;
  recordingUrl?: string;
}): Promise<{ bucket?: string; path?: string }> {
  const recordingUrl = params.recordingUrl;
  const shouldMirror = process.env.MIRROR_AUDIO_TO_SUPABASE_STORAGE === 'true';

  if (!recordingUrl || !shouldMirror) {
    return {};
  }

  const response = await fetch(recordingUrl);
  if (!response.ok) {
    throw new Error(`Failed to fetch recording for mirroring: ${response.status}`);
  }

  const contentType = response.headers.get('content-type') ?? 'audio/mpeg';
  const extension = contentType.includes('wav') ? 'wav' : 'mp3';
  const bucket = getRecordingBucketName();
  const storagePath = `${params.callId}/${Date.now()}.${extension}`;
  const bytes = new Uint8Array(await response.arrayBuffer());

  const supabase = getSupabaseAdminClient();
  const { error } = await supabase.storage.from(bucket).upload(storagePath, bytes, {
    contentType,
    upsert: false,
  });

  if (error) {
    throw new Error(`Failed to mirror audio to Supabase Storage: ${error.message}`);
  }

  return { bucket, path: storagePath };
}

export async function persistStatusUpdate(message: StatusUpdateMessage): Promise<void> {
  await upsertSessionBase({
    callId: message.call.id,
    callType: message.call.type,
    status: message.status,
    assistantId: message.call.assistantId,
    startedAt: normalizeTimestamp(message.call.createdAt),
    metadata: message.call.metadata ?? {},
    patientIdentifier: message.call.customer?.number ?? null,
  });

  await writeAuditLog({
    action: 'status-upsert',
    tableName: 'call_sessions',
    callId: message.call.id,
    metadata: { status: message.status },
  });
}

export async function persistTranscriptTurn(message: TranscriptMessage): Promise<void> {
  const supabase = getSupabaseAdminClient();

  await upsertSessionBase({
    callId: message.call.id,
    callType: message.call.type,
    status: message.call.status,
    assistantId: message.call.assistantId,
    startedAt: normalizeTimestamp(message.call.createdAt),
    metadata: message.call.metadata ?? {},
    patientIdentifier: message.call.customer?.number ?? null,
  });

  const { error } = await supabase.from('call_turns_raw').insert({
    call_id: message.call.id,
    speaker: message.role,
    uttered_at: normalizeTimestamp(message.timestamp),
    utterance_text: message.transcript,
    confidence_score: parseConfidence(message),
    tool_call_context: extractToolCallContext(message),
    raw_payload: message,
    expires_at: getArtifactExpiry('raw_turn'),
  });

  if (error) {
    throw new Error(`Failed to persist raw transcript turn: ${error.message}`);
  }

  await writeAuditLog({
    action: 'insert-raw-turn',
    tableName: 'call_turns_raw',
    callId: message.call.id,
    metadata: {
      role: message.role,
      confidence: parseConfidence(message),
    },
  });
}

export async function persistEndOfCallArtifacts(
  message: EndOfCallReportMessage
): Promise<PersistOutcome> {
  const supabase = getSupabaseAdminClient();
  const endedAt = normalizeTimestamp(message.timestamp);

  await upsertSessionBase({
    callId: message.call.id,
    callType: message.call.type,
    status: message.call.status,
    assistantId: message.call.assistantId,
    startedAt: normalizeTimestamp(message.call.createdAt),
    endedAt,
    durationSeconds: message.call.duration,
    endedReason: message.endedReason,
    metadata: message.call.metadata ?? {},
    patientIdentifier: message.call.customer?.number ?? null,
  });

  const transcript = message.transcript ?? '';
  const redactedTranscript = redactPhiText(transcript);
  const structuredSummary = buildStructuredSummary({
    endedReason: message.endedReason,
    summary: message.summary,
    transcript,
  });

  const { bucket, path } = await mirrorRecordingIfConfigured({
    callId: message.call.id,
    recordingUrl: message.recordingUrl,
  });

  const recordingInsert = await supabase.from('call_recordings').upsert(
    {
      call_id: message.call.id,
      provider_recording_url: message.recordingUrl,
      storage_bucket: bucket,
      storage_object_path: path,
      expires_at: getArtifactExpiry('recording_reference'),
      metadata: {
        mirroredToSupabase: Boolean(bucket && path),
      },
    },
    { onConflict: 'call_id' }
  );

  if (recordingInsert.error) {
    throw new Error(`Failed to persist recording metadata: ${recordingInsert.error.message}`);
  }

  const redactedInsert = await supabase.from('call_transcript_artifacts').insert({
    call_id: message.call.id,
    artifact_type: 'redacted_staff',
    transcript_text: redactedTranscript,
    redaction_version: 'v1-regex',
    metadata: {
      source: 'end-of-call-report',
      containsSummary: Boolean(message.summary),
    },
    expires_at: getArtifactExpiry('redacted_transcript'),
  });

  if (redactedInsert.error) {
    throw new Error(`Failed to persist redacted transcript: ${redactedInsert.error.message}`);
  }

  const summaryInsert = await supabase.from('call_structured_summaries').upsert(
    {
      call_id: message.call.id,
      intent: structuredSummary.intent,
      outcome: structuredSummary.outcome,
      reason_codes: structuredSummary.reasonCodes,
      next_action: structuredSummary.nextAction,
      summary_text: message.summary,
      analytics: {
        endedReason: message.endedReason,
        generatedAt: structuredSummary.generatedAt,
      },
      expires_at: getArtifactExpiry('structured_summary'),
    },
    { onConflict: 'call_id' }
  );

  if (summaryInsert.error) {
    throw new Error(`Failed to persist structured summary: ${summaryInsert.error.message}`);
  }

  await writeAuditLog({
    action: 'insert-end-of-call-artifacts',
    tableName: 'call_sessions',
    callId: message.call.id,
    metadata: {
      recordingMirrored: Boolean(bucket && path),
      endedReason: message.endedReason,
    },
  });

  return {
    redactedTranscript,
    structuredSummary,
  };
}
