'use client';

import React from 'react';
import Link from 'next/link';
import { VapiButton } from './VapiButton';

export const VapiExample: React.FC = () => {
  return (
    <div style={{ padding: '20px' }}>
      <h2>Vapi Voice Assistant Example</h2>
      <p>Click the button below to start a voice conversation:</p>

      <VapiButton />

      <div style={{ marginTop: '20px' }}>
        <h3>How it works:</h3>
        <ol>
          <li>Make sure you have set up your environment variables</li>
          <li>Click "Start Call" to begin the conversation</li>
          <li>Speak naturally with the assistant</li>
          <li>Click "End Call" when finished</li>
        </ol>
      </div>

      <div style={{ marginTop: '30px', padding: '15px', backgroundColor: '#f0f0f0', borderRadius: '5px' }}>
        <h3>Monitor Phone Calls</h3>
        <p>View real-time transcripts and call analytics:</p>
        <Link
          href="/monitor"
          style={{
            display: 'inline-block',
            marginTop: '10px',
            padding: '10px 20px',
            backgroundColor: '#0070f3',
            color: 'white',
            textDecoration: 'none',
            borderRadius: '5px',
            fontWeight: 'bold'
          }}
        >
          Open Call Monitor →
        </Link>
      </div>
    </div>
  );
};
