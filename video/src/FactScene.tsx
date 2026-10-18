import { Highlight } from "@remotion/rough-notation";
import type React from "react";
import { Easing, Interactive, Sequence, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { Caption } from "./Caption";
import { type Box, ScanView } from "./ScanView";
import { colors, fonts } from "./theme";

type FactSceneProps = {
  readonly headword: string;
  readonly edition: string;
  readonly scanLabel: string;
  readonly scan: string;
  readonly pageWidth: number;
  readonly pageHeight: number;
  readonly block: Box;
  readonly marks: readonly Box[];
  readonly quoteBefore: string;
  readonly quoteMark: string;
  readonly quoteAfter: string;
  readonly nowText: string;
  readonly citation: string;
  // Seconds from the scene start when the second caption and the Wikipedia card appear.
  readonly nowAt: number;
  readonly captionThen: string;
  readonly captionNow: string;
};

const fade = (frame: number, from: number, to: number) =>
  interpolate(frame, [from, to], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });

const FactSceneInner: React.FC<FactSceneProps> = ({
  headword,
  edition,
  scanLabel,
  scan,
  pageWidth,
  pageHeight,
  block,
  marks,
  quoteBefore,
  quoteMark,
  quoteAfter,
  nowText,
  citation,
  nowAt,
  captionThen,
  captionNow,
}) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();

  return (
    <>
      <ScanView
        scan={scan}
        pageWidth={pageWidth}
        pageHeight={pageHeight}
        width={820}
        height={750}
        block={block}
        marks={marks}
        zoomFrom={1.5}
        zoomTo={4}
        markFrom={5}
        style={{ position: "absolute", left: 100, top: 50 }}
      />
      <div
        style={{
          position: "absolute",
          left: 100,
          top: 812,
          width: 820,
          fontFamily: fonts.sans,
          fontSize: 22,
          color: colors.muted,
        }}
      >
        {scanLabel}
      </div>
      <div
        style={{
          position: "absolute",
          left: 1000,
          top: 60,
          width: 820,
          display: "flex",
          flexDirection: "column",
          gap: 28,
        }}
      >
        <div style={{ opacity: fade(frame, 0, 0.6 * fps) }}>
          <div style={{ fontFamily: fonts.sans, fontSize: 26, fontWeight: 600, color: colors.britannica, letterSpacing: 2 }}>
            {edition.toUpperCase()}
          </div>
          <div style={{ fontFamily: fonts.serif, fontSize: 92, fontWeight: 600, color: colors.ink, lineHeight: 1.05 }}>
            {headword}
          </div>
        </div>
        <Interactive.Div
          name="Britannica quote"
          style={{
            padding: "22px 30px",
            borderLeft: `8px solid ${colors.britannica}`,
            backgroundColor: colors.britannicaBg,
            fontFamily: fonts.serif,
            fontSize: 40,
            lineHeight: 1.35,
            color: colors.ink,
            opacity: interpolate(frame, [3 * fps, 4 * fps], [0, 1], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            }),
          }}
        >
          “{quoteBefore}
          <Highlight
            color={colors.highlight}
            progress={interpolate(frame, [5 * fps, 6.5 * fps], [0, 1], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            })}
          >
            {quoteMark}
          </Highlight>
          {quoteAfter}”
        </Interactive.Div>
        <Interactive.Div
          name="Wikipedia card"
          style={{
            padding: "22px 30px",
            borderLeft: `8px solid ${colors.wikipedia}`,
            backgroundColor: colors.wikipediaBg,
            fontFamily: fonts.sans,
            fontSize: 34,
            lineHeight: 1.35,
            color: colors.ink,
            opacity: interpolate(frame, [nowAt * fps, (nowAt + 0.8) * fps], [0, 1], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            }),
            translate: interpolate(frame, [nowAt * fps, (nowAt + 0.8) * fps], ["0px 40px", "0px 0px"], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
              easing: Easing.bezier(0.16, 1, 0.3, 1),
            }),
          }}
        >
          <div style={{ fontSize: 24, fontWeight: 700, color: colors.wikipedia, letterSpacing: 2, marginBottom: 8 }}>
            TODAY
          </div>
          {nowText}
          <div style={{ fontSize: 22, color: colors.muted, marginTop: 12 }}>{citation}</div>
        </Interactive.Div>
      </div>
      <Sequence name="Caption: then" durationInFrames={nowAt * fps} layout="none">
        <Caption name="Voice-over">{captionThen}</Caption>
      </Sequence>
      <Sequence name="Caption: now" from={nowAt * fps} durationInFrames={durationInFrames - nowAt * fps} layout="none">
        <Caption name="Voice-over">{captionNow}</Caption>
      </Sequence>
    </>
  );
};

export const FactScene = Interactive.create({
  Component: FactSceneInner,
  layout: "absolute-fill",
  schema: {
    ...Interactive.backgroundSchema,
    headword: { type: "string", default: "", description: "Headword" },
    nowText: { type: "string", default: "", description: "Wikipedia text" },
    captionThen: { type: "string", default: "", description: "Voice-over, then" },
    captionNow: { type: "string", default: "", description: "Voice-over, now" },
  },
});
