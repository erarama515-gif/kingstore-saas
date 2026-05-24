"use client";

import * as React from "react";
import { animate, useMotionValue, useTransform, motion } from "framer-motion";

/**
 * Count-up animated number. Pass a numeric value; it tweens smoothly from the
 * previous render's value to the new one.
 *
 * Default duration 0.9s, eased "out" — feels responsive but not snappy.
 */
export function AnimatedNumber({
  value,
  duration = 0.9,
  formatter,
}: {
  value: number;
  duration?: number;
  formatter?: (n: number) => string;
}) {
  const mv = useMotionValue(0);
  const display = useTransform(mv, (latest) =>
    formatter ? formatter(latest) : latest.toFixed(0),
  );

  React.useEffect(() => {
    const controls = animate(mv, value, { duration, ease: "easeOut" });
    return controls.stop;
  }, [value, duration, mv]);

  return <motion.span className="tabular">{display}</motion.span>;
}
