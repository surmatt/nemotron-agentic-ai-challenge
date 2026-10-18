import type React from "react";
import { Easing, Interactive, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { Caption } from "./Caption";
import { colors, fonts } from "./theme";

type Bar = {
  readonly label: string;
  readonly value: number;
  readonly color: string;
};

type Stat = {
  readonly label: string;
  readonly before: string;
  readonly after: string;
};

type BarsSceneProps = {
  readonly kicker: string;
  readonly title: string;
  readonly bars: readonly Bar[];
  readonly max: number;
  readonly unit: string;
  readonly decimals: number;
  readonly stat: Stat | null;
  readonly footnote: string;
  readonly source: string;
  readonly caption: string;
};

const BAR_AREA = 980;

const BarsSceneInner: React.FC<BarsSceneProps> = ({
  kicker,
  title,
  bars,
  max,
  unit,
  decimals,
  stat,
  footnote,
  source,
  caption,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const grow = (i: number) =>
    interpolate(frame, [(0.8 + i * 0.5) * fps, (1.8 + i * 0.5) * fps], [0, 1], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
      easing: Easing.bezier(0.16, 1, 0.3, 1),
    });
  const statAt = 0.8 + bars.length * 0.5 + 0.5;

  return (
    <>
      <div style={{ position: "absolute", left: 120, top: 70 }}>
        <div style={{ fontFamily: fonts.sans, fontSize: 28, fontWeight: 700, color: colors.generated, letterSpacing: 3 }}>
          {kicker.toUpperCase()}
        </div>
        <div style={{ fontFamily: fonts.sans, fontSize: 72, fontWeight: 700, color: colors.ink }}>{title}</div>
      </div>
      <div style={{ position: "absolute", left: 120, top: 270, display: "flex", flexDirection: "column", gap: 48 }}>
        {bars.map((bar, i) => (
          <div key={bar.label} style={{ display: "flex", alignItems: "center", gap: 28 }}>
            <div style={{ width: 380, textAlign: "right", fontFamily: fonts.sans, fontSize: 36, color: colors.ink }}>
              {bar.label}
            </div>
            <div
              style={{
                width: (bar.value / max) * BAR_AREA * grow(i),
                height: 78,
                borderRadius: 8,
                backgroundColor: bar.color,
              }}
            />
            <div style={{ fontFamily: fonts.sans, fontSize: 42, fontWeight: 700, color: colors.ink, opacity: grow(i) }}>
              {(bar.value * grow(i)).toFixed(decimals)}
              {unit}
            </div>
          </div>
        ))}
      </div>
      {stat ? (
        <Interactive.Div
          name="Stat"
          style={{
            position: "absolute",
            right: 120,
            top: 90,
            padding: "20px 34px",
            borderRadius: 14,
            backgroundColor: "white",
            boxShadow: "0 12px 30px rgba(0,0,0,0.12)",
            fontFamily: fonts.sans,
            textAlign: "center",
            opacity: interpolate(frame, [statAt * fps, (statAt + 0.6) * fps], [0, 1], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            }),
          }}
        >
          <div style={{ fontSize: 26, color: colors.muted }}>{stat.label}</div>
          <div style={{ fontSize: 76, fontWeight: 700, color: colors.ink }}>
            {stat.before} <span style={{ color: colors.muted }}>→</span>{" "}
            <span style={{ color: colors.good }}>{stat.after}</span>
          </div>
        </Interactive.Div>
      ) : null}
      <div
        style={{
          position: "absolute",
          left: 120,
          right: 120,
          top: 760,
          fontFamily: fonts.sans,
          fontSize: 30,
          color: colors.ink,
          opacity: interpolate(frame, [(statAt + 0.5) * fps, (statAt + 1.1) * fps], [0, 1], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          }),
        }}
      >
        {footnote}
        <div style={{ fontSize: 22, color: colors.muted, marginTop: 6 }}>{source}</div>
      </div>
      <Caption name="Voice-over">{caption}</Caption>
    </>
  );
};

export const BarsScene = Interactive.create({
  Component: BarsSceneInner,
  layout: "absolute-fill",
  schema: {
    ...Interactive.backgroundSchema,
    title: { type: "string", default: "", description: "Title" },
    footnote: { type: "string", default: "", description: "Footnote" },
    caption: { type: "string", default: "", description: "Voice-over" },
  },
});
