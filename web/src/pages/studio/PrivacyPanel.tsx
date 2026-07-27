/** Privacy panel (Art. V + Amendment A2): transcript toggle (default ON),
 * one-touch and custom-duration privacy pause, the per-recipient permission
 * matrix (grant the nurse, deny the son: the resident's choice), and the
 * consent record view. Copy never promises deletion we do not do. */

import { useCallback, useEffect, useState } from "react";
import { apiDelete, apiGet, apiPatch, apiPost, apiPut } from "../../lib/api";
import type {
  ConsentRecord,
  Contact,
  Device,
  PermissionMatrix,
} from "../../lib/types";
import { Button, Card, Chip, EmptyNote, Toggle } from "../../components/ui";

const SCOPES = [
  { key: "checkins", label: "Check-in summaries" },
  { key: "alerts", label: "Alerts" },
  { key: "transcripts", label: "Conversation transcripts" },
  { key: "clips", label: "Event clips" },
] as const;

const DEFAULT_GRANTS: Record<string, boolean> = {
  checkins: true,
  alerts: true,
  transcripts: false,
  clips: false,
};

export default function PrivacyPanel({ contacts }: { contacts: Contact[] }) {
  const [device, setDevice] = useState<Device | null>(null);
  const [pausedUntil, setPausedUntil] = useState<string | null>(null);
  const [customMinutes, setCustomMinutes] = useState("");
  const [matrix, setMatrix] = useState<PermissionMatrix>({});
  const [consent, setConsent] = useState<ConsentRecord[]>([]);

  const refresh = useCallback(() => {
    apiGet<Device>("/api/v1/devices/1")
      .then(setDevice)
      .catch(() => setDevice(null));
    apiGet<{ until?: string }>("/api/v1/devices/1/settings/privacy.pause")
      .then((value) => {
        const until = value.until ?? "";
        setPausedUntil(until && until > new Date().toISOString() ? until : null);
      })
      .catch(() => setPausedUntil(null));
    apiGet<PermissionMatrix>("/api/v1/devices/1/settings/privacy.permissions")
      .then(setMatrix)
      .catch(() => setMatrix({}));
    apiGet<ConsentRecord[]>("/api/v1/devices/1/consent")
      .then(setConsent)
      .catch(() => setConsent([]));
  }, []);

  useEffect(refresh, [refresh]);

  const setTranscripts = async (on: boolean) => {
    const updated = await apiPatch<Device>("/api/v1/devices/1", {
      store_transcripts: on,
    });
    setDevice(updated);
  };

  const pause = async (minutes: number) => {
    const result = await apiPost<{ paused_until: string }>(
      "/api/v1/devices/1/privacy/pause",
      { minutes },
    );
    setPausedUntil(result.paused_until);
  };

  const resume = async () => {
    await apiDelete("/api/v1/devices/1/privacy/pause");
    setPausedUntil(null);
  };

  const grantFor = (who: string, scope: string): boolean =>
    matrix[who]?.[scope] ?? DEFAULT_GRANTS[scope] ?? false;

  const toggleGrant = async (who: string, scope: string) => {
    const next: PermissionMatrix = {
      ...matrix,
      [who]: {
        ...Object.fromEntries(
          SCOPES.map((s) => [s.key, grantFor(who, s.key)]),
        ),
        [scope]: !grantFor(who, scope),
      },
    };
    setMatrix(next);
    await apiPut("/api/v1/devices/1/settings/privacy.permissions", {
      value: next,
    });
  };

  return (
    <Card title="Privacy" hint="the resident's choice, always">
      <p className="mb-2 text-sm text-ink-soft">
        What Meemoo hears and sees is kept on this base station in your home.
        You decide who may see any of it, below.
      </p>
      <Toggle
        checked={device?.store_transcripts ?? true}
        onChange={(on) => void setTranscripts(on)}
        label="Keep conversation transcripts"
        detail="On by default. Transcripts stay on this base station and only the people you allow can see them. Turn this off and new chats are not written down."
      />

      <div className="mt-4 rounded-2xl bg-cream p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="font-medium">Privacy pause</p>
            <p className="text-sm text-ink-faint">
              {pausedUntil
                ? `Meemoo is sitting out until ${new Date(pausedUntil).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })}.`
                : "One touch and Meemoo stops looking and listening for a while."}
            </p>
          </div>
          {pausedUntil ? (
            <Button kind="soft" onClick={() => void resume()}>
              Resume now
            </Button>
          ) : (
            <div className="flex flex-wrap items-center gap-2">
              <Button kind="soft" onClick={() => void pause(15)}>
                15 min
              </Button>
              <Button kind="soft" onClick={() => void pause(60)}>
                1 hour
              </Button>
              <form
                className="flex items-center gap-1"
                onSubmit={(event) => {
                  event.preventDefault();
                  const minutes = Number.parseInt(customMinutes, 10);
                  if (Number.isFinite(minutes) && minutes >= 1 && minutes <= 480) {
                    void pause(minutes);
                    setCustomMinutes("");
                  }
                }}
              >
                <input
                  type="number"
                  min={1}
                  max={480}
                  value={customMinutes}
                  onChange={(event) => setCustomMinutes(event.target.value)}
                  placeholder="minutes"
                  aria-label="Pause for a custom number of minutes"
                  className="w-24 rounded-full border border-line bg-card px-3 py-2 text-sm outline-none focus:border-sage"
                />
                <Button
                  type="submit"
                  kind="soft"
                  disabled={
                    !/^\d+$/.test(customMinutes.trim()) ||
                    Number.parseInt(customMinutes, 10) < 1 ||
                    Number.parseInt(customMinutes, 10) > 480
                  }
                >
                  Pause
                </Button>
              </form>
            </div>
          )}
        </div>
        <p className="mt-2 text-xs text-ink-faint">
          Up to 8 hours at a time. The mute switch on the base station cuts the
          microphone at the hardware whenever you want.
        </p>
      </div>

      <div className="mt-5">
        <p className="font-medium">Who may see what</p>
        <p className="text-sm text-ink-faint">
          Grant the nurse, deny the son. Each person you ring can see exactly
          what the resident allows.
        </p>
        {contacts.length === 0 ? (
          <EmptyNote>Add people under &ldquo;Who to ring&rdquo; first.</EmptyNote>
        ) : (
          <div className="mt-3 overflow-x-auto">
            <table className="w-full min-w-[28rem] text-sm">
              <thead>
                <tr className="text-left text-ink-faint">
                  <th className="py-2 pr-4 font-normal">Person</th>
                  {SCOPES.map((scope) => (
                    <th key={scope.key} className="px-2 py-2 text-center font-normal">
                      {scope.label}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {contacts.map((contact) => (
                  <tr key={contact.id} className="border-t border-line">
                    <td className="py-2 pr-4 font-medium">{contact.name}</td>
                    {SCOPES.map((scope) => {
                      const granted = grantFor(contact.name, scope.key);
                      return (
                        <td key={scope.key} className="px-2 py-2 text-center">
                          <button
                            type="button"
                            aria-label={`${scope.label} for ${contact.name}: ${granted ? "granted" : "denied"}`}
                            onClick={() => void toggleGrant(contact.name, scope.key)}
                            className={`h-7 w-7 rounded-full text-sm transition ${
                              granted
                                ? "bg-sage text-white"
                                : "bg-line text-ink-faint"
                            }`}
                          >
                            {granted ? "✓" : "–"}
                          </button>
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="mt-5">
        <p className="font-medium">Consent on file</p>
        {consent.length === 0 ? (
          <EmptyNote>
            No consent records yet. They&apos;re created during onboarding and
            listed here for review.
          </EmptyNote>
        ) : (
          <ul className="mt-2 space-y-2">
            {consent.map((record) => (
              <li key={record.id} className="flex flex-wrap items-center gap-2 text-sm">
                <Chip tone={record.granted ? "sage" : "rose"}>
                  {record.granted ? "granted" : "revoked"}
                </Chip>
                <span className="font-medium">{record.scope}</span>
                <span className="text-ink-faint">
                  by {record.consenting_party}
                  {record.is_surrogate &&
                    ` (${record.surrogate_relationship ?? "surrogate"})`}{" "}
                  · via {record.method}
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </Card>
  );
}
