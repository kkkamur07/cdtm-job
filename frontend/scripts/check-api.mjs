#!/usr/bin/env node
/**
 * Fails if src/api/schema.d.ts is stale with respect to openapi/openapi.json.
 *
 * The backend owns exporting openapi.json (a python command in the repo root);
 * this only checks that the committed TypeScript matches the committed JSON, so
 * it runs anywhere without a python toolchain.
 */
import { execFileSync } from "node:child_process";
import { mkdtempSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const root = dirname(dirname(fileURLToPath(import.meta.url)));
const committed = join(root, "src", "api", "schema.d.ts");
const tmp = mkdtempSync(join(tmpdir(), "cdtm-api-"));
const candidate = join(tmp, "schema.d.ts");

try {
    execFileSync(
        "npx",
        ["openapi-typescript", join(root, "openapi", "openapi.json"), "-o", candidate],
        { cwd: root, stdio: "inherit" },
    );
    execFileSync("npx", ["prettier", "--write", candidate], { cwd: root, stdio: "ignore" });

    if (readFileSync(candidate, "utf8") !== readFileSync(committed, "utf8")) {
        console.error(
            "\nsrc/api/schema.d.ts is out of date with openapi/openapi.json.\n" +
                "Run `npm run generate:api` and commit the result.\n",
        );
        process.exit(1);
    }
    console.log("src/api/schema.d.ts matches openapi/openapi.json.");
} finally {
    rmSync(tmp, { recursive: true, force: true });
}
