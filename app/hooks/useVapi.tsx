import { useState, useCallback, useEffect } from 'react';
import Vapi from '@vapi-ai/web';

interface VapiConfig {
  publicKey: string;
  assistantId: string;
  baseUrl?: string;
}

interface VapiState {
  isSessionActive: boolean;
  isLoading: boolean;
  error: string | null;
}

export const useVapi = (config: VapiConfig) => {
  const [vapi, setVapi] = useState<Vapi | null>(null);
  const [state, setState] = useState<VapiState>({
    isSessionActive: false,
    isLoading: false,
    error: null,
  });

  useEffect(() => {
    const vapiInstance = new Vapi(config.publicKey, config.baseUrl);
    setVapi(vapiInstance);

    const handleCallStart = () => {
      setState(prev => ({ ...prev, isSessionActive: true, isLoading: false }));
    };

    const handleCallEnd = () => {
      setState(prev => ({ ...prev, isSessionActive: false, isLoading: false }));
    };

    const handleError = (error: any) => {
      setState(prev => ({ ...prev, error: error.message, isLoading: false }));
    };

    vapiInstance.on('call-start', handleCallStart);
    vapiInstance.on('call-end', handleCallEnd);
    vapiInstance.on('error', handleError);

    return () => {
      vapiInstance.off('call-start', handleCallStart);
      vapiInstance.off('call-end', handleCallEnd);
      vapiInstance.off('error', handleError);
    };
  }, [config.publicKey, config.baseUrl]);

  const startCall = useCallback(async () => {
    if (!vapi) return;

    setState(prev => ({ ...prev, isLoading: true, error: null }));
    
    try {
      await vapi.start(config.assistantId);
    } catch (error: any) {
      setState(prev => ({ ...prev, error: error.message, isLoading: false }));
    }
  }, [vapi, config.assistantId]);

  const endCall = useCallback(() => {
    if (!vapi) return;
    vapi.stop();
  }, [vapi]);

  return {
    startCall,
    endCall,
    ...state,
  };
};
