import { animate, useReducedMotion } from "motion/react";
import { useEffect, useState } from "react";

/** Animate a number from 0 to `target` (float); jumps straight there with reduced motion. */
export function useAnimatedValue(target: number, duration = 1.4, delay = 0): number {
  const reduce = useReducedMotion();
  const [value, setValue] = useState(reduce ? target : 0);

  useEffect(() => {
    if (reduce) {
      setValue(target);
      return;
    }
    const controls = animate(0, target, {
      duration,
      delay,
      ease: [0.16, 1, 0.3, 1],
      onUpdate: setValue,
    });
    return () => controls.stop();
  }, [target, duration, delay, reduce]);

  return value;
}

/** Integer count-up for numbers shown as text. */
export function useCountUp(target: number, duration = 1.4, delay = 0): number {
  return Math.round(useAnimatedValue(target, duration, delay));
}
