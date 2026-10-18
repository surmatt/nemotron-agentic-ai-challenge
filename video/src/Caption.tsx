import type React from "react";
import { Interactive } from "remotion";
import { fonts } from "./theme";

type CaptionProps = {
  readonly children: React.ReactNode;
  readonly style?: React.CSSProperties;
};

// The voice-over line from video/script.md, shown as a subtitle.
const CaptionInner: React.FC<CaptionProps> = ({ children, style }) => {
  return (
    <div
      style={{
        position: "absolute",
        left: 160,
        right: 160,
        bottom: 70,
        padding: "18px 32px",
        borderRadius: 14,
        backgroundColor: "rgba(20, 18, 16, 0.82)",
        color: "white",
        fontFamily: fonts.sans,
        fontSize: 36,
        lineHeight: 1.35,
        textAlign: "center",
        ...style,
      }}
    >
      {children}
    </div>
  );
};

export const Caption = Interactive.create({
  Component: CaptionInner,
  layout: "none",
  schema: {
    ...Interactive.childrenSchema,
    ...Interactive.textSchema,
  },
});
