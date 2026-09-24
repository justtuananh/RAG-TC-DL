import { describe, expect, it } from "vitest";
import { locateQuote, splitHighlight } from "./highlight";

describe("splitHighlight", () => {
  it("splits around a valid range", () => {
    expect(splitHighlight("abcdef", 2, 4)).toEqual({ before: "ab", match: "cd", after: "ef" });
  });

  it("returns the whole text when the range is missing or invalid", () => {
    expect(splitHighlight("abc", null, null)).toEqual({ before: "abc", match: "", after: "" });
    expect(splitHighlight("abc", 2, 1)).toEqual({ before: "abc", match: "", after: "" });
    expect(splitHighlight("abc", 5, 9)).toEqual({ before: "abc", match: "", after: "" });
  });

  it("clamps out-of-range bounds", () => {
    expect(splitHighlight("abcdef", -3, 100)).toEqual({ before: "", match: "abcdef", after: "" });
  });
});

describe("locateQuote", () => {
  it("falls back to finding the quote when offsets are absent", () => {
    expect(locateQuote("đến 1 400 bar", "1 400", null, null)).toEqual({
      before: "đến ",
      match: "1 400",
      after: " bar",
    });
  });

  it("keeps offsets when they are valid", () => {
    expect(locateQuote("abcdef", "zzz", 1, 3)).toEqual({ before: "a", match: "bc", after: "def" });
  });

  it("does not fabricate a match", () => {
    expect(locateQuote("abcdef", "zzz", null, null)).toEqual({ before: "abcdef", match: "", after: "" });
  });
});
