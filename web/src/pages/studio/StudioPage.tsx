/** Setup Studio — chat-style config, presets, voices, privacy, plan.
 * The demo-script path: describe Ruth → review → save → (key or skip) →
 * the dashboard shows the whale on its dock and the next check-in. */

import { useCallback, useEffect, useRef, useState } from "react";
import { apiGet } from "../../lib/api";
import type { Contact, Preset, StudioCurrent, Voice } from "../../lib/types";
import { Button, Card } from "../../components/ui";
import AdvancedPanel from "./AdvancedPanel";
import ContactsCard from "./ContactsCard";
import ScheduleCard from "./ScheduleCard";
import PersonalityPicker from "./PersonalityPicker";
import PrivacyPanel from "./PrivacyPanel";
import StudioChat from "./StudioChat";

export default function StudioPage({ onDone }: { onDone: () => void }) {
  const [presets, setPresets] = useState<Preset[]>([]);
  const [voices, setVoices] = useState<Voice[]>([]);
  const [role, setRole] = useState("companion");
  const [sub, setSub] = useState<string | null>(null);
  const [voiceKey, setVoiceKey] = useState("elder_male");
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [savedName, setSavedName] = useState<string | null>(null);

  // The picker state also feeds StudioChat's save — read it via ref so the
  // chat card never re-renders (and loses its draft) on a picker click.
  const pickerState = useRef({ role, sub, voiceKey });
  pickerState.current = { role, sub, voiceKey };
  const saveExtras = useCallback(
    () => ({
      role: pickerState.current.role,
      sub_preset: pickerState.current.sub,
      voice: pickerState.current.voiceKey,
    }),
    [],
  );

  useEffect(() => {
    apiGet<Preset[]>("/api/v1/presets")
      .then(setPresets)
      .catch(() => setPresets([]));
    apiGet<Voice[]>("/api/v1/voices")
      .then(setVoices)
      .catch(() => setVoices([]));
    apiGet<StudioCurrent>("/api/v1/studio/current?device_id=1")
      .then((current) => {
        setRole(current.role);
        setSub(current.sub_preset);
        setVoiceKey(current.voice);
      })
      .catch(() => undefined);
  }, []);

  const onSaved = useCallback((personName: string) => {
    setSavedName(personName);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }, []);

  return (
    <div className="space-y-6">
      {savedName !== null && (
        <Card className="border-sage bg-sage-soft/60">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="text-lg">
              <span className="font-semibold">All set — Meemoo knows {savedName}.</span>{" "}
              <span className="text-ink-soft">
                The whale is on its dock, ready for the next check-in.
              </span>
            </p>
            <Button onClick={onDone}>See the dashboard</Button>
          </div>
        </Card>
      )}

      <StudioChat onSaved={onSaved} saveExtras={saveExtras} />

      <PersonalityPicker
        presets={presets}
        voices={voices}
        role={role}
        sub={sub}
        voiceKey={voiceKey}
        onRole={setRole}
        onSub={setSub}
        onVoice={setVoiceKey}
      />

      <ContactsCard onChanged={setContacts} />

      <ScheduleCard />

      <PrivacyPanel contacts={contacts} />

      <AdvancedPanel />
    </div>
  );
}
