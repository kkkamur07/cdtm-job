import { API_BASE_URL, API_PREFIX } from "./config";
import type { components, operations } from "./schema";

/**
 * Image uploads.
 *
 * The storage buckets are private, so the browser never talks to storage. It
 * posts the file to the API, which stores it and returns a URL that is served
 * back through the API (`GET /api/v1/media/{bucket}/{key}`, public and
 * cache-immutable). That URL is what goes into `jobs.image_url` and
 * `housing_listings.photo_urls`.
 *
 * XMLHttpRequest rather than fetch, for one reason: fetch cannot report upload
 * progress, and a five megabyte photo on a phone connection needs a bar.
 */

export type MediaKind =
    operations["upload_media_api_v1_media__kind__post"]["parameters"]["path"]["kind"];

export type MediaUpload = components["schemas"]["MediaUploadPublic"];

export const MAX_UPLOAD_BYTES = 5 * 1024 * 1024;
export const ACCEPTED_IMAGE_TYPES = ["image/jpeg", "image/png", "image/webp"];

/** Absolute URL for whatever the API handed back, path or full URL. */
export function mediaUrl(url: string): string {
    return url.startsWith("/") ? `${API_BASE_URL}${url}` : url;
}

export function checkImage(file: File): string | null {
    if (!ACCEPTED_IMAGE_TYPES.includes(file.type)) return "Use a JPEG, PNG or WebP image.";
    if (file.size > MAX_UPLOAD_BYTES) return "That image is over 5 MB. Try a smaller one.";
    return null;
}

export function uploadMedia(
    kind: MediaKind,
    file: File,
    token: string | null,
    onProgress?: (percent: number) => void,
): Promise<MediaUpload> {
    return new Promise((resolve, reject) => {
        const form = new FormData();
        form.append("file", file);

        const request = new XMLHttpRequest();
        request.open("POST", `${API_BASE_URL}${API_PREFIX}/media/${kind}`);
        if (token) request.setRequestHeader("Authorization", `Bearer ${token}`);

        request.upload.onprogress = (event) => {
            if (event.lengthComputable && onProgress) {
                onProgress(Math.round((event.loaded / event.total) * 100));
            }
        };

        request.onerror = () => reject(new Error("The upload could not reach the API."));
        request.onload = () => {
            if (request.status >= 200 && request.status < 300) {
                try {
                    resolve(JSON.parse(request.responseText) as MediaUpload);
                } catch {
                    reject(new Error("The API returned something unexpected."));
                }
                return;
            }
            let message = `Upload failed (${request.status}).`;
            try {
                const body = JSON.parse(request.responseText) as {
                    error?: { message?: string };
                    detail?: string;
                };
                message = body.error?.message ?? body.detail ?? message;
            } catch {
                // Keep the status-code message.
            }
            reject(new Error(message));
        };

        request.send(form);
    });
}
