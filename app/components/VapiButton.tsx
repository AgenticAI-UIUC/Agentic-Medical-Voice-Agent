import React from 'react';
import { useVapi } from '../hooks/useVapi';

interface VapiButtonProps {
  publicKey?: string;
  assistantId?: string;
  baseUrl?: string;
  className?: string;
  children?: React.ReactNode;
}

export const VapiButton: React.FC<VapiButtonProps> = ({
  publicKey = process.env.REACT_APP_VAPI_PUBLIC_KEY,
  assistantId = process.env.REACT_APP_VAPI_ASSISTANT_ID,
  baseUrl = process.env.REACT_APP_VAPI_BASE_URL,
  className,
  children,
}) => {
  const { startCall, endCall, isSessionActive, isLoading, error } = useVapi({
    publicKey: publicKey || '',
    assistantId: assistantId || '',
    baseUrl,
  });

  const handleClick = () => {
    if (isSessionActive) {
      endCall();
    } else {
      startCall();
    }
  };

  if (!publicKey || !assistantId) {
    return (
      <div className="text-red-500 p-2">
        Missing Vapi configuration. Please set environment variables.
      </div>
    );
  }

  return (
    <>
      <button
        onClick={handleClick}
        disabled={isLoading}
        className={className || "bg-blue-500 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded disabled:opacity-50"}
      >
        {children || (isLoading ? 'Connecting...' : isSessionActive ? 'End Call' : 'Start Call')}
      </button>
      {error && (
        <div className="text-red-500 mt-2 text-sm">
          Error: {error}
        </div>
      )}
    </>
  );
};
