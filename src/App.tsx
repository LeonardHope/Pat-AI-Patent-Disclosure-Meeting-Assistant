import { useCallback } from "react";
import { useWebSocket } from "./hooks/useWebSocket";
import { useMeetingStore } from "./stores/meetingStore";
import { MeetingControls } from "./components/MeetingControls";
import { Layout } from "./components/Layout";
import { SettingsPanel } from "./components/SettingsPanel";
import { PostMeetingSummary } from "./components/PostMeetingSummary";

export default function App() {
  const { send } = useWebSocket();

  const selectedApp = useMeetingStore((s) => s.selectedApp);
  const selectedMic = useMeetingStore((s) => s.selectedMic);
  const micEnabled = useMeetingStore((s) => s.micEnabled);

  const handleStartMeeting = useCallback(() => {
    fetch("/api/settings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        audio: {
          app_bundle_id: selectedApp,
          microphone_device: selectedMic,
          capture_microphone: micEnabled,
        },
      }),
    }).then(() => {
      send({
        type: "start_meeting",
        app_bundle_id: selectedApp,
        mic_device: selectedMic,
      });
    });
  }, [send, selectedApp, selectedMic, micEnabled]);

  const handleStopMeeting = useCallback(() => {
    send({ type: "stop_meeting" });
  }, [send]);

  const handleGenerateSummary = useCallback(() => {
    send({ type: "generate_summary" });
  }, [send]);

  const handleReset = useCallback(() => {
    send({ type: "reset" });
    useMeetingStore.getState().reset();
  }, [send]);

  return (
    <div className="h-full flex flex-col bg-gray-950">
      <MeetingControls
        onStopMeeting={handleStopMeeting}
        onGenerateSummary={handleGenerateSummary}
        onReset={handleReset}
      />
      <Layout onStartMeeting={handleStartMeeting} send={send} />
      <SettingsPanel />
      <PostMeetingSummary />
    </div>
  );
}
