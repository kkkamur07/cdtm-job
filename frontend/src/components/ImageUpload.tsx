"use client";

import Image from "next/image";
import { useCallback, useId, useRef, useState } from "react";

import { checkImage, mediaUrl, uploadMedia, type MediaKind } from "@/api/media";
import { useSession } from "@/auth/AuthProvider";

type Pending = { name: string; percent: number };

/**
 * Drag a file in, or pick one. The file goes to the API, and the URL it returns
 * is what the form submits.
 *
 * Uploading on selection rather than on submit is deliberate: a five megabyte
 * photo failing at the same moment as a validation error is two problems in one
 * message, and the person cannot tell which one to fix.
 */
export default function ImageUpload({
    kind,
    label,
    hint,
    urls,
    onChange,
    multiple = false,
    max = 8,
}: {
    kind: MediaKind;
    label: string;
    hint?: string;
    urls: string[];
    onChange: (urls: string[]) => void;
    multiple?: boolean;
    max?: number;
}) {
    const inputId = useId();
    const input = useRef<HTMLInputElement>(null);
    const { token } = useSession();
    const [pending, setPending] = useState<Pending[]>([]);
    const [error, setError] = useState<string | null>(null);
    const [over, setOver] = useState(false);

    const accept = useCallback(
        async (files: FileList | File[] | null) => {
            const list = [...(files ?? [])];
            if (!list.length) return;
            setError(null);

            const room = multiple ? Math.max(0, max - urls.length) : 1;
            const chosen = list.slice(0, room);
            if (chosen.length < list.length) {
                setError(`Only ${max} images per listing. The rest were skipped.`);
            }

            for (const file of chosen) {
                const problem = checkImage(file);
                if (problem) {
                    setError(problem);
                    continue;
                }

                setPending((current) => [...current, { name: file.name, percent: 0 }]);
                try {
                    const result = await uploadMedia(kind, file, token, (percent) =>
                        setPending((current) =>
                            current.map((item) =>
                                item.name === file.name ? { ...item, percent } : item,
                            ),
                        ),
                    );
                    // Functional update: several uploads finish independently.
                    onChange(multiple ? [...urls, result.url] : [result.url]);
                } catch (uploadError) {
                    setError(uploadError instanceof Error ? uploadError.message : "Upload failed.");
                } finally {
                    setPending((current) => current.filter((item) => item.name !== file.name));
                }
            }

            if (input.current) input.current.value = "";
        },
        [kind, max, multiple, onChange, token, urls],
    );

    return (
        <div>
            <span className="label" id={`${inputId}-label`}>
                {label}
            </span>

            <div
                onDragOver={(event) => {
                    event.preventDefault();
                    setOver(true);
                }}
                onDragLeave={() => setOver(false)}
                onDrop={(event) => {
                    event.preventDefault();
                    setOver(false);
                    void accept(event.dataTransfer.files);
                }}
                className={`flex flex-wrap items-center gap-2.5 rounded-2xl border border-dashed bg-cream p-3.5 transition-colors ${
                    over ? "border-blue bg-blue-soft" : "border-line"
                }`}
            >
                {urls.map((url) => (
                    <span key={url} className="relative">
                        <Image
                            src={mediaUrl(url)}
                            alt=""
                            width={96}
                            height={72}
                            unoptimized
                            className="h-[54px] w-[72px] rounded-[10px] border border-line object-cover"
                        />
                        <button
                            type="button"
                            onClick={() => onChange(urls.filter((item) => item !== url))}
                            className="absolute -top-1.5 -right-1.5 grid h-5 w-5 place-items-center rounded-full bg-ink text-[11px] text-white"
                        >
                            <span aria-hidden="true">×</span>
                            <span className="sr-only">Remove image</span>
                        </button>
                    </span>
                ))}

                {pending.map((item) => (
                    <span
                        key={item.name}
                        className="grid h-[54px] w-[72px] place-items-center rounded-[10px] border border-line bg-white"
                    >
                        <span className="sr-only">
                            Uploading {item.name}, {item.percent} percent
                        </span>
                        <span
                            aria-hidden="true"
                            className="h-1 w-12 overflow-hidden rounded-full bg-line"
                        >
                            <span
                                className="block h-full bg-blue transition-[width] duration-200"
                                style={{ width: `${Math.max(6, item.percent)}%` }}
                            />
                        </span>
                    </span>
                ))}

                <input
                    ref={input}
                    id={inputId}
                    type="file"
                    accept="image/jpeg,image/png,image/webp"
                    multiple={multiple}
                    className="sr-only"
                    onChange={(event) => void accept(event.target.files)}
                />
                <button
                    type="button"
                    className="btn btn-sm"
                    disabled={pending.length > 0}
                    onClick={() => input.current?.click()}
                >
                    {pending.length
                        ? "Uploading…"
                        : urls.length
                          ? multiple
                              ? "Add photos"
                              : "Replace image"
                          : multiple
                            ? "Add photos"
                            : "Add image"}
                </button>

                <span className="text-[12px] text-muted">
                    {hint ?? "JPEG, PNG or WebP, up to 5 MB. Drag one in if you prefer."}
                </span>
            </div>

            {error && (
                <p role="alert" className="mt-1.5 text-[12px] text-red-700">
                    {error}
                </p>
            )}
        </div>
    );
}
