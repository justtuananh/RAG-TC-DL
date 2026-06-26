/**
 * Normalize LLM LaTeX output so KaTeX / remark-math can render it.
 * Ports app.py _fix_latex:
 *   - Removes backtick wrappers around formulas
 *   - Converts \[...\] → $$...$$
 *   - Converts \(...\) → $...$
 *   - Fixes double backslashes (\\frac → \frac) inside math delimiters
 */
export function fixLatex(text) {
  if (!text) return "";

  // 1. `$...$` → $...$
  text = text.replace(/`(\$[^`]+?\$)`/g, "$1");

  // 2. \[...\] → $$...$$
  text = text.replace(/\\\[([\s\S]+?)\\\]/g, (_, m) =>
    "$$" + m.replace(/\\\\/g, "\\") + "$$"
  );

  // 3. \(...\) → $...$
  text = text.replace(/\\\(([\s\S]+?)\\\)/g, (_, m) =>
    "$" + m.replace(/\\\\/g, "\\") + "$"
  );

  // 4. Fix \\ inside $$...$$
  text = text.replace(/\$\$([\s\S]+?)\$\$/g, (_, m) =>
    "$$" + m.replace(/\\\\/g, "\\") + "$$"
  );

  // 5. Fix \\ inside $...$  (skip if $$ already handled above)
  text = text.replace(/(?<!\$)\$([^\n$]+?)\$(?!\$)/g, (_, m) =>
    "$" + m.replace(/\\\\/g, "\\") + "$"
  );

  return text;
}
