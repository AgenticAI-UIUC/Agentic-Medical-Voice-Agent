export interface StructuredCallSummary {
  intent: string;
  outcome: string;
  reasonCodes: string[];
  nextAction: string;
  generatedAt: string;
}

const EMAIL_REGEX = /\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b/gi;
const PHONE_REGEX = /\b(?:\+?1[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4})\b/g;
const SSN_REGEX = /\b\d{3}-\d{2}-\d{4}\b/g;
const DOB_REGEX = /\b(?:0?[1-9]|1[0-2])[\/-](?:0?[1-9]|[12]\d|3[01])[\/-](?:19|20)?\d{2}\b/g;
const MRN_REGEX = /\b(?:mrn|medical\s*record\s*number)[:\s#-]*\d{5,}\b/gi;

export function redactPhiText(text?: string | null): string {
  if (!text) {
    return '';
  }

  return text
    .replace(EMAIL_REGEX, '[REDACTED_EMAIL]')
    .replace(PHONE_REGEX, '[REDACTED_PHONE]')
    .replace(SSN_REGEX, '[REDACTED_SSN]')
    .replace(DOB_REGEX, '[REDACTED_DOB]')
    .replace(MRN_REGEX, '[REDACTED_MRN]');
}

export function maskTextForUi(text?: string | null, allowPhi = false): string {
  if (!text) {
    return '';
  }

  return allowPhi ? text : redactPhiText(text);
}

function inferIntent(summaryText: string): string {
  const lower = summaryText.toLowerCase();

  if (lower.includes('appointment')) return 'appointment-management';
  if (lower.includes('refill') || lower.includes('prescription')) return 'medication-request';
  if (lower.includes('billing') || lower.includes('insurance')) return 'billing-support';
  if (lower.includes('symptom') || lower.includes('pain')) return 'symptom-triage';
  if (lower.includes('lab') || lower.includes('result')) return 'lab-follow-up';

  return 'general-medical-inquiry';
}

function inferOutcome(endedReason?: string, summaryText = ''): string {
  const lowerSummary = summaryText.toLowerCase();

  if (!endedReason && lowerSummary.includes('resolved')) return 'resolved';
  if (endedReason === 'assistant-ended-call' || endedReason === 'customer-ended-call') {
    return lowerSummary.includes('follow up') ? 'follow-up-required' : 'completed';
  }

  if (endedReason === 'customer-did-not-answer') return 'no-answer';
  if (endedReason === 'unknown-error' || endedReason?.includes('failed')) return 'technical-failure';

  return 'inconclusive';
}

function inferNextAction(summaryText: string): string {
  if (!summaryText) {
    return 'Review call details and assign a follow-up owner.';
  }

  const sentences = summaryText
    .split(/(?<=[.!?])\s+/)
    .map((sentence) => sentence.trim())
    .filter(Boolean);

  const preferred = sentences.find((sentence) => {
    const lower = sentence.toLowerCase();
    return (
      lower.includes('next step') ||
      lower.includes('next action') ||
      lower.includes('follow up') ||
      lower.includes('should')
    );
  });

  return preferred ?? 'Clinical staff should review and schedule a follow-up if required.';
}

export function buildStructuredSummary(params: {
  endedReason?: string;
  summary?: string;
  transcript?: string;
}): StructuredCallSummary {
  const summaryText = params.summary?.trim() || params.transcript?.trim() || '';
  const reasonCodes = [params.endedReason ?? 'unknown-ended-reason'];

  if (summaryText.toLowerCase().includes('urgent')) {
    reasonCodes.push('urgent-follow-up');
  }

  if (summaryText.toLowerCase().includes('escalat')) {
    reasonCodes.push('escalated-to-staff');
  }

  return {
    intent: inferIntent(summaryText),
    outcome: inferOutcome(params.endedReason, summaryText),
    reasonCodes,
    nextAction: inferNextAction(summaryText),
    generatedAt: new Date().toISOString(),
  };
}
