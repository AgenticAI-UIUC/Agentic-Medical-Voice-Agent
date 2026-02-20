# Agentic Medical Voice Agent

An AI-powered medical voice assistant built with Next.js and [Vapi](https://vapi.ai) for handling patient calls, real-time transcription, and call monitoring.

## Features

- **Voice Assistant Integration**: Powered by Vapi for natural voice conversations
- **Real-time Call Monitoring**: Live transcription dashboard for ongoing calls
- **Call Analytics**: Automatic summaries, transcripts, and recordings
- **Webhook System**: Server-side event handling for call events
- **Server-Sent Events (SSE)**: Real-time updates to the frontend

## Tech Stack

- **Framework**: Next.js 16 with App Router
- **Voice AI**: Vapi Web SDK
- **Styling**: Tailwind CSS v4
- **Language**: TypeScript
- **Deployment**: Vercel

## Project Structure

```
app/
├── api/
│   └── vapi/
│       ├── webhook/         # Receives Vapi webhook events
│       │   └── route.ts
│       └── events/          # SSE endpoint for frontend
│           └── route.ts
├── components/
│   ├── CallMonitor.tsx      # Real-time call monitoring UI
│   ├── VapiButton.tsx       # Voice call button
│   └── VapiExample.tsx      # Main demo interface
├── monitor/
│   └── page.tsx             # Call monitoring page
├── types/
│   └── vapi.ts              # TypeScript type definitions
└── page.tsx                 # Homepage
```

## Getting Started

### Prerequisites

- Node.js 18+ installed
- A [Vapi](https://vapi.ai) account
- (Optional) ngrok for local webhook testing

### 1. Clone and Install

```bash
git clone <your-repo-url>
cd Agentic-Medical-Voice-Agent
npm install
```

### 2. Environment Setup

Create a `.env.local` file in the root directory:

```bash
# Vapi Configuration (Client-side)
NEXT_PUBLIC_VAPI_PUBLIC_KEY=your_vapi_public_key
NEXT_PUBLIC_VAPI_ASSISTANT_ID=your_assistant_id
NEXT_PUBLIC_VAPI_BASE_URL=https://api.vapi.ai

# Webhook Configuration (Server-side - Optional)
# VAPI_WEBHOOK_SECRET=your_webhook_secret
```

**Get your Vapi credentials:**
1. Sign up at [vapi.ai](https://vapi.ai)
2. Create an assistant in the dashboard
3. Copy your Public Key and Assistant ID

### 3. Run Development Server

```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) to see the app.

### 4. Test Webhooks Locally (Optional)

To receive webhook events during local development:

```bash
# In a separate terminal
ngrok http 3000
```

Copy the ngrok HTTPS URL and configure it in your Vapi dashboard:
```
https://your-ngrok-url.ngrok.io/api/vapi/webhook
```

## Pages & Routes

### User Interfaces

- `/` - Main page with voice call button
- `/monitor` - Real-time call monitoring dashboard

### API Routes

- `/api/vapi/webhook` - Receives webhook events from Vapi (POST)
- `/api/vapi/events` - SSE endpoint for real-time frontend updates (GET)

## How It Works

### Call Flow

```
1. User initiates call → Vapi handles voice interaction
2. Vapi sends webhook events → /api/vapi/webhook
3. Backend broadcasts events → SSE stream (/api/vapi/events)
4. Frontend receives updates → Real-time UI update
```

### Webhook Events

The system handles these Vapi webhook events:

- `assistant-request` - Configure assistant per call
- `status-update` - Call status changes (ringing, in-progress, ended)
- `transcript` - Real-time speech-to-text updates
- `function-call` - Execute custom functions during calls
- `end-of-call-report` - Full call analytics (transcript, recording, summary)
- `hang` - Call ended
- `speech-update` - Speech recognition status

### Data You Receive

**During Call:**
- Real-time text transcripts (both user and assistant)
- Call status updates

**After Call:**
- MP3 recording URL
- Full transcript
- Call summary
- Duration and metadata

## Deployment to Vercel

### 1. Push to GitHub

```bash
git add .
git commit -m "Deploy medical voice agent"
git push origin main
```

### 2. Deploy to Vercel

1. Go to [vercel.com](https://vercel.com) and import your repository
2. Configure project:
   - **Framework Preset**: Next.js
   - **Root Directory**: `./`
   - **Build Command**: `npm run build`

### 3. Add Environment Variables

In Vercel Dashboard → Settings → Environment Variables, add:

```
NEXT_PUBLIC_VAPI_PUBLIC_KEY=your_vapi_public_key
NEXT_PUBLIC_VAPI_ASSISTANT_ID=your_assistant_id
NEXT_PUBLIC_VAPI_BASE_URL=https://api.vapi.ai
```

Make sure to add for **all environments** (Production, Preview, Development).

### 4. Configure Vapi Webhook

In your Vapi dashboard, set the webhook URL to:

```
https://your-app.vercel.app/api/vapi/webhook
```

### 5. Access Your App

- **Homepage**: `https://your-app.vercel.app`
- **Call Monitor**: `https://your-app.vercel.app/monitor`

## Usage

### Making a Call

1. Open the homepage
2. Click "Start Call" button
3. Allow microphone access
4. Speak naturally with the assistant
5. Click "End Call" when finished

### Monitoring Calls

1. Open `/monitor` page
2. The dashboard shows:
   - Connection status
   - Live transcripts as they happen
   - Call summaries after completion
   - Audio recordings (with playback and download)

## Development

### Build for Production

```bash
npm run build
npm start
```

### Type Checking

```bash
npx tsc --noEmit
```

### Linting

```bash
npm run lint
```

## Features Roadmap

Current TODOs (see code comments):

- [ ] Database integration for storing call records
- [ ] User authentication for monitor page
- [ ] Webhook signature verification for security
- [ ] Sentiment analysis on transcripts
- [ ] Keyword-based alerts
- [ ] Real-time notifications
- [ ] Call analytics dashboard
- [ ] Export call data (CSV, JSON)

## Security Considerations

**Important for Production:**

The webhook endpoint is currently **unprotected**. For production use:

1. Enable webhook signature verification (uncomment in `webhook/route.ts`)
2. Add authentication to the `/monitor` page
3. Implement rate limiting
4. Use HTTPS only
5. Store sensitive data securely

## Resources

- [Vapi Documentation](https://docs.vapi.ai)
- [Next.js Documentation](https://nextjs.org/docs)
- [Tailwind CSS](https://tailwindcss.com/docs)
- [Vercel Deployment](https://vercel.com/docs)

## Troubleshooting

### "Missing Vapi configuration" Error

Make sure your `.env.local` file has the correct environment variables and restart the dev server.

### Webhook Not Receiving Events

- Check your webhook URL in Vapi dashboard
- Ensure ngrok is running for local testing
- Check server logs: `npm run dev`
- Verify webhook URL is accessible (test with curl)

### Monitor Page Shows 404

- Ensure you've pushed all files to your repository
- Check Vercel build logs for errors
- Try redeploying with "Redeploy without cache"

### Frontend Not Updating

- Check browser console for SSE connection errors
- Verify `/api/vapi/events` endpoint is accessible
- Check that webhook is broadcasting events

## License

MIT

## Contributing

Contributions welcome! Please open an issue or submit a pull request.
