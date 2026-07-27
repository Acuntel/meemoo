/** Role picker → personality sub-presets → voice with audio preview
 * (Constitution Art. VII §3–4). Power users can open the raw context. */

import { useState } from "react";
import type { Preset, Voice } from "../../lib/types";
import { Card, Chip } from "../../components/ui";

const ROLE_EMOJI: Record<string, string> = {
  companion: "🫂",
  trainer: "🏋️",
  hospital_checkin: "🏥",
  tour_guide: "🗺️",
  tutor: "📚",
};

export default function PersonalityPicker({
  presets,
  voices,
  role,
  sub,
  voiceKey,
  onRole,
  onSub,
  onVoice,
}: {
  presets: Preset[];
  voices: Voice[];
  role: string;
  sub: string | null;
  voiceKey: string;
  onRole: (role: string) => void;
  onSub: (sub: string | null) => void;
  onVoice: (voice: string) => void;
}) {
  const [previewNote, setPreviewNote] = useState<string | null>(null);
  const active = presets.find((preset) => preset.role === role) ?? null;

  const preview = async (character: string) => {
    setPreviewNote(null);
    try {
      const response = await fetch(
        `/api/v1/voice/preview?character=${encodeURIComponent(character)}`,
      );
      if (!response.ok) {
        const body = (await response.json()) as { detail?: string };
        setPreviewNote(
          body.detail ?? "No speech engine on this machine yet.",
        );
        return;
      }
      const url = URL.createObjectURL(await response.blob());
      const audio = new Audio(url);
      audio.onended = () => URL.revokeObjectURL(url);
      await audio.play();
    } catch {
      setPreviewNote("Preview unavailable right now.");
    }
  };

  return (
    <Card title="Personality & voice">
      <p className="mb-3 text-sm text-ink-soft">What is Meemoo here to be?</p>
      <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-5">
        {presets.map((preset) => (
          <button
            key={preset.role}
            type="button"
            onClick={() => {
              onRole(preset.role);
              onSub(preset.default_sub || null);
            }}
            className={`rounded-2xl border p-4 text-center transition ${
              role === preset.role
                ? "border-sage bg-sage-soft"
                : "border-line bg-card hover:border-sage/50"
            }`}
          >
            <span className="block text-3xl" aria-hidden="true">
              {ROLE_EMOJI[preset.role] ?? "🎈"}
            </span>
            <span className="mt-2 block text-sm font-semibold">{preset.title}</span>
          </button>
        ))}
      </div>

      {active !== null && active.sub_presets.length > 0 && (
        <div className="mt-4">
          <p className="mb-2 text-sm text-ink-soft">…and what kind?</p>
          <div className="flex flex-wrap gap-2">
            {active.sub_presets.map((subPreset) => (
              <button
                key={subPreset.key}
                type="button"
                onClick={() => onSub(subPreset.key)}
                className={`rounded-full px-4 py-2 text-sm font-medium transition ${
                  sub === subPreset.key
                    ? "bg-sage text-white"
                    : "bg-cream text-ink-soft hover:bg-sage-soft"
                }`}
              >
                {subPreset.title}
              </button>
            ))}
          </div>
        </div>
      )}

      <div className="mt-5">
        <p className="mb-2 text-sm text-ink-soft">Whose voice?</p>
        <div className="grid gap-3 sm:grid-cols-3">
          {voices.map((voice) => (
            <div
              key={voice.key}
              className={`rounded-2xl border p-4 transition ${
                voiceKey === voice.key
                  ? "border-sage bg-sage-soft"
                  : "border-line bg-card"
              }`}
            >
              <button
                type="button"
                onClick={() => onVoice(voice.key)}
                className="block w-full text-left"
              >
                <span className="font-semibold">{voice.label}</span>
                <span className="mt-1 block text-sm text-ink-soft">
                  {voice.description}
                </span>
              </button>
              <button
                type="button"
                onClick={() => void preview(voice.key)}
                className="mt-3 rounded-full bg-sky-soft px-3 py-1 text-sm text-ink-soft transition hover:bg-sky/40"
              >
                ▶ Hear it
              </button>
            </div>
          ))}
        </div>
        {previewNote && (
          <p className="mt-2 text-sm text-ink-faint">{previewNote}</p>
        )}
      </div>

      {active !== null && (
        <details className="mt-5">
          <summary className="cursor-pointer text-sm text-ink-faint">
            Open the raw context (for power users)
          </summary>
          <div className="mt-2 space-y-2 rounded-2xl bg-cream p-4 text-sm text-ink-soft">
            <p className="whitespace-pre-wrap">{active.context}</p>
            {sub !== null && (
              <p className="whitespace-pre-wrap border-t border-line pt-2">
                {active.sub_presets.find((s) => s.key === sub)?.context ?? ""}
              </p>
            )}
            <p className="text-xs text-ink-faint">
              preset v{active.version} <Chip tone="plain">read-only here; edit presets in brain/presets/</Chip>
            </p>
          </div>
        </details>
      )}
    </Card>
  );
}
