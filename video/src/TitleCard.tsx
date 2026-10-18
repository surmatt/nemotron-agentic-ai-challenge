import type React from "react";
import { Easing, Interactive, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { colors, fonts } from "./theme";

type TitleCardProps = {
  readonly kicker: string;
  readonly title: string;
  readonly note: string;
};

// Part titles and the outro.
const TitleCardInner: React.FC<TitleCardProps> = ({ kicker, title, note }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  return (
    <div
      style={{
        textAlign: "center",
        opacity: interpolate(frame, [0, 0.5 * fps], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }),
        translate: interpolate(frame, [0, 0.8 * fps], ["0px 30px", "0px 0px"], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
          easing: Easing.bezier(0.16, 1, 0.3, 1),
        }),
      }}
    >
      <div style={{ fontFamily: fonts.sans, fontSize: 32, fontWeight: 700, color: colors.britannica, letterSpacing: 4 }}>
        {kicker.toUpperCase()}
      </div>
      <div style={{ fontFamily: fonts.serif, fontSize: 110, fontWeight: 600, color: colors.ink, margin: "10px 0 24px" }}>
        {title}
      </div>
      <div style={{ fontFamily: fonts.sans, fontSize: 30, color: colors.muted, maxWidth: 1400 }}>{note}</div>
    </div>
  );
};

export const TitleCard = Interactive.create({
  Component: TitleCardInner,
  layout: "absolute-fill",
  schema: {
    ...Interactive.backgroundSchema,
    kicker: { type: "string", default: "", description: "Kicker" },
    title: { type: "string", default: "", description: "Title" },
    note: { type: "string", default: "", description: "Note" },
  },
});
