import { Circle, Highlight } from "@remotion/rough-notation";
import type React from "react";
import {
  Interactive,
  Sequence,
  interpolate,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { Caption } from "./Caption";
import { type Box, ScanView } from "./ScanView";
import { colors, fonts } from "./theme";

type Row = {
  readonly label: string;
  readonly before: string;
  readonly mark: string;
  readonly after: string;
};

type BlooperSceneProps = {
  readonly scan: string;
  readonly pageWidth: number;
  readonly pageHeight: number;
  readonly block: Box;
  readonly marks: readonly Box[];
  readonly scanRow: Row;
  readonly parseRow: Row;
  readonly modelRow: Row;
  readonly source: string;
  readonly captionFirst: string;
  readonly captionSecond: string;
};

const BlooperSceneInner: React.FC<BlooperSceneProps> = ({
  scan,
  pageWidth,
  pageHeight,
  block,
  marks,
  scanRow,
  parseRow,
  modelRow,
  source,
  captionFirst,
  captionSecond,
}) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const half = Math.round(durationInFrames / 2);
  const rowStyle = (at: number, border: string): React.CSSProperties => ({
    display: "flex",
    alignItems: "baseline",
    gap: 28,
    padding: "14px 28px",
    borderLeft: `8px solid ${border}`,
    backgroundColor: "white",
    fontSize: 44,
    opacity: interpolate(frame, [at * fps, (at + 0.5) * fps], [0, 1], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
    }),
  });
  const label: React.CSSProperties = {
    width: 220,
    flexShrink: 0,
    fontFamily: fonts.sans,
    fontSize: 26,
    fontWeight: 700,
    color: colors.muted,
    letterSpacing: 1,
  };

  return (
    <>
      <div
        style={{
          position: "absolute",
          left: 100,
          top: 40,
          fontFamily: fonts.sans,
          fontSize: 30,
          fontWeight: 700,
          color: colors.bad,
          letterSpacing: 3,
        }}
      >
        BLOOPER · LAKE ERIE, 1771
      </div>
      <ScanView
        scan={scan}
        pageWidth={pageWidth}
        pageHeight={pageHeight}
        width={1720}
        height={250}
        block={block}
        marks={marks}
        zoomFrom={0}
        zoomTo={0}
        markFrom={0.8}
        style={{ position: "absolute", left: 100, top: 95 }}
      />
      <div
        style={{
          position: "absolute",
          left: 100,
          top: 380,
          width: 1720,
          display: "flex",
          flexDirection: "column",
          gap: 18,
        }}
      >
        <div style={rowStyle(0.5, colors.britannica)}>
          <span style={label}>{scanRow.label}</span>
          <span style={{ fontFamily: fonts.serif }}>
            {scanRow.before}
            <Highlight
              color={colors.highlight}
              progress={interpolate(frame, [1 * fps, 1.6 * fps], [0, 1], {
                extrapolateLeft: "clamp",
                extrapolateRight: "clamp",
              })}
            >
              {scanRow.mark}
            </Highlight>
            {scanRow.after}
          </span>
        </div>
        <div style={rowStyle(2, colors.generated)}>
          <span style={label}>{parseRow.label}</span>
          <span style={{ fontFamily: fonts.serif, color: colors.muted }}>
            {parseRow.before}
            <Highlight
              color="rgba(150,150,150,0.35)"
              progress={interpolate(frame, [2.5 * fps, 3.1 * fps], [0, 1], {
                extrapolateLeft: "clamp",
                extrapolateRight: "clamp",
              })}
            >
              {parseRow.mark}
            </Highlight>
            {parseRow.after}
          </span>
        </div>
        <div style={rowStyle(3.5, colors.bad)}>
          <span style={label}>{modelRow.label}</span>
          <span style={{ fontFamily: fonts.serif }}>
            {modelRow.before}
            <span style={{ display: "inline-block", margin: "0 8px 0 14px" }}>
              <Circle
                color={colors.bad}
                strokeWidth={4}
                progress={interpolate(frame, [4.2 * fps, 5 * fps], [0, 1], {
                  extrapolateLeft: "clamp",
                  extrapolateRight: "clamp",
                })}
              >
                <span style={{ padding: "0 10px" }}>{modelRow.mark}</span>
              </Circle>
            </span>
            {modelRow.after}
          </span>
        </div>
        <div
          style={{ fontFamily: fonts.sans, fontSize: 22, color: colors.muted }}
        >
          {source}
        </div>
      </div>
      <Sequence name="Caption: first" durationInFrames={half} layout="none">
        <Caption name="Voice-over">{captionFirst}</Caption>
      </Sequence>
      <Sequence
        name="Caption: second"
        from={half}
        durationInFrames={durationInFrames - half}
        layout="none"
      >
        <Caption name="Voice-over">{captionSecond}</Caption>
      </Sequence>
    </>
  );
};

export const BlooperScene = Interactive.create({
  Component: BlooperSceneInner,
  layout: "absolute-fill",
  schema: {
    ...Interactive.backgroundSchema,
    captionFirst: {
      type: "string",
      default: "",
      description: "Voice-over, first half",
    },
    captionSecond: {
      type: "string",
      default: "",
      description: "Voice-over, second half",
    },
  },
});
