import { useCallback, useState } from 'react';
import { useWebSocket } from './hooks/useWebSocket';
import { useAudioCapture } from './hooks/useAudioCapture';
import { StatusBar } from './components/StatusBar';
import { TranscriptPanel } from './components/TranscriptPanel';
import { DemographicsPanel } from './components/DemographicsPanel';
import { ChiefComplaintPanel } from './components/ChiefComplaintPanel';
import { KeywordGuidancePanel } from './components/KeywordGuidancePanel';
import { SummaryPanel } from './components/SummaryPanel';

function App() {
  const {
    status,
    transcript,
    keywordSuggestions,
    encounterState,
    soapNote,
    latencyMs,
    statusMessage,
    error: wsError,
    sendAudio,
    sendControl,
  } = useWebSocket();

  const { isRecording, error: audioError, start, stop } = useAudioCapture(sendAudio);
  const [showSoap, setShowSoap] = useState(false);

  const handleEndSession = useCallback(() => {
    stop();
    sendControl('end_session');
    setShowSoap(true);
  }, [stop, sendControl]);

  const handleReset = useCallback(() => {
    stop();
    sendControl('reset');
    setShowSoap(false);
  }, [stop, sendControl]);

  return (
    <div className="h-screen flex flex-col bg-[radial-gradient(circle_at_top_left,_rgba(14,165,233,0.12),_transparent_35%),radial-gradient(circle_at_bottom_right,_rgba(20,184,166,0.1),_transparent_38%)]">
      <StatusBar
        connectionStatus={status}
        isRecording={isRecording}
        latencyMs={latencyMs}
        statusMessage={statusMessage}
        errorMessage={audioError ?? wsError}
        onStartRecording={start}
        onStopRecording={stop}
        onEndSession={handleEndSession}
        onReset={handleReset}
      />

      <main className="flex-1 flex flex-col gap-3 p-3 md:p-4 min-h-0">
        <section className="min-h-[78px] lg:min-h-[86px]">
          <DemographicsPanel demographics={encounterState?.demographics ?? null} />
        </section>

        <section className="flex-1 grid grid-cols-1 lg:grid-cols-12 gap-3 min-h-0">
          <section className="lg:col-span-9 flex flex-col gap-3 min-h-0">
            <div className="flex-1 min-h-0">
              <KeywordGuidancePanel groups={keywordSuggestions} />
            </div>

            <div className="h-[92px] lg:h-[110px] shrink-0">
              <ChiefComplaintPanel
                chiefComplaint={encounterState?.chief_complaint ?? null}
                structured={encounterState?.chief_complaint_structured ?? null}
              />
            </div>
          </section>

          <section className="lg:col-span-3 min-h-[180px] lg:min-h-0">
            <TranscriptPanel transcript={transcript} />
          </section>
        </section>
      </main>

      {/* SOAP Note modal */}
      {showSoap && (
        <SummaryPanel soapNote={soapNote} onClose={() => setShowSoap(false)} />
      )}
    </div>
  );
}

export default App;
