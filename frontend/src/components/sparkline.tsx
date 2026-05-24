"use client";

import * as React from "react";
import { Area, AreaChart, ResponsiveContainer } from "recharts";

/**
 * Tiny inline sparkline. Renders within whatever height/width its parent
 * gives it. No axes, no tooltip — pure trend ribbon.
 *
 * Pass colors as raw HSL values (without the wrapping `hsl(...)`) so the
 * component can compose them into gradients.
 */
export function Sparkline({
  data,
  color = "var(--chart-1)",
  height = 32,
}: {
  data: { value: number }[];
  /** A Tailwind/CSS color expression. Defaults to chart-1. */
  color?: string;
  height?: number;
}) {
  if (!data || data.length === 0) {
    return <div style={{ height }} className="opacity-30" />;
  }
  const id = React.useId().replace(/:/g, "_");
  return (
    <div style={{ height, width: "100%" }} className="pointer-events-none">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 2, right: 0, bottom: 0, left: 0 }}>
          <defs>
            <linearGradient id={`sl-${id}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%"   stopColor={`hsl(${color})`} stopOpacity={0.5} />
              <stop offset="100%" stopColor={`hsl(${color})`} stopOpacity={0} />
            </linearGradient>
          </defs>
          <Area
            type="monotone"
            dataKey="value"
            stroke={`hsl(${color})`}
            strokeWidth={1.75}
            fill={`url(#sl-${id})`}
            isAnimationActive
            animationDuration={600}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
