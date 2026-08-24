"use client";

import { useId, useMemo } from "react";

import type { PathFlow } from "@/api/types";
import { STAGE_LABELS, layoutFlow, type LaidOutNode } from "./layout";

/**
 * The flow, as a Sankey.
 *
 * Hand-rolled rather than pulled from a charting library: three or four stages
 * and a few dozen ribbons is one pass of proportional stacking, and a library
 * would add far more JavaScript than the diagram is worth. It is loaded with
 * next/dynamic so the bytes only arrive on the pages that draw it.
 *
 * Two readings of the same data, because the two pages ask different things
 * of it:
 *
 *   Paths   the whole community: filled ribbons, width is the count, and
 *           picking a group lists the members in it.
 *   Ask     the handful of people one question found: one thin strand per
 *           person, which is the same statement drawn at a size where the
 *           individual is still visible.
 *
 * What a strand cannot do is say whose it is. The API reports how many members
 * took a route, not which ones, so nothing here claims a strand belongs to a
 * particular person: selecting a person is what the list underneath is for.
 */

type Band = { stage: string; group: string };

/** Above this many members a strand is thinner than a hairline, so ribbons win. */
const STRAND_LIMIT = 60;

export default function PathsChart({
    flow,
    selected = null,
    onSelect,
    perPerson = false,
}: {
    flow: PathFlow;
    selected?: Band | null;
    onSelect?: (band: Band | null) => void;
    /** Draw one strand per member rather than one ribbon per route. */
    perPerson?: boolean;
}) {
    const asStrands = perPerson && flow.members_counted <= STRAND_LIMIT;
    const layout = useMemo(() => layoutFlow(flow, 880, perPerson ? 380 : 470), [flow, perPerson]);
    const strands = useMemo(() => (asStrands ? layout.strands() : []), [asStrands, layout]);
    const titleId = useId();

    if (!layout.nodes.length) {
        return (
            <p className="px-4 py-10 text-center text-[13.5px] text-muted">
                No paths have been worked out for these members yet.
            </p>
        );
    }

    const isHot = (stage: string, group: string) =>
        selected?.stage === stage && selected.group === group;

    /** A ribbon dims unless it touches the group that is selected. */
    const litRibbon = (link: { sourceStage: string; sourceGroup: string; targetStage: string; targetGroup: string }) =>
        !selected ||
        isHot(link.sourceStage, link.sourceGroup) ||
        isHot(link.targetStage, link.targetGroup);

    return (
        // No `role="img"`: when `onSelect` is given, every node inside is a
        // button, and an image is a leaf that a screen reader will not let you
        // into. The <title> still names the diagram through `aria-labelledby`,
        // which is what the role was there for.
        <svg
            viewBox={`0 0 ${layout.width} ${layout.height + 34}`}
            width="100%"
            aria-labelledby={titleId}
        >
            <title id={titleId}>
                {perPerson
                    ? `How the ${flow.members_counted} members in this answer got where they are, from field of study to what they are open to`
                    : "What members studied, the first thing they did after CDTM, and where they are now"}
            </title>

            <g transform="translate(0, 30)">
                {layout.stages.map((stage) => {
                    const first = layout.nodes.find((node) => node.stage === stage);
                    if (!first) return null;
                    return (
                        <text
                            key={stage}
                            x={first.x}
                            y={-12}
                            fontSize="11"
                            letterSpacing="1"
                            fill="var(--color-muted)"
                        >
                            {(STAGE_LABELS[stage] ?? stage).toUpperCase()}
                        </text>
                    );
                })}

                {asStrands
                    ? strands.map((strand) => (
                          <path
                              key={strand.key}
                              d={strand.path}
                              fill="none"
                              stroke="var(--color-blue)"
                              strokeOpacity={0.42}
                              strokeWidth={1}
                              strokeLinecap="round"
                          >
                              <title>{strand.label}</title>
                          </path>
                      ))
                    : layout.links.map((link) => {
                          const lit = litRibbon(link);
                          const hot = Boolean(selected) && lit;
                          return (
                              <path
                                  // Keyed by the two ends it joins, not by its
                                  // position: the class filter reorders these,
                                  // and an index key would repaint the wrong
                                  // ribbon rather than move it.
                                  key={`${link.sourceStage}:${link.sourceGroup}->${link.targetStage}:${link.targetGroup}`}
                                  d={link.path}
                                  fill={hot ? "var(--color-green)" : "var(--color-blue)"}
                                  fillOpacity={hot ? 0.55 : lit ? 0.16 : 0.05}
                                  stroke="none"
                              >
                                  <title>
                                      {link.sourceGroup} to {link.targetGroup}: {link.count}{" "}
                                      {link.count === 1 ? "member" : "members"}
                                  </title>
                              </path>
                          );
                      })}

                {layout.nodes.map((node) => (
                    <Node
                        key={`${node.stage}-${node.group}`}
                        node={node}
                        hot={isHot(node.stage, node.group)}
                        interactive={Boolean(onSelect)}
                        intent={node.stage === "intent" || node.stage === "intents"}
                        onSelect={onSelect}
                    />
                ))}
            </g>
        </svg>
    );
}

