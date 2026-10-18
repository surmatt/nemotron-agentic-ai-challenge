import type React from "react";
import { Easing, Interactive, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { Caption } from "./Caption";
import { colors, fonts } from "./theme";

type Candidate = {
  readonly title: string;
  readonly logit: number;
};

type MissSceneProps = {
  readonly kicker: string;
  readonly title: string;
  readonly candidates: readonly Candidate[];
  readonly margin: number;
  readonly rule: number;
  readonly scaleMax: number;
  readonly source: string;
  readonly caption: string;
};

const AXIS = { left: 220, width: 1480, top: 700 };

const MissSceneInner: React.FC<MissSceneProps> = ({
  kicker,
  title,
  candidates,
  margin,
  rule,
  scaleMax,
  source,
  caption,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const x = (v: number) => AXIS.left + (v / scaleMax) * AXIS.width;
  const show = (at: number) =>
    interpolate(frame, [at * fps, (at + 0.5) * fps], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });

  return (
    <>
      <div style={{ position: "absolute", left: 120, top: 70 }}>
        <div style={{ fontFamily: fonts.sans, fontSize: 28, fontWeight: 700, color: colors.bad, letterSpacing: 3 }}>
          {kicker.toUpperCase()}
        </div>
        <div style={{ fontFamily: fonts.sans, fontSize: 64, fontWeight: 700, color: colors.ink }}>{title}</div>
      </div>
      <div style={{ position: "absolute", left: 120, top: 280, display: "flex", flexDirection: "column", gap: 14 }}>
        {candidates.map((c, i) => (
          <div
            key={c.title}
            style={{
              display: "flex",
              gap: 30,
              fontFamily: fonts.sans,
              fontSize: 40,
              color: i === 0 ? colors.ink : colors.muted,
              fontWeight: i === 0 ? 700 : 400,
              opacity: show(0.6 + i * 0.4),
            }}
          >
            <span style={{ width: 50 }}>{i + 1}.</span>
            <span style={{ width: 520 }}>{c.title}</span>
            <span>reranker {c.logit.toFixed(3)}</span>
          </div>
        ))}
      </div>
      <div style={{ position: "absolute", left: AXIS.left, top: AXIS.top, width: AXIS.width, height: 6, backgroundColor: "#cfc8bd" }} />
      <div
        style={{
          position: "absolute",
          left: x(rule) - 3,
          top: AXIS.top - 70,
          width: 6,
          height: 146,
          backgroundColor: colors.good,
          opacity: show(2),
        }}
      />
      <div
        style={{
          position: "absolute",
          left: x(rule) - 200,
          top: AXIS.top + 90,
          width: 400,
          textAlign: "center",
          fontFamily: fonts.sans,
          fontSize: 30,
          color: colors.good,
          opacity: show(2),
        }}
      >
        accept rule: margin ≥ {rule}
      </div>
      <div
        style={{
          position: "absolute",
          top: AXIS.top - 22,
          width: 50,
          height: 50,
          borderRadius: 25,
          backgroundColor: colors.bad,
          left:
            interpolate(frame, [3 * fps, 4.2 * fps], [x(rule), x(margin)], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
              easing: Easing.bezier(0.16, 1, 0.3, 1),
            }) - 25,
          opacity: show(3),
        }}
      />
      <div
        style={{
          position: "absolute",
          left: x(margin) - 40,
          top: AXIS.top - 100,
          fontFamily: fonts.sans,
          fontSize: 34,
          fontWeight: 700,
          color: colors.bad,
          opacity: show(4.2),
        }}
      >
        margin {margin}: rejected
      </div>
      <div style={{ position: "absolute", left: 120, top: 830, fontFamily: fonts.sans, fontSize: 22, color: colors.muted }}>
        {source}
      </div>
      <Caption name="Voice-over">{caption}</Caption>
    </>
  );
};

export const MissScene = Interactive.create({
  Component: MissSceneInner,
  layout: "absolute-fill",
  schema: {
    ...Interactive.backgroundSchema,
    title: { type: "string", default: "", description: "Title" },
    caption: { type: "string", default: "", description: "Voice-over" },
  },
});
