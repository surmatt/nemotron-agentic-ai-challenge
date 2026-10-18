import type React from "react";
import { Easing, Interactive, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { Caption } from "./Caption";
import { colors, fonts } from "./theme";

type Card = {
  readonly label: string;
  readonly text: string;
  readonly note: string;
};

type BeforeAfterSceneProps = {
  readonly kicker: string;
  readonly title: string;
  readonly before: Card;
  readonly after: Card;
  readonly source: string;
  readonly caption: string;
};

const BeforeAfterSceneInner: React.FC<BeforeAfterSceneProps> = ({ kicker, title, before, after, source, caption }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const card = (at: number, color: string): React.CSSProperties => ({
    flex: 1,
    padding: "30px 36px",
    borderRadius: 16,
    borderTop: `10px solid ${color}`,
    backgroundColor: "white",
    boxShadow: "0 16px 40px rgba(0,0,0,0.12)",
    fontFamily: fonts.sans,
    opacity: interpolate(frame, [at * fps, (at + 0.6) * fps], [0, 1], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
    }),
    translate: interpolate(frame, [at * fps, (at + 0.6) * fps], ["0px 40px", "0px 0px"], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
      easing: Easing.bezier(0.16, 1, 0.3, 1),
    }),
  });

  return (
    <>
      <div style={{ position: "absolute", left: 120, top: 70 }}>
        <div style={{ fontFamily: fonts.sans, fontSize: 28, fontWeight: 700, color: colors.generated, letterSpacing: 3 }}>
          {kicker.toUpperCase()}
        </div>
        <div style={{ fontFamily: fonts.sans, fontSize: 72, fontWeight: 700, color: colors.ink }}>{title}</div>
      </div>
      <div style={{ position: "absolute", left: 120, right: 120, top: 280, display: "flex", gap: 60 }}>
        <div style={card(0.8, colors.bad)}>
          <div style={{ fontSize: 28, fontWeight: 700, color: colors.bad, letterSpacing: 2 }}>{before.label}</div>
          <div style={{ fontSize: 46, fontWeight: 600, margin: "18px 0", color: colors.ink }}>{before.text}</div>
          <div style={{ fontSize: 28, color: colors.muted }}>{before.note}</div>
        </div>
        <div style={card(3, colors.good)}>
          <div style={{ fontSize: 28, fontWeight: 700, color: colors.good, letterSpacing: 2 }}>{after.label}</div>
          <div style={{ fontSize: 46, fontWeight: 600, margin: "18px 0", color: colors.ink }}>{after.text}</div>
          <div style={{ fontSize: 28, color: colors.muted }}>{after.note}</div>
        </div>
      </div>
      <div style={{ position: "absolute", left: 120, top: 800, fontFamily: fonts.sans, fontSize: 22, color: colors.muted }}>
        {source}
      </div>
      <Caption name="Voice-over">{caption}</Caption>
    </>
  );
};

export const BeforeAfterScene = Interactive.create({
  Component: BeforeAfterSceneInner,
  layout: "absolute-fill",
  schema: {
    ...Interactive.backgroundSchema,
    title: { type: "string", default: "", description: "Title" },
    caption: { type: "string", default: "", description: "Voice-over" },
  },
});
