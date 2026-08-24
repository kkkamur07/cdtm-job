import type { PathFlow } from "@/api/types";

/**
 * Turns the flow the API returns into geometry.
 *
 * It is a Sankey without a Sankey library: three or four stages, a handful of
 * groups each, so the whole layout is one pass of proportional stacking. Node
 * height is share of its column, and a ribbon leaves its source at a running
 * offset so two ribbons never overlap inside one node.
 *
 * Ribbons are filled shapes, not thick strokes. A stroke of width N is centred
 * on its path, so where two of them cross the overlap doubles in weight and the
 * diagram turns to mud; a filled band between two edges reads as one thing
 * passing behind another, which is what the picture means.
 */

export const STAGE_LABELS: Record<string, string> = {
    study: "Field of study",
    study_group: "Field of study",
    first_step: "First career",
    first_step_group: "First career",
    current: "Current role",
    current_group: "Current role",
    intent: "Open to",
    intents: "Open to",
};

const PREFERRED_ORDER = [
    "study",
    "study_group",
    "first_step",
    "first_step_group",
    "current",
    "current_group",
    "intent",
    "intents",
];

export type LaidOutNode = {
    stage: string;
    group: string;
    count: number;
    x: number;
    y: number;
    width: number;
    height: number;
};

export type LaidOutLink = {
    /** A filled ribbon between the two node edges. */
    path: string;
    /** A single centre line, for the per-person reading. */
    centre: string;
    /** Vertical extent at the source edge, for splitting into strands. */
    span: { x1: number; y1: number; x2: number; y2: number; thickness: number };
    count: number;
    sourceStage: string;
    sourceGroup: string;
    targetStage: string;
    targetGroup: string;
    thickness: number;
};

export type FlowLayout = {
    stages: string[];
    nodes: LaidOutNode[];
    links: LaidOutLink[];
    width: number;
    height: number;
    /**
     * One thin line per member on each ribbon.
     *
     * The API reports how many members took a route, not which ones, so a
     * strand stands for "somebody on this route" and carries no identity. It is
     * only worth drawing for a small answer, where N strands and a ribbon of
     * width N are the same statement and the strands read better.
     */
    strands: () => { key: string; path: string; label: string }[];
};

const NODE_WIDTH = 156;
const GAP = 12;
const MIN_NODE_HEIGHT = 26;