/** Cut to fit the box, with an ellipsis so the cut is visible. */
function clip(text: string, max: number): string {
    return text.length > max ? `${text.slice(0, max - 1).trimEnd()}…` : text;
}

function Node({
    node,
    hot,
    interactive,
    intent,
    onSelect,
}: {
    node: LaidOutNode;
    hot: boolean;
    interactive: boolean;
    intent: boolean;
    onSelect?: (band: Band | null) => void;
}) {
    /**
     * Two label budgets, because the two node shapes leave different room. The
     * tall node centres the name over its own count and has the whole width;
     * the short one shares its line with the count at the right edge, so it
     * gets less. The full name is always in the <title> either way.
     */
    const stacked = node.height >= 40;
    const label = clip(node.group, stacked ? 22 : 17);
    const count = `${node.count} ${node.count === 1 ? "person" : "people"}`;
    const fill = hot || intent ? "var(--color-green-soft)" : "#fff";
    const stroke = hot ? "var(--color-green)" : intent ? "transparent" : "var(--color-line)";

    const body = (
        <>
            <rect
                x={node.x}
                y={node.y}
                width={node.width}
                height={node.height}
                rx={Math.min(14, node.height / 2)}
                fill={fill}
                stroke={stroke}
            />
            {stacked ? (
                <>
                    <text
                        x={node.x + node.width / 2}
                        y={node.y + node.height / 2 - 3}
                        textAnchor="middle"
                        fontSize="11.5"
                        fontWeight="600"
                        fill="var(--color-ink)"
                    >
                        {label}
                    </text>
                    <text
                        x={node.x + node.width / 2}
                        y={node.y + node.height / 2 + 12}
                        textAnchor="middle"
                        fontSize="10.5"
                        fill="var(--color-muted)"
                    >
                        {count}
                    </text>
                </>
            ) : (
                // A short node has no room for two lines, so the label takes
                // one and the count moves to the right edge rather than
                // disappearing with the box.
                <>
                    <text
                        x={node.x + 12}
                        y={node.y + node.height / 2}
                        dominantBaseline="central"
                        fontSize="11"
                        fontWeight="600"
                        fill="var(--color-ink)"
                    >
                        {label}
                    </text>
                    <text
                        x={node.x + node.width - 12}
                        y={node.y + node.height / 2}
                        textAnchor="end"
                        dominantBaseline="central"
                        fontSize="10.5"
                        fill="var(--color-muted)"
                    >
                        {node.count}
                    </text>
                </>
            )}
        </>
    );

    if (!interactive || !onSelect) {
        return (
            <g aria-hidden="true">
                {body}
                <title>{`${node.group}, ${count}`}</title>
            </g>
        );
    }

    return (
        <g
            role="button"
            tabIndex={0}
            // An SVG group gets no focus ring of its own, so one is drawn: the
            // dashed halo below, hidden until the group is keyboard-focused.
            // Without it the keyboard path through the diagram is invisible.
            className="cursor-pointer outline-none [&:focus-visible>.node-ring]:opacity-100"
            onClick={() => onSelect(hot ? null : { stage: node.stage, group: node.group })}
            onKeyDown={(event) => {
                if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    onSelect(hot ? null : { stage: node.stage, group: node.group });
                }
            }}
            aria-pressed={hot}
            aria-label={`${node.group}, ${count}`}
        >
            {body}
            <rect
                className="node-ring pointer-events-none opacity-0"
                x={node.x - 3}
                y={node.y - 3}
                width={node.width + 6}
                height={node.height + 6}
                rx={Math.min(16, node.height / 2 + 3)}
                fill="none"
                stroke="var(--color-blue)"
                strokeWidth={2}
                strokeDasharray="4 3"
            />
        </g>
    );
}
