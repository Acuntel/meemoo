/** Managed-vs-self-serve (Art. VII §2): managed is the default face; bring-
 * your-own keys and model tiers live behind "Advanced". Keys are write-only —
 * the server returns a masked tail, never the key. */

import { useCallback, useEffect, useState } from "react";
import { apiDelete, apiGet, apiPost, apiPut } from "../../lib/api";
import type { ProviderInfo, TierConfig, UsageInfo } from "../../lib/types";
import { Button, Card, Chip, EmptyNote } from "../../components/ui";

type KeyRow = { provider: string; masked: string; created_at: string };

const TIER_BLURB: Record<string, string> = {
  reflex: "quick reactions",
  conversation: "everyday chat",
  reasoning: "the careful thinking",
};

export default function AdvancedPanel() {
  const [providers, setProviders] = useState<ProviderInfo[]>([]);
  const [keys, setKeys] = useState<KeyRow[]>([]);
  const [tiers, setTiers] = useState<TierConfig[]>([]);
  const [usage, setUsage] = useState<UsageInfo | null>(null);
  const [provider, setProvider] = useState("anthropic");
  const [keyDraft, setKeyDraft] = useState("");
  const [note, setNote] = useState<string | null>(null);

  const refresh = useCallback(() => {
    apiGet<ProviderInfo[]>("/api/v1/providers?device_id=1")
      .then(setProviders)
      .catch(() => setProviders([]));
    apiGet<KeyRow[]>("/api/v1/devices/1/keys")
      .then(setKeys)
      .catch(() => setKeys([]));
    apiGet<TierConfig[]>("/api/v1/devices/1/model-config")
      .then(setTiers)
      .catch(() => setTiers([]));
    apiGet<UsageInfo>("/api/v1/devices/1/usage")
      .then(setUsage)
      .catch(() => setUsage(null));
  }, []);

  useEffect(refresh, [refresh]);

  const saveKey = async () => {
    if (keyDraft.trim().length < 4) return;
    try {
      await apiPost(`/api/v1/devices/1/keys`, {
        provider,
        key: keyDraft.trim(),
      });
      setKeyDraft("");
      setNote(`Saved — ${provider} is ready.`);
      refresh();
    } catch {
      setNote("Couldn't save that key.");
    }
  };

  const removeKey = async (name: string) => {
    try {
      await apiDelete(`/api/v1/devices/1/keys/${name}`);
      refresh();
    } catch {
      setNote("Couldn't remove that key.");
    }
  };

  const updateTier = async (tier: TierConfig, model: string) => {
    try {
      await apiPut(`/api/v1/devices/1/model-config/${tier.tier}`, {
        provider: tier.provider,
        model,
        max_tokens: tier.max_tokens,
      });
      refresh();
    } catch {
      setNote("Couldn't update that tier.");
    }
  };

  return (
    <Card title="Plan & models">
      <div className="rounded-2xl bg-sage-soft p-4">
        <p className="font-semibold text-sage-deep">Managed by Meemoo</p>
        <p className="mt-1 text-sm text-ink-soft">
          The default: your subscription covers the models, the credits, and
          the helium — nothing to configure here.
          {usage && usage.estimated_monthly_usd > 0 && (
            <>
              {" "}
              Current pace ≈ <b>${usage.estimated_monthly_usd.toFixed(2)}/month</b>{" "}
              in model usage.
            </>
          )}
        </p>
      </div>

      <details className="mt-4">
        <summary className="cursor-pointer text-sm font-medium text-ink-soft">
          Advanced — I&apos;ll run my own models and keys
        </summary>
        <div className="mt-3 space-y-5">
          <div>
            <p className="mb-2 text-sm text-ink-soft">Providers</p>
            <div className="flex flex-wrap gap-2">
              {providers.map((info) => (
                <Chip key={info.name} tone={info.configured ? "sage" : "plain"}>
                  {info.name}
                  {info.configured ? ` ✓ (${info.source})` : " — not set up"}
                </Chip>
              ))}
            </div>
          </div>

          <form
            className="flex flex-wrap items-center gap-2"
            onSubmit={(event) => {
              event.preventDefault();
              void saveKey();
            }}
          >
            <select
              value={provider}
              onChange={(event) => setProvider(event.target.value)}
              aria-label="Provider"
              className="rounded-full border border-line bg-card px-3 py-2 text-sm outline-none"
            >
              {providers
                .filter((info) => info.name !== "ollama")
                .map((info) => (
                  <option key={info.name} value={info.name}>
                    {info.name}
                  </option>
                ))}
            </select>
            <input
              type="password"
              value={keyDraft}
              onChange={(event) => setKeyDraft(event.target.value)}
              placeholder="Paste an API key (stored encrypted)"
              className="min-w-0 flex-1 rounded-full border border-line bg-card px-4 py-2 text-sm outline-none focus:border-sage"
            />
            <Button type="submit" kind="soft" disabled={keyDraft.trim().length < 4}>
              Save key
            </Button>
          </form>
          {keys.length > 0 && (
            <ul className="space-y-1">
              {keys.map((row) => (
                <li key={row.provider} className="flex items-center gap-3 text-sm">
                  <span className="font-medium">{row.provider}</span>
                  <span className="font-mono text-ink-faint">{row.masked}</span>
                  <button
                    type="button"
                    onClick={() => void removeKey(row.provider)}
                    className="text-rose transition hover:underline"
                  >
                    remove
                  </button>
                </li>
              ))}
            </ul>
          )}

          <div>
            <p className="mb-2 text-sm text-ink-soft">
              Which model handles what
            </p>
            {tiers.length === 0 ? (
              <EmptyNote>Model routing unavailable.</EmptyNote>
            ) : (
              <ul className="space-y-2">
                {tiers.map((tier) => (
                  <li
                    key={tier.tier}
                    className="flex flex-wrap items-center gap-2 rounded-2xl bg-cream px-4 py-2 text-sm"
                  >
                    <span className="w-28 font-medium">
                      {tier.tier}
                      <span className="block text-xs font-normal text-ink-faint">
                        {TIER_BLURB[tier.tier] ?? ""}
                      </span>
                    </span>
                    <input
                      defaultValue={tier.model}
                      aria-label={`${tier.tier} model`}
                      onBlur={(event) => {
                        if (event.target.value !== tier.model) {
                          void updateTier(tier, event.target.value);
                        }
                      }}
                      className="min-w-0 flex-1 rounded-full border border-line bg-card px-3 py-1.5 font-mono text-xs outline-none focus:border-sage"
                    />
                    <span className="text-ink-faint">
                      {tier.price_per_mtok
                        ? `$${tier.price_per_mtok.input}/$${tier.price_per_mtok.output} per Mtok`
                        : "price unknown"}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </div>
          {note && <p className="text-sm text-ink-soft">{note}</p>}
        </div>
      </details>
    </Card>
  );
}
