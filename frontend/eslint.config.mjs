import nextCoreWebVitals from "eslint-config-next/core-web-vitals";
import nextTypescript from "eslint-config-next/typescript";

/**
 * Next 16 ships flat configs, so they are imported directly rather than
 * squeezed through FlatCompat.
 */
const config = [
    {
        // Generated from openapi/openapi.json; never hand-edited, never linted.
        ignores: [
            "src/api/schema.d.ts",
            ".next/**",
            "out/**",
            "public/**",
            "node_modules/**",
            "scripts/ingest.mjs",
        ],
    },
    ...nextCoreWebVitals,
    ...nextTypescript,
    {
        rules: {
            // Avatars come from public/ already sized by the ingest script and
            // company logos come from arbitrary hosts, so next/image would add
            // a proxy hop or a config entry per domain for no gain. Uploaded
            // media does use next/image.
            "@next/next/no-img-element": "off",
        },
    },
];

export default config;
