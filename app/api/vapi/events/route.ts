import { NextRequest } from 'next/server';

// Store for active SSE connections
const clients = new Map<string, ReadableStreamDefaultController>();

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

// Server-Sent Events endpoint for streaming Vapi events to frontend
export async function GET(request: NextRequest) {
  const clientId = crypto.randomUUID();

  // Create a readable stream for SSE
  const stream = new ReadableStream({
    start(controller) {
      // Store this client's controller
      clients.set(clientId, controller);

      // Send initial connection message
      const encoder = new TextEncoder();
      controller.enqueue(
        encoder.encode(`data: ${JSON.stringify({ type: 'connected', clientId })}\n\n`)
      );

      console.log(`SSE client connected: ${clientId}`);
    },
    cancel() {
      // Clean up when client disconnects
      clients.delete(clientId);
      console.log(`SSE client disconnected: ${clientId}`);
    },
  });

  // Return SSE response
  return new Response(stream, {
    headers: {
      'Content-Type': 'text/event-stream',
      'Cache-Control': 'no-cache',
      'Connection': 'keep-alive',
    },
  });
}

// Function to broadcast events to all connected clients
export function broadcastToClients(event: any) {
  const encoder = new TextEncoder();
  const data = `data: ${JSON.stringify(event)}\n\n`;

  clients.forEach((controller, clientId) => {
    try {
      controller.enqueue(encoder.encode(data));
    } catch (error) {
      console.error(`Error sending to client ${clientId}:`, error);
      clients.delete(clientId);
    }
  });
}

// Export clients for external access
export { clients };
