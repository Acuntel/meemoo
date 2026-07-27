/** Conversational config: "prompting your robot" as a product experience.
 * Owner writes plain language → extract → review/edit → save. The raw text
 * is always stored verbatim as custom context. */

import { useState } from "react";
import { apiPost } from "../../lib/api";
import type { StudioConfig } from "../../lib/types";
import { Button, Card, Chip } from "../../components/ui";

const PLACEHOLDER =
  "You're checking on my mom Ruth. She takes her heart medication at 8am " +
  "and 6pm, loves gardening and her grandkids, and gets lonely in the " +
  "evenings. If something seems wrong, call me first.";

type ExtractOut = { config: StudioConfig; source: string; raw_text: string };

export default function StudioChat({
  onSaved,
  saveExtras,
}: {
  onSaved: (personName: string) => void;
  saveExtras: () => { role: string; sub_preset: string | null; voice: string };
}) {
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [review, setReview] = useState<ExtractOut | null>(null);
  const [note, setNote] = useState<string | null>(null);

  const extract = async () => {
    if (!text.trim()) return;
    setBusy(true);
    setNote(null);
    try {
      const result = await apiPost<ExtractOut>("/api/v1/studio/extract", {
        text: text.trim(),
        device_id: 1,
      });
      setReview(result);
    } catch {
      setNote("Couldn't reach Meemoo. Is the app running?");
    } finally {
      setBusy(false);
    }
  };

  const update = (patch: Partial<StudioConfig>) => {
    setReview((prev) =>
      prev === null ? prev : { ...prev, config: { ...prev.config, ...patch } },
    );
  };

  const save = async () => {
    if (review === null) return;
    setBusy(true);
    try {
      await apiPost("/api/v1/studio/apply", {
        device_id: 1,
        config: review.config,
        raw_text: review.raw_text,
        ...saveExtras(),
      });
      onSaved(review.config.person_name);
    } catch {
      setNote("Saving failed. Try again in a moment.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card title="Tell Meemoo who it's for">
      <div className="space-y-3">
        <div className="flex justify-start">
          <p className="max-w-[90%] rounded-2xl bg-sage-soft px-4 py-3 text-sm text-sage-deep">
            Hi! Tell me about the person I&apos;ll be looking after: their
            name, their routine, what they love, and who to call if I get
            worried. Plain words are perfect.
          </p>
        </div>
        {review === null ? (
          <>
            <textarea
              value={text}
              onChange={(event) => setText(event.target.value)}
              placeholder={PLACEHOLDER}
              rows={5}
              className="w-full rounded-2xl border border-line bg-card p-4 text-sm outline-none focus:border-sage"
            />
            <div className="flex items-center gap-3">
              <Button onClick={() => void extract()} disabled={busy || !text.trim()}>
                {busy ? "Reading…" : "That's them"}
              </Button>
              {note && <span className="text-sm text-rose">{note}</span>}
            </div>
          </>
        ) : (
          <div className="rounded-2xl border border-line bg-cream p-4">
            <p className="mb-3 text-sm text-ink-faint">
              Here&apos;s what I understood. Fix anything before saving.
              {review.source === "deterministic" &&
                " (No AI key yet, so I kept it simple. Your full note is saved word-for-word either way.)"}
            </p>
            <div className="grid gap-3 sm:grid-cols-2">
              <label className="text-sm">
                <span className="mb-1 block text-ink-soft">Their name</span>
                <input
                  value={review.config.person_name}
                  onChange={(event) => update({ person_name: event.target.value })}
                  className="w-full rounded-xl border border-line bg-card px-3 py-2 outline-none focus:border-sage"
                />
              </label>
              <label className="text-sm">
                <span className="mb-1 block text-ink-soft">They&apos;re your…</span>
                <input
                  value={review.config.relationship ?? ""}
                  placeholder="mom, neighbor, patient…"
                  onChange={(event) =>
                    update({ relationship: event.target.value || null })
                  }
                  className="w-full rounded-xl border border-line bg-card px-3 py-2 outline-none focus:border-sage"
                />
              </label>
            </div>
            <div className="mt-3">
              <span className="mb-1 block text-sm text-ink-soft">Reminders</span>
              <div className="flex flex-wrap gap-2">
                {review.config.reminders.map((reminder, index) => (
                  <Chip
                    key={`${reminder.time}-${index}`}
                    tone="peach"
                    onRemove={() =>
                      update({
                        reminders: review.config.reminders.filter(
                          (_, i) => i !== index,
                        ),
                      })
                    }
                  >
                    {reminder.label} at {reminder.time}
                  </Chip>
                ))}
                {review.config.reminders.length === 0 && (
                  <span className="text-sm text-ink-faint">none spotted</span>
                )}
              </div>
            </div>
            <div className="mt-3">
              <span className="mb-1 block text-sm text-ink-soft">
                Things they love
              </span>
              <div className="flex flex-wrap gap-2">
                {review.config.interests.map((interest, index) => (
                  <Chip
                    key={interest}
                    onRemove={() =>
                      update({
                        interests: review.config.interests.filter(
                          (_, i) => i !== index,
                        ),
                      })
                    }
                  >
                    {interest}
                  </Chip>
                ))}
                {review.config.interests.length === 0 && (
                  <span className="text-sm text-ink-faint">none spotted</span>
                )}
              </div>
            </div>
            {review.config.escalation_note && (
              <p className="mt-3 text-sm text-ink-soft">
                <span className="font-semibold">If something seems wrong:</span>{" "}
                {review.config.escalation_note}
              </p>
            )}
            <div className="mt-4 flex items-center gap-3">
              <Button onClick={() => void save()} disabled={busy}>
                {busy ? "Saving…" : `Save, so Meemoo knows ${review.config.person_name}`}
              </Button>
              <Button kind="quiet" onClick={() => setReview(null)}>
                Start over
              </Button>
              {note && <span className="text-sm text-rose">{note}</span>}
            </div>
          </div>
        )}
      </div>
    </Card>
  );
}