export function layoutFlow(flow: PathFlow, width = 880, height = 460): FlowLayout {
    const nodes = flow.nodes ?? [];
    const links = flow.links ?? [];

    const stages = [...new Set(nodes.map((node) => node.stage))].sort((a, b) => {
        const ai = PREFERRED_ORDER.indexOf(a);
        const bi = PREFERRED_ORDER.indexOf(b);
        return (ai === -1 ? 99 : ai) - (bi === -1 ? 99 : bi);
    });

    const laidOut: LaidOutNode[] = [];
    const byKey = new Map<string, LaidOutNode>();

    stages.forEach((stage, columnIndex) => {
        const column = nodes
            .filter((node) => node.stage === stage)
            .sort((a, b) => b.count - a.count);
        const total = column.reduce((sum, node) => sum + node.count, 0) || 1;
        const gaps = GAP * Math.max(column.length - 1, 0);

        // Every group keeps a readable minimum, and the rest of the column is
        // shared out in proportion. Without the floor, a group of three people
        // next to a group of four hundred is a hairline with no room for a
        // label, which is exactly the group somebody is looking for.
        const floors = MIN_NODE_HEIGHT * column.length;
        const flexible = Math.max(height - gaps - floors, 0);

        const x =
            stages.length === 1 ? 0 : (columnIndex * (width - NODE_WIDTH)) / (stages.length - 1);

        let y = 0;
        for (const node of column) {
            const nodeHeight = MIN_NODE_HEIGHT + (node.count / total) * flexible;
            const entry: LaidOutNode = {
                stage,
                group: node.group,
                count: node.count,
                x,
                y,
                width: NODE_WIDTH,
                height: nodeHeight,
            };
            laidOut.push(entry);
            byKey.set(`${stage}::${node.group}`, entry);
            y += nodeHeight + GAP;
        }
    });

    // Running offsets, so several ribbons leaving one node stack instead of
    // all starting at its top edge.
    const outOffset = new Map<string, number>();
    const inOffset = new Map<string, number>();

    const laidOutLinks: LaidOutLink[] = [];
    // Largest first: a wide ribbon laid down before a narrow one keeps the
    // stacking order the same on both edges, which is what stops them crossing
    // inside a node.
    for (const link of [...links].sort((a, b) => b.count - a.count)) {
        const source = byKey.get(`${link.source_stage}::${link.source_group}`);
        const target = byKey.get(`${link.target_stage}::${link.target_group}`);
        if (!source || !target) continue;

        const sourceTotal = totalFor(links, link.source_stage, link.source_group, "source") || 1;
        const targetTotal = totalFor(links, link.target_stage, link.target_group, "target") || 1;
        const outThickness = Math.max((link.count / sourceTotal) * source.height, 1.5);
        const inThickness = Math.max((link.count / targetTotal) * target.height, 1.5);

        const sourceKey = `${link.source_stage}::${link.source_group}`;
        const targetKey = `${link.target_stage}::${link.target_group}`;
        const y0 = source.y + (outOffset.get(sourceKey) ?? 0);
        const y1 = target.y + (inOffset.get(targetKey) ?? 0);
        outOffset.set(sourceKey, (outOffset.get(sourceKey) ?? 0) + outThickness);
        inOffset.set(targetKey, (inOffset.get(targetKey) ?? 0) + inThickness);

        const x1 = source.x + source.width;
        const x2 = target.x;
        const mid = (x1 + x2) / 2;

        // Top edge left to right, down the target edge, bottom edge back.
        const path = [
            `M${x1},${y0}`,
            `C${mid},${y0} ${mid},${y1} ${x2},${y1}`,
            `L${x2},${y1 + inThickness}`,
            `C${mid},${y1 + inThickness} ${mid},${y0 + outThickness} ${x1},${y0 + outThickness}`,
            "Z",
        ].join(" ");

        const cy0 = y0 + outThickness / 2;
        const cy1 = y1 + inThickness / 2;

        laidOutLinks.push({
            path,
            centre: `M${x1},${cy0} C${mid},${cy0} ${mid},${cy1} ${x2},${cy1}`,
            span: { x1, y1: y0, x2, y2: y1, thickness: outThickness },
            count: link.count,
            sourceStage: link.source_stage,
            sourceGroup: link.source_group,
            targetStage: link.target_stage,
            targetGroup: link.target_group,
            thickness: outThickness,
        });
    }

    const strands = () => {
        const result: { key: string; path: string; label: string }[] = [];
        for (const link of laidOutLinks) {
            const { x1, y1, x2, y2, thickness } = link.span;
            const mid = (x1 + x2) / 2;
            const inThickness = thickness;
            for (let index = 0; index < link.count; index++) {
                // Evenly spaced inside the ribbon, never on its very edge.
                const t = (index + 0.5) / link.count;
                const sy = y1 + t * thickness;
                const ty = y2 + t * inThickness;
                result.push({
                    // The stages belong in the key: a group name is unique
                    // inside a stage, not across them ("Consulting" and
                    // "Other" are both a first career and a current role), so
                    // group-to-group alone collides between the two columns.
                    key: `${link.sourceStage}:${link.sourceGroup}>${link.targetStage}:${link.targetGroup}#${index}`,
                    path: `M${x1},${sy} C${mid},${sy} ${mid},${ty} ${x2},${ty}`,
                    label: `${link.sourceGroup} to ${link.targetGroup}`,
                });
            }
        }
        return result;
    };

    return { stages, nodes: laidOut, links: laidOutLinks, width, height, strands };
}

function totalFor(
    links: PathFlow["links"],
    stage: string,
    group: string,
    side: "source" | "target",
): number {
    return (links ?? [])
        .filter((link) =>
            side === "source"
                ? link.source_stage === stage && link.source_group === group
                : link.target_stage === stage && link.target_group === group,
        )
        .reduce((sum, link) => sum + link.count, 0);
}
