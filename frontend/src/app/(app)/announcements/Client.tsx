"use client";

import { useState } from "react";

import { useCreateAnnouncement } from "@/api/hooks/community";
import Field from "@/components/Field";
import Panel from "@/components/Panel";
import { FormError } from "@/components/states";

/**
 * Admin only. The page decides whether to draw it from the Member the server
 * already read, and the API rejects the write regardless, so this holds no
 * check of its own.
 */
export default function AnnouncementComposer() {
    const create = useCreateAnnouncement();
    const [title, setTitle] = useState("");
    const [body, setBody] = useState("");
    const [pinned, setPinned] = useState(false);

    const submit = (event: React.FormEvent) => {
        event.preventDefault();
        create.mutate(
            { title: title.trim(), body: body.trim(), is_pinned: pinned },
            {
                onSuccess: () => {
                    setTitle("");
                    setBody("");
                    setPinned(false);
                },
            },
        );
    };

    return (
        <Panel title="Post an announcement">
            <form className="grid gap-3.5" onSubmit={submit}>
                <Field label="Title" required>
                    {(props) => (
                        <input
                            {...props}
                            className="input"
                            required
                            maxLength={200}
                            value={title}
                            onChange={(event) => setTitle(event.target.value)}
                        />
                    )}
                </Field>
                <Field label="Body" required>
                    {(props) => (
                        <textarea
                            {...props}
                            className="textarea"
                            required
                            value={body}
                            onChange={(event) => setBody(event.target.value)}
                        />
                    )}
                </Field>
                <label className="flex items-center gap-2 text-[13px]">
                    <input
                        type="checkbox"
                        checked={pinned}
                        onChange={(event) => setPinned(event.target.checked)}
                        className="accent-blue"
                    />
                    Pin to the top
                </label>

                <FormError error={create.error} />

                <div>
                    <button
                        type="submit"
                        className="btn btn-primary"
                        disabled={create.isPending || !title.trim() || !body.trim()}
                    >
                        {create.isPending ? "Posting…" : "Post announcement"}
                    </button>
                </div>
            </form>
        </Panel>
    );
}
