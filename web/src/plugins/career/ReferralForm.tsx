import { useState } from "react";
import { LoadError } from "@shell/LoadError";
import { href } from "@shell/router";
import { useLoad } from "@shell/useLoad";
import { fetchPeople } from "../networking/data";
import { PersonPicker } from "../networking/PersonPicker";
import { setReferral, type RoleDetail } from "./data";
import { useSave } from "@shell/useSave";

// Who referred you, picked from your phonebook. The search shows only once you ask for it
// (+ Add referrer, or Change); picking saves. People are added on the Networking page, never here.

export function ReferralForm({ role, onSaved }: { role: RoleDetail; onSaved: () => Promise<void> }) {
  const [picking, setPicking] = useState(false);
  const { busy, error, save } = useSave(onSaved);
  const saved = role.referral;

  return (
    <section aria-label="Referred by" className="panel flex flex-col gap-2">
      <h2 className="label">Referred by</h2>
      {picking ? (
        <Picker role={role} save={save} onCancel={() => setPicking(false)} />
      ) : saved ? (
        <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
          <a href={href("networking", saved.id)} className="text-accent hover:underline">
            {saved.name ?? saved.id}
          </a>
          <button type="button" onClick={() => setPicking(true)} className="link-button link-button-quiet">
            Change
          </button>
          <button type="button" disabled={busy} onClick={() => save(() => setReferral(role.id, null))} className="link-button link-button-quiet">
            Remove
          </button>
        </div>
      ) : (
        <button type="button" onClick={() => setPicking(true)} className="link-button self-start">
          + Add referrer
        </button>
      )}
      {busy && <p className="text-small text-muted">Saving…</p>}
      {error && <p className="text-small text-negative">{error}</p>}
    </section>
  );
}

/** The phonebook search, loaded only when it opens. */
function Picker({ role, save, onCancel }: { role: RoleDetail; save: (change: () => Promise<unknown>) => void; onCancel: () => void }) {
  const { load } = useLoad(fetchPeople, "people");
  return (
    <>
      {load.state === "loading" && <p className="text-small text-muted">Loading your phonebook</p>}
      {load.state === "error" && <LoadError what="your phonebook" error={load.error} />}
      {load.state === "ready" && (
        <PersonPicker
          people={load.data}
          value={null}
          onChange={(who) => who && "id" in who && save(() => setReferral(role.id, who.id))}
          label="Referred by"
          placeholder="Search your phonebook"
          canAdd={false}
          autoFocus
        />
      )}
      <button type="button" onClick={onCancel} className="link-button link-button-quiet self-start">
        Cancel
      </button>
    </>
  );
}
