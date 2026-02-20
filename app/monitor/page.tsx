import CallMonitor from '../components/CallMonitor';

export default function MonitorPage() {
  return (
    <main className="min-h-screen bg-gray-100 py-8">
      <div className="container mx-auto">
        <div className="mb-6">
          <h1 className="text-3xl font-bold text-gray-900">
            Vapi Call Monitor
          </h1>
          <p className="text-gray-800 mt-2">
            Real-time monitoring of phone calls and transcripts
          </p>
        </div>
        <CallMonitor />
      </div>
    </main>
  );
}
