// SPDX-License-Identifier: MIT
// Cycles as defined in spec/metrics.md: strongly connected components with two or more units,
// each with one concrete example loop.

import { compareText, sortText } from "../text.js";

export interface Cycle {
  members: string[];
  size: number;
  example: string[];
}

/** `successors` has every unit as a key, with the units it depends on. */
export function findCycles(successors: Map<string, string[]>): Cycle[] {
  const sorted = new Map(sortText(successors.keys()).map((unit) => [unit, sortText(new Set(successors.get(unit)))]));
  const cycles: Cycle[] = [];
  for (const component of components(sorted)) {
    if (component.length < 2) {
      continue;
    }
    const members = sortText(component);
    cycles.push({ members, size: members.length, example: example(members[0]!, new Set(members), sorted) });
  }
  return cycles.sort((a, b) => b.size - a.size || compareText(a.members[0]!, b.members[0]!));
}

/** Tarjan's algorithm, written iteratively so deep dependency chains cannot overflow the stack. */
function components(successors: Map<string, string[]>): string[][] {
  const index = new Map<string, number>();
  const low = new Map<string, number>();
  const onStack = new Set<string>();
  const stack: string[] = [];
  const result: string[][] = [];
  let next = 0;

  for (const root of successors.keys()) {
    if (index.has(root)) {
      continue;
    }
    // Each frame is [unit, position of the next successor to visit].
    const frames: [string, number][] = [[root, 0]];
    index.set(root, next);
    low.set(root, next++);
    stack.push(root);
    onStack.add(root);

    while (frames.length) {
      const frame = frames.at(-1)!;
      const [unit, position] = frame;
      const targets = successors.get(unit) ?? [];
      if (position < targets.length) {
        frame[1]++;
        const target = targets[position]!;
        if (!index.has(target)) {
          index.set(target, next);
          low.set(target, next++);
          stack.push(target);
          onStack.add(target);
          frames.push([target, 0]);
        } else if (onStack.has(target)) {
          low.set(unit, Math.min(low.get(unit)!, index.get(target)!));
        }
        continue;
      }

      frames.pop();
      const parent = frames.at(-1)?.[0];
      if (parent !== undefined) {
        low.set(parent, Math.min(low.get(parent)!, low.get(unit)!));
      }
      if (low.get(unit) === index.get(unit)) {
        const component: string[] = [];
        let member: string;
        do {
          member = stack.pop()!;
          onStack.delete(member);
          component.push(member);
        } while (member !== unit);
        result.push(component);
      }
    }
  }
  return result;
}

/**
 * The shortest loop from `start` back to itself, by breadth-first search visiting neighbours in
 * code-point order. Any such loop stays inside the cycle, so the search does too.
 */
function example(start: string, members: Set<string>, successors: Map<string, string[]>): string[] {
  const parent = new Map<string, string>();
  const queue = [start];
  for (let head = 0; head < queue.length; head++) {
    const unit = queue[head]!;
    for (const target of successors.get(unit) ?? []) {
      if (!members.has(target)) {
        continue;
      }
      if (target === start) {
        const path = [start];
        for (let step = unit; step !== start; step = parent.get(step)!) {
          path.push(step);
        }
        path.push(start);
        return path.reverse();
      }
      if (!parent.has(target)) {
        parent.set(target, unit);
        queue.push(target);
      }
    }
  }
  throw new Error(`no loop through ${start}`);
}
