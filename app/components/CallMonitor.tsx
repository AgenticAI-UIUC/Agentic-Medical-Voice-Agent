'use client';

import { useEffect, useState, useRef } from 'react';
import { maskTextForUi } from '@/app/lib/phi';

interface TranscriptMessage {
  id: string;
  role: 'user' | 'assistant';
  transcript: string;
  redactedTranscript?: string;
  timestamp: string;
}

interface CallStatus {
  status: string;
  callId: string;
  timestamp: string;
}

interface CallReport {
  callId: string;
  duration: number;
  endedReason: string;
  recordingUrl?: string;
  transcript?: string;
  redactedTranscript?: string;
  summary?: string;
  structuredSummary?: {
    intent: string;
    outcome: string;
    reasonCodes: string[];
    nextAction: string;
    generatedAt: string;
  };
  timestamp: string;
}

export default function CallMonitor() {
  const allowPhiView = process.env.NEXT_PUBLIC_ALLOW_MONITOR_PHI_VIEW === 'true';
  const [connected, setConnected] = useState(false);
  const [transcripts, setTranscripts] = useState<TranscriptMessage[]>([]);
  const [callStatus, setCallStatus] = useState<CallStatus | null>(null);
  const [callReport, setCallReport] = useState<CallReport | null>(null);
  const transcriptEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // Connect to SSE endpoint
    const eventSource = new EventSource('/api/vapi/events');

    eventSource.onopen = () => {
      console.log('SSE Connection established');
      setConnected(true);
    };

    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        console.log('Received SSE event:', data);

        switch (data.type) {
          case 'connected':
            console.log('Connected with client ID:', data.clientId);
            break;

          case 'transcript':
            // Add new transcript message
            setTranscripts((prev) => [
              ...prev,
              {
                id: `${data.data.callId}-${Date.now()}`,
                role: data.data.role,
                transcript: data.data.transcript,
                redactedTranscript: data.data.redactedTranscript,
                timestamp: data.data.timestamp,
              },
            ]);
            break;

          case 'status-update':
            setCallStatus(data.data);
            // Clear transcripts when new call starts
            if (data.data.status === 'ringing') {
              setTranscripts([]);
              setCallReport(null);
            }
            break;

          case 'end-of-call-report':
            setCallReport(data.data);
            break;
        }
      } catch (error) {
        console.error('Error parsing SSE data:', error);
      }
    };

    eventSource.onerror = (error) => {
      console.error('SSE error:', error);
      setConnected(false);
    };

    // Cleanup on unmount
    return () => {
      eventSource.close();
    };
  }, []);

  // Auto-scroll to bottom when new transcripts arrive
  useEffect(() => {
    transcriptEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [transcripts]);

  return (
    <div className="max-w-4xl mx-auto p-6 space-y-6">
      {/* Connection Status */}
      <div className="flex items-center justify-between p-4 bg-gray-50 rounded-lg border">
        <div className="flex items-center gap-2">
          <div
            className={`w-3 h-3 rounded-full ${
              connected ? 'bg-green-500' : 'bg-red-500'
            }`}
          />
          <span className="font-medium text-gray-900">
            {connected ? 'Connected to Vapi' : 'Disconnected'}
          </span>
        </div>
        {callStatus && (
          <div className="text-sm text-gray-800">
            Status: <span className="font-medium text-gray-900">{callStatus.status}</span>
          </div>
        )}
      </div>

      {/* Real-time Transcripts */}
      <div className="bg-white rounded-lg border shadow-sm">
        <div className="p-4 border-b bg-gray-50">
          <h2 className="text-lg font-semibold text-gray-900">Live Transcript</h2>
          {transcripts.length === 0 && (
            <p className="text-sm text-gray-700 mt-1">
              Waiting for call to start...
            </p>
          )}
        </div>
        <div className="p-4 space-y-4 max-h-96 overflow-y-auto">
          {transcripts.map((message) => (
            <div
              key={message.id}
              className={`flex ${
                message.role === 'assistant' ? 'justify-start' : 'justify-end'
              }`}
            >
              <div
                className={`max-w-[80%] rounded-lg p-3 ${
                  message.role === 'assistant'
                    ? 'bg-blue-50 border border-blue-200'
                    : 'bg-green-50 border border-green-200'
                }`}
              >
                <div className="text-xs font-medium mb-1 text-gray-700">
                  {message.role === 'assistant' ? 'Assistant' : 'Patient'}
                </div>
                <div className="text-sm text-gray-900">
                  {maskTextForUi(
                    message.redactedTranscript ?? message.transcript,
                    allowPhiView
                  )}
                </div>
                <div className="text-xs text-gray-600 mt-1">
                  {new Date(message.timestamp).toLocaleTimeString()}
                </div>
              </div>
            </div>
          ))}
          <div ref={transcriptEndRef} />
        </div>
      </div>

      {/* Call Report (shown after call ends) */}
      {callReport && (
        <div className="bg-white rounded-lg border shadow-sm">
          <div className="p-4 border-b bg-gray-50">
            <h2 className="text-lg font-semibold text-gray-900">Call Summary</h2>
          </div>
          <div className="p-4 space-y-3">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <div className="text-sm font-medium text-gray-700">Call ID</div>
                <div className="font-mono text-sm text-gray-900">{callReport.callId}</div>
              </div>
              <div>
                <div className="text-sm font-medium text-gray-700">Duration</div>
                <div className="font-medium text-gray-900">
                  {Math.floor(callReport.duration / 60)}m{' '}
                  {callReport.duration % 60}s
                </div>
              </div>
              <div>
                <div className="text-sm font-medium text-gray-700">Ended Reason</div>
                <div className="font-medium text-gray-900">{callReport.endedReason}</div>
              </div>
              <div>
                <div className="text-sm font-medium text-gray-700">Timestamp</div>
                <div className="text-sm text-gray-900">
                  {new Date(callReport.timestamp).toLocaleString()}
                </div>
              </div>
            </div>

            {callReport.summary && (
              <div>
                <div className="text-sm font-medium text-gray-700 mb-1">Summary</div>
                <div className="text-sm text-gray-900 bg-gray-50 p-3 rounded border">
                  {maskTextForUi(callReport.summary, allowPhiView)}
                </div>
              </div>
            )}

            {callReport.structuredSummary && (
              <div>
                <div className="text-sm font-medium text-gray-700 mb-1">
                  Structured Summary
                </div>
                <div className="text-sm text-gray-900 bg-gray-50 p-3 rounded border space-y-1">
                  <div>
                    <span className="font-medium">Intent:</span>{' '}
                    {callReport.structuredSummary.intent}
                  </div>
                  <div>
                    <span className="font-medium">Outcome:</span>{' '}
                    {callReport.structuredSummary.outcome}
                  </div>
                  <div>
                    <span className="font-medium">Reason Codes:</span>{' '}
                    {callReport.structuredSummary.reasonCodes.join(', ')}
                  </div>
                  <div>
                    <span className="font-medium">Next Action:</span>{' '}
                    {callReport.structuredSummary.nextAction}
                  </div>
                </div>
              </div>
            )}

            {callReport.recordingUrl && (
              <div>
                <div className="text-sm font-medium text-gray-700 mb-2">
                  Call Recording (MP3)
                </div>
                <audio
                  controls
                  src={callReport.recordingUrl}
                  className="w-full"
                >
                  Your browser does not support the audio element.
                </audio>
                <a
                  href={callReport.recordingUrl}
                  download
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-block mt-2 text-sm text-blue-600 hover:text-blue-800 underline font-medium"
                >
                  Download Recording
                </a>
              </div>
            )}

            {callReport.transcript && (
              <div>
                <div className="text-sm font-medium text-gray-700 mb-1">
                  Full Transcript
                </div>
                <div className="text-sm text-gray-900 bg-gray-50 p-3 rounded border max-h-48 overflow-y-auto whitespace-pre-wrap">
                  {maskTextForUi(
                    callReport.redactedTranscript ?? callReport.transcript,
                    allowPhiView
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
